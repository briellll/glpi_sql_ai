-----

# GLPI SQL AI

Um **assistente de IA** que entende perguntas em **linguagem natural** sobre o banco de dados **GLPI**, gera a **query SQL automaticamente**, executa-a e responde em **portugues natural** — tudo direto no seu **terminal**.

-----

## Sumario

  * [Funcionalidades]
  * [Arquitetura Multi-Agente]
  * [Estrutura do Projeto]
  * [Tecnologias Utilizadas]
  * [Instalacao e Configuracao]
  * [Como Usar]
  * [Fluxo da Aplicacao]
  * [Ambiente de Teste (Seed)]
  * [Exemplos de Perguntas]
  * [Como Contribuir]
  * [Licenca]

-----

## Funcionalidades

  * **Consultas em Linguagem Natural**
    Faca perguntas como "quantos chamados atrasados existem?" — e receba respostas completas sem escrever uma linha de SQL.

  * **Classificacao Automatica de Intencao**
    O modelo entende se voce quer **consultar dados** ou **gerar solucoes para um chamado especifico**.

  * **Validacao de Escopo (Guardrail)**
    Um no `guard_scope` no grafo supervisor bloqueia perguntas fora do dominio helpdesk/GLPI (ex: saude, esportes, curiosidades), impedindo que cheguem aos workers.

  * **Integracao com a Base de Conhecimento GLPI**
    Enriquece as sugestoes de solucao com artigos diretamente da sua `Knowbase` do GLPI, indexados via **busca semantica vetorial** (ChromaDB + OpenAI Embeddings).

  * **Engenharia de Prompt Avancada**
    Inclui um "Dicionario de Termos de Negocio" e um mapa detalhado das tabelas do GLPI, garantindo queries mais precisas e contextualizadas.

  * **Auto-correcao de SQL**
    O worker de SQL tenta executar a query e, em caso de erro, corrige automaticamente ate **3 tentativas**.

  * **Arquitetura Multi-Agente (LangGraph)**
    Grafo supervisor que roteia entre workers especializados — `sql_worker` para consultas e `solutions_worker` para solucoes com base de conhecimento.

  * **Integracao com o GLPI**
    Totalmente adaptado a estrutura de dados do sistema de chamados GLPI (MySQL) e sua API REST para a Base de Conhecimento.

-----

## Arquitetura Multi-Agente

O sistema utiliza **LangGraph** para orquestrar um grafo supervisor com dois workers especializados.

```
[Usuario faz pergunta]
        |
[Supervisor: classificacao de intencao]
        |
[Supervisor: validacao de escopo]
        |
       / \
      /   \
[SQL Worker]    [Solutions Worker]
     |                |
 Gera SQL        Extrai ID do chamado
     |            Busca detalhes (MySQL)
 Executa SQL     Busca artigos KB (vetorial)
     |            Gera solucoes (LLM)
 Auto-corrige         |
 (ate 3x)        Resposta final
     |                |
     \______________/
            |
    [Resposta no terminal]
```
```
[Fora do escopo]
        |
[Resposta educada de recusa — sem acionar workers]
```

| Agente | Funcao |
| ------ | ------ |
| Supervisora | Classifica intencao (`database_query` ou `get_solutions`), valida escopo e roteia para o worker |
| Guardiao de Escopoa | Bloqueia perguntas fora do dominio helpdesk/GLPI com recusa educada |
| SQL Workera | Gera SQL, executa no MySQL, auto-corrige erros, formata resposta natural |
| Solutions Workera | Extrai ID do chamado, busca na base vetorial (ChromaDB), gera solucoes baseadas nos artigos |

-----

## Estrutura do Projeto

```
glpi-sql-ai/
├── .env                       # Configuracoes de ambiente (chaves, DB, GLPI API)
├── pyproject.toml             # Dependencias e metadata do Poetry
├── README.md
├── scripts/
│   └── seed_test_data.py      # Script de seed para ambiente de teste
└── src/
    └── glpi_sql_ai/
        ├── __init__.py
        ├── agents/
        │   ├── __init__.py
        │   ├── supervisor.py         # Grafo supervisor (classifica e roteia)
        │   ├── sql_worker.py         # Worker de consultas SQL com auto-correcao
        │   └── solutions_worker.py   # Worker de solucoes com busca vetorial
        ├── tools/
        │   ├── __init__.py
        │   └── db_tools.py           # Wrappers de acesso ao banco
        ├── config.py           # AppContext: DB, LLM, VectorStore e KB
        ├── prompts.py          # Templates de prompts e instrucoes do sistema
        ├── chains.py           # Factories das LangChains
        ├── memory.py           # Memoria conversacional entre turnos
        ├── vector_store.py     # ChromaDB + OpenAI Embeddings (busca semantica)
        ├── knowledge_base.py   # Modulo de acesso a API REST do GLPI
        ├── services.py         # Logica de negocio (legado)
        └── main.py             # Loop principal do chat interativo
```

