import json
from datetime import datetime
from dotenv import load_dotenv
from crewai.project.crew_loader import load_crew
from tools.digifort_api import DigifortStatusTool


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

    crew, _ = load_crew("crew.jsonc")
    resultado = crew.kickoff(
        inputs={
            "data_hora_atual": agora,
            "dados_digifort": dados_json,
        }
    )
    print("\n3. Boletim gerado em 'boletim_cftv.md'!")
    return resultado


if __name__ == "__main__":
    run()