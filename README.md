Markdown

# 📹 Digifort CFTV Monitor — Auditoria Automatizada com CrewAI

Sistema multiagente desenvolvido em **Python** e **CrewAI** para auditoria automatizada de telemetria, disponibilidade, status de gravação e retenção em disco de servidores **Digifort Enterprise**.

O projeto utiliza uma **arquitetura híbrida determinística**: um coletor em Python consulta diretamente a API HTTP nativa do Digifort, cruza metadados e calcula métricas exatas antes de injetar o contexto estruturado nos agentes de IA, eliminando alucinações e gerando boletins operacionais prontos para Centros de Operações de Rede (NOC).

---

## 🚀 Funcionalidades Principais

* **Coleta Determinística via API HTTP:** Integração direta com os endpoints `/Interface/Cameras/GetCameras`, `/Interface/Cameras/GetStatus` e `/Interface/Cameras/GetGroups` do Digifort Enterprise.
* **Resolução Dinâmica de Hierarquia:** Mapeia automaticamente os UUIDs de grupos para a árvore completa de unidades/regionais cadastradas no servidor, sem necessidade de configurações fixas no código.
* **Diagnóstico Diferenciado de Falhas:**
  * **Incidentes Críticos:** Identifica quedas totais ou majoritárias por unidade/grupo (sugerindo falha de link de dados, túnel VPN ou NVR/switch local) e câmeras em estado *Falso Online* (conectadas, mas sem gravação em disco).
  * **Falhas Pontuais:** Isola câmeras offline individuais em unidades operacionais (indicando falha de hardware, cabeamento ou porta PoE).
* **Auditoria de Retenção em Disco:** Converte `RecordingHours` em dias reais gravados e sinaliza dispositivos ativos abaixo do SLA configurado (padrão de **28 dias** para metas de 30 dias), diferenciando recém-ativações de anomalias de storage/bitrate.
* **Geração de Boletim Executivo:** Consolida os indicadores em um relatório técnico limpo em Markdown (`boletim_cftv.md`).

---

## 🏗️ Arquitetura do Projeto

```text
digifort-cftv-monitor/
├── agents/
│   ├── inspetor_digifort.jsonc   # Agente auditor de telemetria e retenção
│   └── operador_noc.jsonc        # Agente redator do boletim técnico
├── tools/
│   └── digifort_api.py           # Ferramenta de consulta, cruzamento e cálculo determinístico
├── crew.jsonc                    # Orquestração declarativa sequencial da Crew
├── main.py                       # Ponto de entrada (coleta API + disparo dos agentes)
├── .env.example                  # Modelo de variáveis de ambiente
├── .gitignore                    # Bloqueio de credenciais e relatórios gerados
└── pyproject.toml                # Dependências gerenciadas via uv

Fluxo de Execução

main.py aciona a DigifortStatusTool para autenticar via HTTP Basic Auth na API do servidor Digifort.

tools/digifort_api.py extrai câmeras, status e grupos, reconstrói os caminhos das unidades, calcula taxas de disponibilidade e filtra alertas de retenção, gerando um JSON estruturado.

inspetor_digifort analisa estritamente o JSON coletado, classificando incidentes de infraestrutura vs. falhas pontuais.

operador_noc redige o documento final boletim_cftv.md com resumo executivo, tabelas de auditoria e plano de ação imediato.

🛠️ Pré-requisitos

Python 3.11+

uv (gerenciador de pacotes e ambientes virtuais)

Acesso de rede/VPN à porta HTTP da API do Digifort Enterprise (padrão 8601) com usuário habilitado para leitura de interface (GetCameras, GetStatus, GetGroups)

Endpoint compatível com a API OpenAI (local ou em nuvem) para execução do LLM

⚙️ Instalação e Configuração

Clone o repositório:

Bash
git clone https://github.com/Tebaum/asterixco_digifort_monitor
cd digifort-cftv-monitor

Instale as dependências com uv:

Bash
uv sync

Configure as variáveis de ambiente:

Copie o arquivo .env.example para .env e preencha com as credenciais do seu ambiente:

Bash
cp .env.example .env

Exemplo de configuração no .env:

Ini, TOML
# Configuração do LLM (compatível com OpenAI API)
OPENAI_API_BASE=http://127.0.0.1:31415/v1
OPENAI_API_KEY=sua_chave_aqui
MODEL=openai/gemini-3.5-flash
CREWAI_TRACING_ENABLED=false

# Configuração da API HTTP do Digifort Enterprise
DIGIFORT_URL=http://IP_DO_SERVIDOR:8601
DIGIFORT_SERVER_NAME=Servidor Digifort Principal
DIGIFORT_USER=usuario_leitura_api
DIGIFORT_PASS=senha_segura
DIGIFORT_TIMEOUT=15

▶️ Como Executar

Com o ambiente configurado e a rede/VPN ativa, execute:

Bash
uv run python main.py

Ao final da execução, o relatório consolidado será salvo na raiz do projeto como boletim_cftv.md (arquivo ignorado automaticamente pelo .gitignore para preservar a confidencialidade dos dados operacionais).

🔒 Segurança e Boas Práticas

Zero Hardcoding: Nenhuma credencial, endereço IP, topologia ou identificação de ambiente é armazenada no código-fonte.

Proteção de Saídas: O .gitignore bloqueia arquivos .env* e relatórios gerados (boletim_*.md), impedindo vazamento acidental de inventário de câmeras em commits.

Travamento Anti-Alucinação: Toda contagem, conversão de horas para dias e agrupamento topológico é executada via Python antes da inferência do LLM.