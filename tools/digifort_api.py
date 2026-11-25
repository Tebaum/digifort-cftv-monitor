import os
import json
from collections import defaultdict
import requests
from requests.auth import HTTPBasicAuth
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class DigifortMonitorInput(BaseModel):
    grupo_filtro: str = Field(
        default="TODOS",
        description="Nome ou trecho do grupo/cliente raiz para filtrar, ou 'TODOS' para auditar todo o servidor.",
    )
    min_dias_retencao: float = Field(
        default=28.0,
        description="Mínimo de dias de gravação aceitáveis (padrão 28.0 dias).",
    )


class DigifortStatusTool(BaseTool):
    name: str = "consultar_status_digifort"
    description: str = (
        "Consulta a API HTTP de um servidor Digifort Enterprise (GetCameras, GetStatus e GetGroups), "
        "cruza metadados de descrição e hierarquia de grupos com telemetria de conexão, "
        "gravação ativa e dias de retenção em disco."
    )
    args_schema: Type[BaseModel] = DigifortMonitorInput

    def _fazer_requisicao(self, endpoint: str, user: str, password: str, timeout: int) -> dict:
        base_url = os.getenv("DIGIFORT_URL", "http://localhost:8601").rstrip("/")
        url = f"{base_url}{endpoint}"
        resp = requests.get(
            url,
            params={"ResponseFormat": "JSON"},
            auth=HTTPBasicAuth(user, password),
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _montar_mapa_grupos(self, grupos_raw: list) -> dict:
        por_id = {
            g.get("ID", "").strip(): {
                "nome": g.get("Name", "").strip(),
                "parent": g.get("Parent", "").strip(),
            }
            for g in grupos_raw
            if g.get("ID")
        }

        mapa = {}
        for gid, info in por_id.items():
            caminho = [info["nome"]]
            atual_parent = info["parent"]
            visitados = {gid}
            while atual_parent and atual_parent in por_id and atual_parent not in visitados:
                visitados.add(atual_parent)
                caminho.insert(0, por_id[atual_parent]["nome"])
                atual_parent = por_id[atual_parent]["parent"]
            mapa[gid] = {
                "raiz": caminho[0] if caminho else "GERAL",
                "caminho_completo": " / ".join(caminho),
            }
        return mapa

    def _run(self, grupo_filtro: str = "TODOS", min_dias_retencao: float = 28.0) -> str:
        user = os.getenv("DIGIFORT_USER")
        password = os.getenv("DIGIFORT_PASS")
        servidor_nome = os.getenv("DIGIFORT_SERVER_NAME", "Digifort Enterprise Server")
        timeout = int(os.getenv("DIGIFORT_TIMEOUT", "15"))

        if not user or not password:
            return json.dumps(
                {"erro": "Credenciais DIGIFORT_USER ou DIGIFORT_PASS ausentes no .env."},
                ensure_ascii=False,
            )

        try:
            resp_info = self._fazer_requisicao("/Interface/Cameras/GetCameras", user, password, timeout)
            resp_status = self._fazer_requisicao("/Interface/Cameras/GetStatus", user, password, timeout)
            resp_grupos = self._fazer_requisicao("/Interface/Cameras/GetGroups", user, password, timeout)
        except requests.exceptions.ConnectTimeout:
            return json.dumps(
                {"erro": "Timeout ao conectar no servidor Digifort. Verifique a rede/VPN."},
                ensure_ascii=False,
            )
        except requests.exceptions.ConnectionError:
            return json.dumps(
                {"erro": "Falha de conexão com a API HTTP do servidor Digifort."},
                ensure_ascii=False,
            )
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else "N/D"
            return json.dumps(
                {"erro": f"Erro HTTP {code} ao consultar API do Digifort."},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"erro": f"Falha inesperada na leitura da API: {type(e).__name__}"},
                ensure_ascii=False,
            )

        cameras_info = resp_info.get("Response", {}).get("Data", {}).get("Cameras", [])
        cameras_status = resp_status.get("Response", {}).get("Data", {}).get("Cameras", [])
        grupos_raw = resp_grupos.get("Response", {}).get("Data", {}).get("Groups", [])

        mapa_grupos = self._montar_mapa_grupos(grupos_raw)

        mapa_metadados = {
            cam.get("Name", "").strip(): {
                "descricao": cam.get("Description", "").strip(),
                "grupo_id": cam.get("Group", "SEM_GRUPO").strip(),
                "modelo": cam.get("Model", "").strip(),
            }
            for cam in cameras_info
        }

        totais_por_grupo = defaultdict(int)
        for cam in cameras_info:
            grp = cam.get("Group", "SEM_GRUPO").strip()
            totais_por_grupo[grp] += 1

        resumo = defaultdict(
            lambda: {
                "total_monitoradas": 0,
                "online_e_gravando": 0,
                "desativadas_no_servidor": [],
                "offline": [],
                "falso_online_sem_gravacao": [],
                "alerta_baixa_retencao": [],
            }
        )

        filtro = grupo_filtro.upper().strip()

        for st in cameras_status:
            nome = st.get("Name", "").strip()
            meta = mapa_metadados.get(
                nome, {"descricao": "N/D", "grupo_id": "SEM_GRUPO", "modelo": "N/D"}
            )
            grupo_id = meta["grupo_id"]
            info_grupo = mapa_grupos.get(
                grupo_id, {"raiz": "GERAL", "caminho_completo": grupo_id}
            )
            grupo_raiz = info_grupo["raiz"]

            if filtro != "TODOS" and filtro not in info_grupo["caminho_completo"].upper():
                continue

            ativa = bool(st.get("Active", False))
            working = bool(st.get("Working", False))
            config_gravar = bool(st.get("ConfiguredToRecord", False))
            gravando = bool(st.get("WrittingToDisk", False))
            fps = st.get("RecordingFPS", 0)

            horas_gravadas = float(st.get("RecordingHours", 0) or 0)
            horas_estimadas = float(st.get("RecordingHoursEstimative", 0) or 0)
            dias_gravados = round(horas_gravadas / 24.0, 1)
            dias_estimados = round(horas_estimadas / 24.0, 1)

            resumo[grupo_raiz]["total_monitoradas"] += 1

            registro = {
                "camera": nome,
                "descricao": meta["descricao"],
                "unidade_grupo": info_grupo["caminho_completo"],
                "grupo_id": grupo_id,
                "total_cameras_no_grupo": totais_por_grupo[grupo_id],
                "modelo": meta["modelo"],
                "dias_gravados": dias_gravados,
                "dias_estimados_meta": dias_estimados,
                "horas_gravadas": horas_gravadas,
            }

            if not ativa:
                resumo[grupo_raiz]["desativadas_no_servidor"].append(registro)
            elif not working:
                resumo[grupo_raiz]["offline"].append(registro)
            elif config_gravar and not gravando:
                registro["fps_atual"] = fps
                resumo[grupo_raiz]["falso_online_sem_gravacao"].append(registro)
            else:
                resumo[grupo_raiz]["online_e_gravando"] += 1
                if config_gravar and dias_gravados < min_dias_retencao:
                    resumo[grupo_raiz]["alerta_baixa_retencao"].append(registro)

        for grp in resumo:
            resumo[grp]["alerta_baixa_retencao"].sort(key=lambda x: x["dias_gravados"])

        saida = {
            "servidor": servidor_nome,
            "parametro_min_dias_retencao": min_dias_retencao,
            "grupos_monitorados": dict(resumo),
        }
        return json.dumps(saida, ensure_ascii=False, indent=2)