-----

## Tecnologias Utilizadas

  * **Python 3.13+**
  * **Poetry** — gerenciamento de pacotes e ambientes virtuais
  * **LangChain + LangGraph** — orquestracao de prompts, chains e grafo multi-agente
  * **OpenAI GPT-3.5-Turbo** — modelo de linguagem principal
  * **OpenAI text-embedding-3-small** — embeddings para busca semantica
  * **ChromaDB** — banco vetorial para busca semantica na base de conhecimento
  * **MySQL** — banco de dados do GLPI
  * **Requests** — para comunicacao com a API REST do GLPI
  * **python-dotenv** — gerenciamento seguro de variaveis de ambiente

-----

## Instalacao e Configuracao

### 1. Pre-requisitos

  * Python 3.13+
  * Poetry instalado
  * Acesso a um banco GLPI MySQL ativo
  * Acesso a API REST do GLPI (opcional, para sincronizacao da base de conhecimento)
  * Chave de API da OpenAI

-----

### 2. Clonar o Repositorio

```bash
git clone https://github.com/seu-usuario/glpi-sql-ai.git
cd glpi-sql-ai
```

-----

### 3. Instalar as Dependencias

```bash
poetry install
```

-----

### 4. Gerar os Tokens da API do GLPI

Para a integracao com a base de conhecimento, voce precisa de **dois tokens** no GLPI: o **App-Token** (identifica a aplicacao cliente) e o **User-Token** (identifica o usuario).

> **Nota:** O sistema funciona sem a API do GLPI — apenas as consultas SQL e a busca vetorial em cache ja sao suficientes. A API e necessaria apenas se voce quiser sincronizar artigos diretamente do GLPI.

#### 4.1 Criar o App-Token

1. Acesse o GLPI com um perfil de **Super-Admin**
2. Va em **Administracao > Configurar > API**
3. Clique em **Adicionar cliente API**
4. Preencha um nome (ex: `glpi-sql-ai`) e salve
5. Anote o **App-Token** gerado (uma string longa como `Xq7pL2mN9vR4tY8wK3sD6fH1jB5cZ0aE2gU7iO4e`)

![Caminho: Administracao > Configurar > API](img/glpi-api-config.png)

#### 4.2 Criar o User-Token

1. Va em **Administracao > Usuarios**
2. Selecione o usuario que sera usado pela aplicacao
3. Na aba **Tokens da API**, clique em **Adicionar token da API**
4. De um nome ao token (ex: `app-token`)
5. Clique em **Adicionar**
6. Anote o **token** gerado (uma string longa como `Mz3kP8rT1yW6nB4vC9xF2hJ7qL5dS0gA8eU3oI6t`)

> **Importante:** O usuario precisa ter permissao de leitura na base de conhecimento (perfil com acesso a `KnowbaseItem`). Recomenda-se um perfil Super-Admin ou um perfil customizado com essa permissao.

-----

### 5. Configurar o Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Chave da OpenAI
OPENAI_API_KEY="sk-..."

# Credenciais do Banco de Dados
DB_HOST="localhost"
DB_NAME="glpi"
DB_USER="root"
DB_PASSWORD="senha"

# Credenciais da API do GLPI (para sincronizacao da Base de Conhecimento)
GLPI_URL="http://seu-glpi/glpi"
GLPI_APP_TOKEN="seu_app_token_aqui"
GLPI_USER_TOKEN="seu_user_token_aqui"
```

> **Telemetria do ChromaDB:** Para desabilitar os avisos de telemetria, adicione `ANONYMIZED_TELEMETRY=False` ao `.env`.

-----

## Como Usar

Inicie a aplicacao com:

```bash
poetry run python -m glpi_sql_ai.main
```

### Exemplo de Sessao:

```
================================================================================
Ola! Sou seu assistente de banco de dados GLPI.
   Faca uma pergunta sobre os chamados ou digite 'sair' para terminar.
