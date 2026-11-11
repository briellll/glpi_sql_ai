# GLPI SQL AI

Assistente conversacional de terminal que integra modelos de linguagem (LLMs) ao [GLPI](https://glpi-project.org/). Ele responde perguntas em linguagem natural sobre os chamados, consultando o banco de dados do GLPI, e sugere soluções para um chamado com base nos artigos da base de conhecimento, por meio de RAG (*Retrieval-Augmented Generation*).

Projeto desenvolvido como Trabalho de Conclusão de Curso do Bacharelado em Sistemas de Informação da Universidade Federal do Oeste do Pará (UFOPA).

> **Protótipo acadêmico.** Foi desenvolvido e avaliado sobre uma instância local do GLPI com dados sintéticos. Leia a seção [Limitações e segurança](#limitações-e-segurança) antes de conectá-lo a qualquer banco real.

## Funcionalidades

- **Soluções para um chamado (fluxo principal, RAG).** Para "soluções para o chamado 10367", o sistema busca o chamado no banco, recupera os três artigos mais próximos na base de conhecimento por busca semântica (ChromaDB + embeddings da OpenAI) e gera os passos de solução. O prompt aplica *grounding*: a resposta deve usar apenas o conteúdo dos artigos recuperados e citar o artigo de origem; se nenhum artigo for pertinente, o modelo declara a ausência em vez de inventar.
- **Consultas em linguagem natural (Text-to-SQL).** Para "quantos chamados atrasados existem?", o modelo gera a consulta SQL, que é validada e executada no MySQL do GLPI; em caso de erro, a consulta é corrigida automaticamente (até 3 tentativas) e o resultado é devolvido em linguagem natural.
- **Proteção contra escrita no banco, em duas camadas que não dependem do modelo.** Antes da execução, a consulta é analisada com o [sqlglot](https://github.com/tobymao/sqlglot) e só é aceita se for um único comando de leitura (`SELECT`); comandos de escrita ou de estrutura, múltiplos comandos e `SELECT ... INTO` são recusados. Além disso, o assistente se conecta com um usuário de banco que só tem permissão de `SELECT`.
- **Classificação de intenção.** Um supervisor decide se a pergunta é uma consulta aos dados ou um pedido de soluções.
- **Guardião de escopo.** Perguntas fora do domínio de helpdesk são bloqueadas antes de chegar aos *workers*. O bloqueio é o padrão: a pergunta só passa se o modelo a classificar explicitamente como dentro do escopo.
- **Verificador de frescor da base de conhecimento.** Na inicialização, o sistema compara a contagem de artigos e a data da última modificação no MySQL com os metadados da última sincronização. Se nada mudou, usa o índice vetorial já gravado e não chama a API do GLPI.
- **Memória conversacional** dos turnos recentes.

## Arquitetura

O fluxo é orquestrado com LangGraph: um grafo supervisor e dois *workers* com estado próprio.

```
[Pergunta do usuário]
        |
[Supervisor: classificação de intenção]
        |
[Supervisor: guardião de escopo] --(fora do escopo)--> [Recusa educada]
       / \
      /   \
[sql_worker]                 [solutions_worker]
 Gera SQL (LLM)               Extrai o ID do chamado
 Executa no MySQL             Busca o chamado (MySQL)
 Autocorreção (até 3x)        Busca 3 artigos (ChromaDB)
 Formata a resposta           Gera a solução com grounding (LLM)
      \                           /
       \_________________________/
                   |
         [Resposta no terminal]
```

Modelo de linguagem: DeepSeek V4 Flash, pela API compatível com a da OpenAI. Se `DEEPSEEK_API_KEY` não estiver configurada, o sistema usa o `gpt-3.5-turbo` da OpenAI. São usadas duas instâncias: temperatura 0 para classificação, escopo, SQL e formatação, e 0,3 para a geração de soluções.

## Estrutura do projeto

```
glpi_sql_ai/
├── pyproject.toml / poetry.lock    # Dependências (Poetry)
├── src/glpi_sql_ai/
│   ├── main.py                     # Loop do chat no terminal
│   ├── config.py                   # AppContext: banco (NullPool + timeout), LLMs, índice vetorial, verificador de frescor
│   ├── agents/
│   │   ├── supervisor.py           # Grafo supervisor: intenção, guardião de escopo e roteamento
│   │   ├── sql_worker.py           # Text-to-SQL com autocorreção
│   │   └── solutions_worker.py     # Fluxo RAG de soluções
│   ├── chains.py                   # Cadeias LangChain e execução validada do SQL (validate_read_only)
│   ├── prompts.py                  # Prompts, dicionário de negócio e regras de grounding
│   ├── vector_store.py             # ChromaDB + text-embedding-3-small
│   ├── knowledge_base.py           # API REST do GLPI e montagem do contexto RAG
│   ├── tools/db_tools.py           # Acesso ao banco
│   ├── memory.py                   # Memória conversacional
│   ├── console.py                  # Saída colorida no terminal
│   └── services.py                 # Utilitários
├── scripts/
│   ├── rebuild_synthetic_data.py   # Recria o ambiente de teste sintético (APAGA dados reais)
│   ├── reload_kb.py                # Recarrega só a base de conhecimento (30 artigos)
│   ├── seed_test_data.py           # Seed básico, sem limpar a base
│   ├── avaliar_rag.py              # Avaliação: recuperação e geração de soluções, com tempos
│   ├── avaliar_parafrases_fluxo.py # Avaliação: fluxo completo com 12 paráfrases × 3 execuções
│   └── resultados/                 # Saídas das avaliações
└── tests/
    └── test_validate_read_only.py  # Testes do validador de SQL
```

## Instalação

Pré-requisitos: Python 3.13+, [Poetry](https://python-poetry.org/), um GLPI com banco MySQL/MariaDB acessível e uma chave da API da OpenAI (usada nos embeddings). A chave do DeepSeek é opcional.

```bash
git clone https://github.com/briellll/glpi_sql_ai.git
cd glpi_sql_ai
poetry install
```

Crie no banco um usuário somente leitura para o assistente (troque a senha). A permissão vale só para as tabelas que o assistente consulta e, na tabela de usuários, só para as colunas de nome, de modo que senhas, tokens de API e configurações do GLPI ficam fora do alcance das consultas geradas:

```sql
CREATE USER 'glpi_ai_leitura'@'localhost' IDENTIFIED BY 'uma_senha_forte';
GRANT SELECT ON glpidb.glpi_tickets        TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_tickets_users  TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_entities       TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_locations      TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_itilcategories TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_groups         TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_groups_tickets TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT ON glpidb.glpi_knowbaseitems  TO 'glpi_ai_leitura'@'localhost';
GRANT SELECT (id, name, firstname, realname) ON glpidb.glpi_users TO 'glpi_ai_leitura'@'localhost';
```

Crie um arquivo `.env` na raiz do projeto (ele já está no `.gitignore`):

```env
# OpenAI: embeddings (obrigatória) e LLM de reserva se o DeepSeek não for configurado
OPENAI_API_KEY="sua_chave_openai"

# DeepSeek: LLM principal (opcional)
DEEPSEEK_API_KEY="sua_chave_deepseek"

# Banco do GLPI: usuário somente leitura, usado pelo assistente
DB_HOST="localhost"
DB_NAME="glpidb"
DB_USER="glpi_ai_leitura"
DB_PASSWORD="uma_senha_forte"

# Usuário administrador, usado apenas pelos scripts que montam o ambiente de teste
DB_ADMIN_USER="root"
DB_ADMIN_PASSWORD=""

# API REST do GLPI (opcional; usada para sincronizar a base de conhecimento)
GLPI_URL="http://seu-glpi/glpi"
GLPI_APP_TOKEN="seu_app_token"
GLPI_USER_TOKEN="seu_user_token"

# Opcional: desliga a telemetria do ChromaDB
ANONYMIZED_TELEMETRY=False
```

Sem a API do GLPI, o sistema funciona com o índice vetorial já gravado. Para usá-la, gere o App-Token em **Configurar > Geral > API** (adicionando um cliente de API) e o User-Token nas configurações do usuário (chave de acesso remoto). O usuário precisa de permissão de leitura na base de conhecimento.

## Uso

```bash
poetry run python -m glpi_sql_ai.main
```

Digite a pergunta e pressione Enter; para encerrar, digite `sair`. Exemplos:

| Tipo | Pergunta |
| --- | --- |
| Soluções (RAG) | "soluções para o chamado 10367" |
| Contagem | "quantos chamados atrasados existem?" |
| Por técnico | "chamados do técnico Ana Pereira" |
| Ranking | "top 5 técnicos com mais chamados solucionados" |
| Fora do escopo | "quantas peças tem um carro?" (é recusada) |

## Ambiente de teste sintético

> **Atenção:** `rebuild_synthetic_data.py` **apaga todos os chamados e artigos** do banco configurado e anonimiza usuários, setores e categorias. Use somente em uma cópia de teste do GLPI, nunca em produção.

```bash
poetry run python scripts/rebuild_synthetic_data.py   # 40 chamados (16 atrasados) + 30 artigos, e reindexa o ChromaDB
```

Para trocar apenas os artigos da base de conhecimento, sem mexer nos chamados: `poetry run python scripts/reload_kb.py`. A reindexação gera embeddings e por isso exige `OPENAI_API_KEY`. Esses scripts escrevem no banco e por isso usam o usuário administrador (`DB_ADMIN_USER`); sem ele, recorrem a `DB_USER`.

## Avaliação

Os scripts de avaliação reproduzem os testes do trabalho sobre o ambiente sintético e gravam as saídas em `scripts/resultados/`:

```bash
poetry run python scripts/avaliar_rag.py               # recuperação (top-1 e similaridade) e soluções por chamado, com tempo por etapa
poetry run python scripts/avaliar_parafrases_fluxo.py  # fluxo completo das 12 paráfrases, 3 execuções cada
```

Resultados na base de 30 artigos:

- **Consultas diretas:** artigo esperado em 1º lugar em 7 de 7.
- **Paráfrases sem as palavras do título:** esperado em 1º lugar em 6 de 12 e entre os três enviados ao modelo em 10 de 12; na resposta final, o artigo esperado apareceu em 9 de 12.
- **Fidelidade:** nenhum passo inventado nas respostas avaliadas; quando o artigo certo não foi recuperado, o sistema recusou ou usou um artigo parcialmente pertinente.
- **Tempo:** mediana de cerca de 7 segundos por diagnóstico (consulta ao banco, busca e geração).

A ordenação da busca é sensível a artigos de tema vizinho. Técnicas como reordenação (*re-ranking*) e busca híbrida são caminhos naturais de melhoria.

Os testes automatizados do validador de SQL rodam com:

```bash
poetry run python -m pytest tests -q
```

## Limitações e segurança

- **Conecte o assistente sempre com um usuário de banco somente leitura** (veja Instalação). O validador recusa comandos de escrita antes da execução, mas a permissão do banco é a barreira que não depende de código; as duas camadas juntas impedem alterações nos dados. A leitura continua permitida: uma pergunta pode trazer qualquer dado do banco do GLPI que o usuário configurado consiga ler.
- **O dicionário de negócio em `prompts.py` é específico da instância usada no trabalho:** por exemplo, filtra `entities_id = 1` e inverte os códigos de status 3 e 4 em relação ao GLPI oficial. Ajuste essas regras antes de usar em outra instância.
- Cada consulta abre uma conexão nova (`NullPool`), escolha que estabilizou o MariaDB do ambiente de teste, mas acrescenta cerca de 2 segundos por consulta.
- A avaliação usou uma base sintética pequena (40 chamados e 30 artigos), sem usuários reais.

## Tecnologias

Python 3.13 · LangChain · LangGraph · ChromaDB · OpenAI `text-embedding-3-small` · DeepSeek V4 Flash · MySQL/MariaDB · SQLAlchemy · sqlglot · pytest · Poetry

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).
