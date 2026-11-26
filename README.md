# 📹 Digifort CFTV Monitor — Auditoria Automatizada com CrewAI

Sistema multiagente desenvolvido em **Python** e **CrewAI** para auditoria automatizada de telemetria, disponibilidade, status de gravação e retenção em disco de servidores **Digifort Enterprise**, com geração de dashboard HTML interativo para operação de NOC.

O projeto utiliza uma **arquitetura híbrida determinística**: um coletor em Python consulta diretamente a API HTTP nativa do Digifort, cruza metadados e calcula métricas exatas antes de injetar o contexto estruturado nos agentes de IA locais (via **Ollama**), eliminando alucinações e dependência de APIs externas.

---

## 🚀 Funcionalidades Principais

- **Coleta Determinística via API HTTP:** Integração direta com os endpoints `/Interface/Cameras/GetCameras`, `/Interface/Cameras/GetStatus` e `/Interface/Cameras/GetGroups` do Digifort Enterprise.
- **Resolução Dinâmica de Hierarquia:** Mapeia automaticamente os UUIDs de grupos para a árvore completa de unidades/regionais cadastradas no servidor, sem necessidade de configurações fixas no código.
- **Diagnóstico Diferenciado de Falhas:**
  - **Incidentes Críticos:** Identifica quedas totais ou majoritárias por unidade/grupo (sugerindo falha de link de dados, túnel VPN ou NVR/switch local) e câmeras em estado *Falso Online* (conectadas, mas sem gravação em disco).
  - **Falhas Pontuais:** Isola câmeras offline individuais em unidades operacionais (indicando falha de hardware, cabeamento ou porta PoE).
- **Auditoria de Retenção em Disco:** Converte `RecordingHours` em dias reais gravados e sinaliza dispositivos ativos abaixo do SLA configurado (padrão de **28 dias** para metas de 30 dias), diferenciando recém-ativações de anomalias de storage/bitrate.
- **Dashboard HTML Interativo (`boletim_cftv.html`):** Gera automaticamente um painel visual em modo escuro com KPIs consolidados, cartões por grupo/cliente, filtro dinâmico em JavaScript, barras de retenção e o diagnóstico técnico estruturado dos agentes.
- **Inferência 100% Local (Ollama):** Configurado para rodar localmente em GPU (`qwen3:8b`), garantindo privacidade total dos dados operacionais e ausência de limites de requisições (*rate limits*).

---

## 🏗️ Arquitetura do Projeto

```text
digifort-cftv-monitor/
├── agents/
│   ├── inspetor_digifort.jsonc   # Agente auditor de telemetria e retenção
│   └── operador_noc.jsonc        # Agente redator do boletim técnico
├── tools/
│   ├── __init__.py
│   ├── digifort_api.py           # Coleta, cruzamento e cálculo determinístico
│   └── dashboard_html.py         # Gerador do dashboard HTML interativo
├── crew.jsonc                    # Orquestração declarativa sequencial da Crew
├── main.py                       # Ponto de entrada (coleta API + Crew + abertura do HTML)
├── .env.example                  # Modelo de variáveis de ambiente
├── .gitignore                    # Bloqueio de credenciais, dumps e relatórios gerados
└── pyproject.toml                # Dependências gerenciadas via uv
```

### Fluxo de Execução

1. `main.py` aciona a `DigifortStatusTool` para autenticar via HTTP Basic Auth na API do servidor Digifort.
2. `tools/digifort_api.py` extrai câmeras, status e grupos, reconstrói os caminhos das unidades, calcula taxas de disponibilidade e filtra alertas de retenção, gerando um JSON estruturado.
3. `inspetor_digifort` analisa estritamente o JSON coletado, classificando incidentes de infraestrutura vs. falhas pontuais.
4. `operador_noc` redige o parecer técnico em Markdown limpo com resumo executivo, tabelas de auditoria e plano de ação imediato.
5. `tools/dashboard_html.py` consolida os dados determinísticos e a análise dos agentes no arquivo `boletim_cftv.html` e o abre no navegador padrão.

---

## 🛠️ Pré-requisitos

- **Python 3.11+**
- **[`uv`](https://docs.astral.sh/uv/)** (gerenciador de pacotes e ambientes virtuais)
- **[Ollama](https://ollama.com/)** instalado localmente (validado com `qwen3:8b` em GPU com 8 GB de VRAM)
- Acesso de rede/VPN à porta HTTP da API do Digifort Enterprise (padrão `8601`) com usuário habilitado para leitura de interface (`GetCameras`, `GetStatus`, `GetGroups`)

---

## ⚙️ Instalação e Configuração

### 1. Clone o repositório e instale as dependências

```bash
git clone https://github.com/Tebaum/digifort-cftv-monitor
cd digifort-cftv-monitor
uv sync
```

### 2. Configure o modelo local no Ollama

Baixe o modelo `qwen3:8b` e crie o perfil customizado com janela de contexto ampliada (`12k`) e temperatura baixa (`0.1`) para maior fidelidade aos dados:

```powershell
ollama pull qwen3:8b

@"
FROM qwen3:8b
PARAMETER num_ctx 12288
PARAMETER num_predict 8192
PARAMETER temperature 0.1
"@ | Out-File -Encoding ascii Modelfile-cftv8b

ollama create qwen3-cftv -f Modelfile-cftv8b
```

*(Opcional para GPUs com 8 GB de VRAM)* Ative a compressão de cache KV no Windows para manter 100% do processamento na GPU:

```powershell
setx OLLAMA_FLASH_ATTENTION 1
setx OLLAMA_KV_CACHE_TYPE q8_0
```

### 3. Configure as variáveis de ambiente

Copie o arquivo `.env.example` para `.env` e preencha com os dados do seu servidor:

```bash
cp .env.example .env
```

Exemplo de configuração no `.env`:

```ini
# Configuração do LLM Local (Ollama compatível com OpenAI API)
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_API_KEY=ollama
MODEL=openai/qwen3-cftv
CREWAI_TRACING_ENABLED=false

# Configuração da API HTTP do Digifort Enterprise
DIGIFORT_URL=http://IP_DO_SERVIDOR:8601
DIGIFORT_SERVER_NAME=Servidor Digifort Principal
DIGIFORT_USER=usuario_leitura_api
DIGIFORT_PASS=senha_segura
DIGIFORT_TIMEOUT=15
```

---

## ▶️ Como Executar

Com o Ollama ativo e a rede/VPN conectada ao servidor Digifort, execute:

```bash
uv run python main.py
```

Ao final da execução, o dashboard será salvo na raiz do projeto como `boletim_cftv.html` (ignorado automaticamente pelo `.gitignore`) e aberto no navegador.

---

## 🔒 Segurança e Boas Práticas

- **Zero Hardcoding:** Nenhuma credencial, endereço IP, topologia ou identificação de ambiente é armazenada no código-fonte ou nas definições dos agentes.
- **Proteção de Saídas e Dumps:** O `.gitignore` bloqueia arquivos `.env*`, dumps `.json`, perfis temporários `Modelfile*` e relatórios gerados (`boletim_*.html` e `boletim_*.md`), impedindo vazamento acidental de inventário em commits.
- **Processamento Local:** Toda a inferência dos agentes ocorre localmente via Ollama, sem envio de telemetria operacional para serviços externos.
- **Travamento Anti-Alucinação:** Toda contagem, conversão de horas para dias e agrupamento topológico é executada via Python antes da inferência do LLM.