================================================================================
Voce: quantos chamados atrasados existem?
Analisando sua pergunta...
[SQL] Gerando SQL...
[SQL] Executando SQL...
Assistente: Existem atualmente 16 chamados atrasados.

--------------------------------------------------------------------------------
Voce: solucoes para o chamado 10367
Analisando sua pergunta...
[Busca] Buscando detalhes do chamado 10367...
[KB] Buscando informacoes na base de conhecimento...
[Solucoes] Gerando solucoes para o chamado 10367...

Solucoes Sugeridas:
Artigo 1: Renovacao de certificado digital A1/A3
1. Identifique o tipo de certificado: A1 (arquivo) ou A3 (token/cartao).
2. Acesse o site da Autoridade Certificadora com o token conectado.
3. No portal, localize a opcao 'Renovar Certificado' e siga o assistente.
...
--------------------------------------------------------------------------------
Voce: sair
Ate a proxima!
```

-----

## Fluxo da Aplicacao

```
[Usuario faz pergunta]
        |
[Supervisor: classificacao de intencao]
        |
[Supervisor: validacao de escopo]
       / \
      /   \
[SQL Worker]                [Solutions Worker]
     |                             |
 Gera SQL (LLM)              Extrai ID do chamado
     |                       Busca detalhes (MySQL)
 Executa no MySQL            Busca artigos (ChromaDB)
     |                       Gera solucoes (LLM)
 Auto-corrige (ate 3x)            |
     |                       Resposta fiel ao artigo
 Formata resposta                 |
     |                             |
     \____________________________/
                    |
        [Resposta no terminal]
```

### Diferenca do fluxo legado

O fluxo original usava chains isoladas. A versao atual usa **LangGraph** com grafo supervisor e workers com estado proprio:

  * **validacao de escopo**: o no `guard_scope` no grafo supervisor intercepta perguntas alheias ao dominio helpdesk/GLPI antes que cheguem aos workers, exibindo uma recusa educada
  * **auto-correcao de SQL**: loop interno no `sql_worker` que detecta erro, envia para o LLM corrigir e re-executa (ate 3 tentativas)
  * **busca vetorial**: substituiu o keyword scoring por embeddings OpenAI + ChromaDB, com resultados muito mais precisos
  * **fidelidade ao artigo**: o prompt de solucoes foi reformulado para reproduzir fielmente o conteudo dos artigos, sem inventar informacoes
  * **tratamento robusto de erros**: tickets inexistentes ou sem ID retornam mensagens de erro claras, sem quebrar o fluxo

-----

## Ambiente de Teste (Seed)

O projeto inclui um script que popula o banco com dados de teste:

```bash
poetry run python scripts/seed_test_data.py
```

Isso cria:
  * **7 chamados** com status variados (novo, em atendimento, pendente, solucionado, fechado), incluindo chamados atrasados
  * **6 artigos** na base de conhecimento (`glpi_knowbaseitems`) sobre temas como: computador lento, reset de senha, impressora de rede, e-mail Outlook, VPN e certificado digital
  * **Indexacao vetorial** automatica no ChromaDB

Com o seed ativo, voce pode testar perguntas como:
  * `quantos chamados atrasados existem?`
  * `solucoes para o chamado 10367`
  * `chamados do tecnico Yan Silva`

-----

## Exemplos de Perguntas

| Tipo | Exemplo |
| ---- | ------- |
| Consultas | "Quantos chamados estao abertos?" |
| Ranking | "Top 5 tecnicos com mais chamados solucionados" |
| Atrasos | "Quantos chamados atrasados existem este mes?" |
| Tecnicos | "Chamados do tecnico Yan Silva" |
| Solucoes | "Solucoes para o chamado 10367" |

-----

## Como Contribuir

1.  Faca um fork do projeto
2.  Crie uma branch para sua feature:
    ```bash
    git checkout -b feature/nova-funcionalidade
    ```
3.  Faca o commit das mudancas:
    ```bash
    git commit -m "feat: adiciona nova funcionalidade"
    ```
4.  Envie o PR

-----

## Licenca

Distribuido sob a licenca **MIT**.
Sinta-se livre para usar, modificar e contribuir!

-----
