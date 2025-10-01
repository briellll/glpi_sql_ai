# 🤖 GLPI SQL AI

Um assistente de IA que utiliza LangChain e modelos de linguagem da OpenAI para traduzir perguntas em linguagem natural para consultas SQL e interagir com um banco de dados GLPI.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.1.0-F54D00?style=for-the-badge)
![Poetry](https://img.shields.io/badge/Poetry-1.5+-60A5FA?style=for-the-badge&logo=poetry&logoColor=white)

## 📜 Tabela de Conteúdos

- [Funcionalidades](#-funcionalidades)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Configuração e Instalação](#-configuração-e-instalação)
- [Como Usar](#-como-usar)
- [Licença](#-licença)

## ✨ Funcionalidades

- **Consultas em Linguagem Natural:** Pergunte ao bot "quantos chamados atrasados existem?" em vez de escrever SQL.
- **Engenharia de Prompt Robusta:** Utiliza um prompt de sistema detalhado com um "Dicionário de Termos de Negócio" para garantir a precisão das queries geradas.
- **Arquitetura Modular:** O projeto é organizado em módulos com responsabilidades separadas (configuração, prompts, chains), seguindo as convenções de desenvolvimento Python.
- **Integração com GLPI:** Focado e otimizado para a estrutura de banco de dados do sistema de chamados GLPI.

## 📁 Estrutura do Projeto

O projeto utiliza uma estrutura `src` para uma melhor organização do código-fonte, gerenciado com Poetry.

```
glpi-sql-ai/
├── .env
├── pyproject.toml
└── src/
    └── glpi_sql_ai/
        ├── __init__.py
        ├── config.py       # Configurações e conexões
        ├── prompts.py      # Módulo do "cérebro" da IA
        ├── chains.py       # Fábrica das chains do LangChain
        └── main.py         # Ponto de entrada da aplicação
```

## 🛠️ Tecnologias Utilizadas

- **Python 3.11+**
- **Poetry** para gerenciamento de dependências.
- **LangChain** para orquestração dos componentes de IA.
- **OpenAI (GPT-3.5-Turbo)** como modelo de linguagem.
- **MySQL** (Banco de dados GLPI).

## 🚀 Configuração e Instalação

Siga os passos abaixo para configurar e rodar o projeto localmente.

### 1. Pré-requisitos

- Python 3.11 ou superior.
- Poetry instalado.
- Acesso a um banco de dados MySQL do GLPI.

### 2. Clone o Repositório

```bash
git clone [https://github.com/seu-usuario/glpi-sql-ai.git](https://github.com/seu-usuario/glpi-sql-ai.git)
cd glpi-sql-ai
```

### 3. Instale as Dependências

O Poetry cuidará de criar o ambiente virtual e instalar todos os pacotes necessários.

```bash
poetry install
```

### 4. Configure o Ambiente

Crie um arquivo chamado `.env` na raiz do projeto, copiando o exemplo abaixo e preenchendo com suas informações.

**Arquivo `.env`:**
```env
# Chave da API da OpenAI
OPENAI_API_KEY="sk-..."

# Configurações do Banco de Dados GLPI
DB_HOST=""
DB_NAME=""
DB_USER=""
DB_PASSWORD=""
```

## ▶️ Como Usar

Para executar a aplicação, utilize o comando abaixo a partir da pasta raiz do projeto. O Poetry garantirá que o ambiente virtual correto seja utilizado.

```bash
poetry run python -m glpi_sql_ai.main
```

O script irá executar as perguntas pré-definidas no arquivo `main.py` e imprimir os resultados no terminal.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.