import html
import re

def _renderizar_tabela_md(linhas_tabela: list[str]) -> str:
    """Converte linhas de tabela Markdown (| a | b |) em tabela HTML alinhada."""
    linhas_limpas = [
        [c.strip() for c in l.strip().strip("|").split("|")]
        for l in linhas_tabela
        if l.strip()
    ]
    if len(linhas_limpas) < 2:
        return "".join(f"<p>{html.escape(l)}</p>" for l in linhas_tabela)

    cabecalho = linhas_limpas[0]
    # Pula a linha separadora (| :--- | :---: |) se existir
    inicio_dados = 2 if all(re.match(r"^:?-{2,}:?$", c) for c in linhas_limpas[1] if c) else 1
    corpo = linhas_limpas[inicio_dados:]

    def _formatar_celula(txt: str) -> str:
        t = html.escape(txt)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t

    ths = "".join(f"<th>{_formatar_celula(col)}</th>" for col in cabecalho)
    trs = []
    for row in corpo:
        tds = "".join(f"<td>{_formatar_celula(col)}</td>" for col in row)
        trs.append(f"<tr>{tds}</tr>")

    return (
        "<div class='table-wrap ia-table-wrap'>"
        f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
        "</div>"
    )

def _formatar_texto_ia_para_html(texto_md: str) -> str:
    """Converte o parecer e o plano de ação da Crew em HTML limpo, incluindo tabelas."""
    texto_limpo = re.sub(r"^```[a-zA-Z]*\s*", "", texto_md.strip())
    texto_limpo = re.sub(r"\s*```$", "", texto_limpo.strip())
    linhas = texto_limpo.splitlines()
    blocos = []
    buffer_tabela = []

    def _descarregar_tabela():
        nonlocal buffer_tabela
        if buffer_tabela:
            blocos.append(_renderizar_tabela_md(buffer_tabela))
            buffer_tabela = []

    
    for linha in linhas:
        l = linha.strip()
        if l.startswith("|") and l.count("|") >= 2:
            buffer_tabela.append(l)
            continue

        _descarregar_tabela()

        if not l:
            continue

        l_esc = html.escape(l)
        l_esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", l_esc)
        l_esc = re.sub(r"`(.+?)`", r"<code>\1</code>", l_esc)

        if l.startswith("### "):
            blocos.append(f"<h4>{l_esc[4:]}</h4>")
        elif l.startswith("## "):
            blocos.append(f"<h3>{l_esc[3:]}</h3>")
        elif l.startswith("# "):
            blocos.append(f"<h3>{l_esc[2:]}</h3>")
        elif l.startswith(("- ", "* ")):
            blocos.append(f"<div class='ia-item'>• {l_esc[2:]}</div>")
        elif re.match(r"^\d+\.\s", l):
            blocos.append(f"<div class='ia-item ia-step'>{l_esc}</div>")
        else:
            blocos.append(f"<p>{l_esc}</p>")

    _descarregar_tabela()
    return "\n".join(blocos)


