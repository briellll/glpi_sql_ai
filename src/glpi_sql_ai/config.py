"""
Módulo de configuração da aplicação.
Gerencia variáveis de ambiente, conexão com banco de dados e inicialização do LLM.
Todas as inicializações são explícitas — sem side effects em tempo de importação.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from .knowledge_base import GLPIKnowledgeBase
from .vector_store import KBVectorStore

logger = logging.getLogger(__name__)


class AppContext:
    """Contexto da aplicação com todas as dependências gerenciadas."""

    def __init__(self):
        load_dotenv()
        self._db: Optional[SQLDatabase] = None
        self._llm_sql: Optional[ChatOpenAI] = None
        self._llm_creative: Optional[ChatOpenAI] = None
        self._kb: Optional[GLPIKnowledgeBase] = None
        self._vector_store: Optional[KBVectorStore] = None
        self._initialized = False

    def initialize(self):
        """Inicializa todas as conexões explicitamente."""
        logger.info("Inicializando a aplicacao...")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")

        self._init_database()
        self._init_llm(api_key)
        self._init_vector_store(api_key)
        self._init_knowledge_base()
        self._initialized = True

    def _init_database(self):
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")

        logger.info("[DB] Conectando ao banco de dados...")
        db_uri = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}"
        self._db = SQLDatabase.from_uri(db_uri)
        logger.info("[DB] Banco de dados conectado com sucesso.")

    def _init_llm(self, api_key: str):
        logger.info("[LLM] Inicializando o modelo de linguagem...")
        self._llm_sql = ChatOpenAI(
            model="gpt-3.5-turbo", temperature=0, api_key=api_key
        )
        self._llm_creative = ChatOpenAI(
            model="gpt-3.5-turbo", temperature=0.3, api_key=api_key
        )
        logger.info("[LLM] Modelo de linguagem inicializado.")

    def _init_vector_store(self, api_key: str):
        logger.info("[KB] Inicializando base de conhecimento vetorial...")
        try:
            self._vector_store = KBVectorStore(api_key=api_key)
        except Exception as e:
            logger.warning(
                "[AVISO] Nao foi possivel inicializar a base vetorial: %s", e
            )

    def _init_knowledge_base(self):
        glpi_url = os.getenv("GLPI_URL")
        glpi_token = os.getenv("GLPI_USER_TOKEN")
        glpi_app_token = os.getenv("GLPI_APP_TOKEN", "")

        if not glpi_url or not glpi_token:
            if self._vector_store and self._vector_store.is_populated:
                logger.info(
                    "[KB] Usando dados em cache da base vetorial "
                    "(GLPI não configurado)."
                )
            else:
                logger.warning(
                    "[AVISO] GLPI_URL ou GLPI_USER_TOKEN nao configurados no .env"
                )
                logger.warning(
                    "   O sistema funcionará apenas com seu conhecimento próprio."
                )
            return

        try:
            self._kb = GLPIKnowledgeBase(glpi_url, glpi_token, glpi_app_token)

            if (
                self._kb.all_articles
                and self._vector_store
                and not self._vector_store.is_populated
            ):
                self._vector_store.sync_from_glpi(self._kb)
                logger.info("[KB] Base de conhecimento indexada com sucesso.")
            else:
                if self._vector_store and self._vector_store.is_populated:
                    logger.info("[KB] Base de conhecimento vetorial ja possui dados em cache.")
                elif self._kb.all_articles:
                    logger.info("[KB] Artigos carregados (busca por palavras-chave como fallback).")
        except Exception as e:
            logger.warning(
                "[AVISO] Nao foi possivel conectar a base de conhecimento: %s", e
            )
            if self._vector_store and self._vector_store.is_populated:
                logger.info(
                    "   Usando dados em cache da base vetorial."
                )
            else:
                logger.warning(
                    "   O sistema funcionará apenas com seu conhecimento próprio."
                )

    @property
    def db(self) -> SQLDatabase:
        if not self._db:
            raise RuntimeError("AppContext não inicializado. Chame initialize() primeiro.")
        return self._db

    @property
    def llm_sql(self) -> ChatOpenAI:
        if not self._llm_sql:
            raise RuntimeError("AppContext não inicializado. Chame initialize() primeiro.")
        return self._llm_sql

    @property
    def llm_creative(self) -> ChatOpenAI:
        if not self._llm_creative:
            raise RuntimeError("AppContext não inicializado. Chame initialize() primeiro.")
        return self._llm_creative

    @property
    def kb(self) -> Optional[GLPIKnowledgeBase]:
        return self._kb

    @property
    def vector_store(self) -> Optional[KBVectorStore]:
        return self._vector_store
