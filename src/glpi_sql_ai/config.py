"""
Módulo de configuração da aplicação.
Gerencia variáveis de ambiente, conexão com banco de dados e inicialização do LLM.
"""

import os
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from .knowledge_base import GLPIKnowledgeBase


load_dotenv()


# ========== CONFIGURAÇÕES DE BANCO DE DADOS ==========
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")


# ========== CONFIGURAÇÕES DE GLPI API ==========
GLPI_URL = os.getenv("GLPI_URL")
GLPI_USER_TOKEN = os.getenv("GLPI_USER_TOKEN")


# ========== INICIALIZAÇÃO DO BANCO DE DADOS ==========
print("🔌 Conectando ao banco de dados...")
db_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
db = SQLDatabase.from_uri(db_uri)


# ========== INICIALIZAÇÃO DO MODELO DE LINGUAGEM ==========
print("🤖 Inicializando o modelo de linguagem...")
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, api_key=API_KEY)  # type: ignore


# ========== INICIALIZAÇÃO DA BASE DE CONHECIMENTO ==========
print("📚 Conectando à base de conhecimento do GLPI...")
kb = None
if GLPI_URL and GLPI_USER_TOKEN:
    try:
        kb = GLPIKnowledgeBase(GLPI_URL, GLPI_USER_TOKEN)
        print("✅ Base de conhecimento conectada com sucesso!")
    except Exception as e:
        print(f"⚠️  Aviso: Não foi possível conectar à base de conhecimento: {e}")
        print("   O sistema funcionará apenas com seu conhecimento próprio.")
else:
    print("⚠️  Aviso: GLPI_URL ou GLPI_API_TOKEN não configurados no .env")
    print("   O sistema funcionará apenas com seu conhecimento próprio.")