def gerar_dashboard_html(
    dados_dict: dict,
    data_hora: str,
    parecer_ia_md: str,
    caminho_saida: str = "boletim_cftv.html",
) -> str:
    servidor = html.escape(dados_dict.get("servidor", "Servidor Digifort"))
    min_dias = float(dados_dict.get("parametro_min_dias_retencao", 28.0))
    grupos = dados_dict.get("grupos_monitorados", {})

    total_cams = sum(g["total_monitoradas"] for g in grupos.values())
    total_online = sum(g["online_e_gravando"] for g in grupos.values())
    total_offline = sum(len(g["offline"]) for g in grupos.values())
    total_falso_online = sum(len(g["falso_online_sem_gravacao"]) for g in grupos.values())
    total_baixa_ret = sum(len(g["alerta_baixa_retencao"]) for g in grupos.values())
    disp_geral = round((total_online / total_cams * 100), 2) if total_cams else 0.0

    cards_grupos_html = []
    incidentes_criticos_html = []
    linhas_offline_html = []
    linhas_retencao_html = []
    opcoes_filtro = ['<option value="TODOS">Todos os Grupos / Clientes</option>']

    unidades_stats = {}

    for grupo_nome, info in sorted(grupos.items()):
        g_esc = html.escape(grupo_nome)
        opcoes_filtro.append(f'<option value="{g_esc}">{g_esc}</option>')

        t_mon = info["total_monitoradas"]
        t_on = info["online_e_gravando"]
        t_off = len(info["offline"])
        t_fo = len(info["falso_online_sem_gravacao"])
        t_br = len(info["alerta_baixa_retencao"])
        disp = round((t_on / t_mon * 100), 2) if t_mon else 0.0
        cor_disp = "#10b981" if disp >= 98 else ("#f59e0b" if disp >= 90 else "#ef4444")

        cards_grupos_html.append(f"""
        <div class="group-card" data-grupo="{g_esc}">
            <div class="group-header">
                <span class="group-title">{g_esc}</span>
                <span class="badge-disp" style="background:{cor_disp}22;color:{cor_disp};border:1px solid {cor_disp}55;">
                    {disp:.2f}% Disponível
                </span>
            </div>
            <div class="group-metrics">
                <div><strong>{t_mon}</strong><span>Total</span></div>
                <div><strong class="txt-ok">{t_on}</strong><span>Online</span></div>
                <div><strong class="txt-err">{t_off}</strong><span>Offline</span></div>
                <div><strong class="txt-warn">{t_fo}</strong><span>Falso On</span></div>
                <div><strong class="txt-warn">{t_br}</strong><span>&lt; {min_dias:.0f}d Ret.</span></div>
            </div>
        </div>
        """)

        for cam in info["offline"]:
            uid = cam["grupo_id"]
            if uid not in unidades_stats:
                unidades_stats[uid] = {
                    "grupo_raiz": grupo_nome,
                    "unidade": cam["unidade_grupo"],
                    "total_unidade": cam["total_cameras_no_grupo"],
                    "offline_cams": [],
                }
            unidades_stats[uid]["offline_cams"].append(cam)

            linhas_offline_html.append(f"""
            <tr data-grupo="{g_esc}">
                <td><span class="pill-grupo">{g_esc}</span></td>
                <td>{html.escape(cam['unidade_grupo'])}</td>
                <td><strong>{html.escape(cam['camera'])}</strong></td>
                <td>{html.escape(cam['descricao'])}</td>
                <td><code>{html.escape(cam['modelo'])}</code></td>
                <td><span class="status-badge status-off">OFFLINE</span></td>
                <td>{cam['dias_gravados']:.1f} d</td>
            </tr>
            """)

        for cam in info["falso_online_sem_gravacao"]:
            incidentes_criticos_html.append(f"""
            <div class="alert-box alert-crit" data-grupo="{g_esc}">
                <strong>Falso Online (Sem Gravação em Disco):</strong>
                {html.escape(cam['camera'])} — {html.escape(cam['descricao'])}
                ({html.escape(cam['unidade_grupo'])}) | FPS Atual: {cam.get('fps_atual', 0)}
            </div>
            """)

        for cam in info["alerta_baixa_retencao"]:
            meta_dias = cam["dias_estimados_meta"] or 30.0
            pct = min(100.0, round((cam["dias_gravados"] / meta_dias) * 100, 1)) if meta_dias > 0 else 0
            linhas_retencao_html.append(f"""
            <tr data-grupo="{g_esc}">
                <td><span class="pill-grupo">{g_esc}</span></td>
                <td>{html.escape(cam['unidade_grupo'])}</td>
                <td><strong>{html.escape(cam['camera'])}</strong></td>
                <td>{html.escape(cam['descricao'])}</td>
                <td>
                    <div class="ret-bar-wrap">
                        <div class="ret-bar" style="width:{pct}%;"></div>
                    </div>
                    <small>{cam['dias_gravados']:.1f}d / {meta_dias:.0f}d ({cam['horas_gravadas']:.1f}h)</small>
                </td>
            </tr>
            """)

    for uid, st in unidades_stats.items():
        qtd_off = len(st["offline_cams"])
        tot_u = st["total_unidade"]
        if tot_u > 1 and (qtd_off == tot_u or qtd_off / tot_u >= 0.5):
            g_esc = html.escape(st["grupo_raiz"])
            cams_nomes = ", ".join(html.escape(c["camera"]) for c in st["offline_cams"])
            incidentes_criticos_html.insert(0, f"""
            <div class="alert-box alert-crit" data-grupo="{g_esc}">
                <strong>Queda Crítica de Unidade ({qtd_off}/{tot_u} câmeras offline):</strong>
                {html.escape(st['unidade'])} — Suspeita de falha em link de dados, VPN ou NVR/switch local.
                <br><small>Dispositivos afetados: {cams_nomes}</small>
            </div>
            """)

    bloco_criticos = (
        "\n".join(incidentes_criticos_html)
        if incidentes_criticos_html
        else '<div class="alert-box alert-ok">Nenhum incidente crítico de queda de unidade ou falso online identificado.</div>'
    )

    tabela_offline = (
        "\n".join(linhas_offline_html)
        if linhas_offline_html
        else '<tr><td colspan="7" class="empty-row">Nenhuma câmera offline registrada nesta auditoria.</td></tr>'
    )

    tabela_retencao = (
        "\n".join(linhas_retencao_html)
        if linhas_retencao_html
        else '<tr><td colspan="5" class="empty-row">Todas as câmeras ativas atendem ao SLA de retenção.</td></tr>'
    )

    parecer_html = _formatar_texto_ia_para_html(parecer_ia_md)

    html_final = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard CFTV — {servidor}</title>
