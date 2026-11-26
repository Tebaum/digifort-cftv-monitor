import json
import webbrowser
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from crewai.project.crew_loader import load_crew
from tools.digifort_api import DigifortStatusTool
from tools.dashboard_html import gerar_dashboard_html


def run():
    load_dotenv()

    print("1. Coletando telemetria da API HTTP do servidor Digifort...")
    tool = DigifortStatusTool()
    dados_json = tool._run(grupo_filtro="TODOS", min_dias_retencao=28.0)
    dados_dict = json.loads(dados_json)

    if "erro" in dados_dict:
        print(f"\n[ERRO CRÍTICO DE COLETA] {dados_dict['erro']}")
        print("Execução abortada para evitar geração de relatório sem dados reais.")
        return

    agora = datetime.now().strftime("%d/%m/%Y - %H:%M")
    print(f"2. Coleta concluída com sucesso ({agora}). Iniciando análise dos agentes...")

    resultado = None
    parecer_ia = ""

    try:
        crew, _ = load_crew("crew.jsonc")
        resultado = crew.kickoff(
            inputs={
                "data_hora_atual": agora,
                "dados_digifort": dados_json,
            }
        )
        parecer_ia = str(resultado.raw)
    except Exception as e:
        print(f"\n[AVISO LLM] Provedor indisponível ({type(e).__name__}). Gerando dashboard em modo contingência...")
        parecer_ia = (
            "### Modo de Contingência Determinística\n"
            "O provedor de IA atingiu limite de taxa (Rate Limit) ou está temporariamente indisponível. "
            "Todos os indicadores, incidentes críticos, dispositivos offline e alertas de retenção acima "
            "foram extraídos diretamente da API HTTP do servidor Digifort com 100% de precisão."
        )

    arquivo_html = gerar_dashboard_html(
        dados_dict=dados_dict,
        data_hora=agora,
        parecer_ia_md=parecer_ia,
        caminho_saida="boletim_cftv.html",
    )

    if resultado:
        print(f"\n3. Boletins gerados: 'boletim_cftv.md' e '{arquivo_html}'!")
    else:
        print(f"\n3. Dashboard de contingência gerado em '{arquivo_html}'!")

    webbrowser.open(Path(arquivo_html).resolve().as_uri())
    return resultado


if __name__ == "__main__":
    run()