<style>
  :root {{
    --bg: #0f172a; --card: #1e293b; --border: #334155;
    --text: #f1f5f9; --muted: #94a3b8;
    --ok: #10b981; --warn: #f59e0b; --err: #ef4444; --accent: #38bdf8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }}
  .container {{ max-width: 1280px; margin: 0 auto; }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px; border-bottom: 1px solid var(--border); padding-bottom: 18px; margin-bottom: 24px; }}
  header h1 {{ font-size: 1.5rem; color: var(--accent); }}
  header .meta {{ color: var(--muted); font-size: 0.9rem; }}
  select {{ background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .kpi span {{ display: block; font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .kpi strong {{ font-size: 1.8rem; display: block; margin-top: 4px; }}
  .txt-ok {{ color: var(--ok); }} .txt-warn {{ color: var(--warn); }} .txt-err {{ color: var(--err); }}
  .section-title {{ font-size: 1.1rem; margin: 26px 0 12px; color: #e2e8f0; border-left: 4px solid var(--accent); padding-left: 10px; }}
  .groups-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
  .group-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .group-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }}
  .group-title {{ font-weight: 700; font-size: 1.05rem; }}
  .badge-disp {{ padding: 3px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }}
  .group-metrics {{ display: grid; grid-template-columns: repeat(5, 1fr); text-align: center; gap: 6px; }}
  .group-metrics strong {{ display: block; font-size: 1.15rem; }}
  .group-metrics span {{ font-size: 0.72rem; color: var(--muted); }}
  .alert-box {{ padding: 14px 16px; border-radius: 8px; margin-bottom: 10px; font-size: 0.92rem; }}
  .alert-crit {{ background: #ef44441a; border: 1px solid #ef444466; color: #fecaca; }}
  .alert-ok {{ background: #10b9811a; border: 1px solid #10b98155; color: #a7f3d0; }}
  .table-wrap {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ padding: 12px 14px; text-align: center; border-bottom: 1px solid var(--border); }}
  th {{ background: #0f172a88; color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }}
  tr:last-child td {{ border-bottom: none; }}
  .empty-row {{ text-align: center; color: var(--muted); padding: 20px; }}
  .pill-grupo {{ background: #38bdf822; color: var(--accent); padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }}
  .status-badge {{ padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }}
  .status-off {{ background: #ef444433; color: #fca5a5; }}
  .ret-bar-wrap {{ width: 140px; height: 8px; background: #0f172a; border-radius: 999px; overflow: hidden; margin: 0 auto 4px; }}
  .ret-bar {{ height: 100%; background: var(--warn); }}
  .ia-box {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; font-size: 0.93rem; }}
  .ia-box h3, .ia-box h4 {{ color: var(--accent); margin: 12px 0 6px; }}
  .ia-table-wrap {{ margin: 10px 0 18px; background: #0f172a66; }}
  .ia-item {{ margin: 6px 0; padding-left: 8px; }}
  code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>Monitoramento & Telemetria CFTV</h1>
      <div class="meta">Servidor: <strong>{servidor}</strong> &bull; Auditoria: <strong>{html.escape(data_hora)}</strong></div>
    </div>
    <div>
      <select id="filtroGrupo" onchange="filtrarGrupo()">
        {"".join(opcoes_filtro)}
      </select>
    </div>
  </header>

  <section class="kpi-grid">
    <div class="kpi"><span>Total Monitoradas</span><strong>{total_cams}</strong></div>
    <div class="kpi"><span>Online e Gravando</span><strong class="txt-ok">{total_online}</strong></div>
    <div class="kpi"><span>Disponibilidade Geral</span><strong class="txt-ok">{disp_geral:.2f}%</strong></div>
    <div class="kpi"><span>Câmeras Offline</span><strong class="txt-err">{total_offline}</strong></div>
    <div class="kpi"><span>Falso Online</span><strong class="txt-warn">{total_falso_online}</strong></div>
    <div class="kpi"><span>Baixa Retenção (&lt;{min_dias:.0f}d)</span><strong class="txt-warn">{total_baixa_ret}</strong></div>
  </section>

  <h2 class="section-title">Disponibilidade por Grupo / Cliente</h2>
  <section class="groups-grid">
    {"".join(cards_grupos_html)}
  </section>

  <h2 class="section-title">Incidentes Críticos</h2>
  <section>
    {bloco_criticos}
  </section>

  <h2 class="section-title">Falhas Pontuais (Dispositivos Offline)</h2>
  <section class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Grupo</th><th>Unidade</th><th>Câmera</th><th>Descrição</th><th>Modelo</th><th>Status</th><th>Retenção</th>
        </tr>
      </thead>
      <tbody>{tabela_offline}</tbody>
    </table>
  </section>

  <h2 class="section-title">Auditoria de Retenção em Disco (SLA &lt; {min_dias:.0f} dias)</h2>
  <section class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Grupo</th><th>Unidade</th><th>Câmera</th><th>Descrição</th><th>Histórico Gravado</th>
        </tr>
      </thead>
      <tbody>{tabela_retencao}</tbody>
    </table>
  </section>

  <h2 class="section-title">Diagnóstico Técnico e Plano de Ação (NOC)</h2>
  <section class="ia-box">
    {parecer_html}
  </section>
</div>

<script>
function filtrarGrupo() {{
  const sel = document.getElementById("filtroGrupo").value;
  document.querySelectorAll("[data-grupo]").forEach(el => {{
    el.style.display = (sel === "TODOS" || el.dataset.grupo === sel) ? "" : "none";
  }});
}}
</script>
</body>
</html>
"""

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html_final)

    return caminho_saida