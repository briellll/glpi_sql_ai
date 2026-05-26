"""
Módulo de configuração da aplicação.
Gerencia variáveis de ambiente, conexão com banco de dados e inicialização do LLM.
Todas as inicializações são explícitas — sem side effects em tempo de importação.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from sqlalchemy import text
from sqlalchemy.pool import NullPool

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
        self._sync_info_path: Path = (
            Path(__file__).parent.parent.parent / "chroma_db" / ".sync_info.json"
        )

    # ------------------------------------------------------------------
    # Controle de sincronizacao da base de conhecimento (evita API GLPI)
    # ------------------------------------------------------------------

    def _read_sync_info(self) -> dict:
        try:
            return json.loads(self._sync_info_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_sync_info(self, info: dict) -> None:
        self._sync_info_path.parent.mkdir(parents=True, exist_ok=True)
        self._sync_info_path.write_text(json.dumps(info), encoding="utf-8")

    def _check_kb_freshness(self) -> bool:
        """Verifica via MySQL se artigos da KB mudaram desde o ultimo sync.

        Retorna True se o cache vetorial esta atualizado (nao precisa chamar API GLPI).
        Retorna False se nunca sincronizou, artigos mudaram, ou houve erro na verificacao.
        """
        if not self._db:
            return False

        try:
            with self._db._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) AS cnt, MAX(date_mod) AS max_mod "
                        "FROM glpi_knowbaseitems"
                    )
                ).fetchone()
                db_count: int = int(row[0] or 0)
                db_max_mod: Optional[str] = str(row[1]) if row[1] else None
        except Exception:
            return False

        if db_count == 0:
            return True

        sync = self._read_sync_info()
        cached_count: int = sync.get("article_count", 0)
        cached_max_mod: Optional[str] = sync.get("last_max_date_mod")

        if cached_count == 0 or cached_max_mod is None:
            return False

        if db_count == cached_count and db_max_mod == cached_max_mod:
            return True

        return False

    def _save_kb_sync_info(self) -> None:
        """Grava metadados do sync atual apos sincronizacao bem-sucedida com a API GLPI."""
        if not self._db:
            return
        try:
            with self._db._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) AS cnt, MAX(date_mod) AS max_mod "
                        "FROM glpi_knowbaseitems"
                    )
                ).fetchone()
            self._write_sync_info({
                "article_count": int(row[0] or 0),
                "last_max_date_mod": str(row[1]) if row[1] else None,
            })
        except Exception:
            pass

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
        self._db = SQLDatabase.from_uri(
            db_uri,
            engine_args={
                "poolclass": NullPool,
                "connect_args": {
                    "connection_timeout": 10,
                },
            },
        )
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
                    "   O sistema funcionará apenas com seu conhecimento proprio."
                )
            return

        # Check de frescor via MySQL: se o cache vetorial ja tem os mesmos
        # artigos que estao no banco, pula a API GLPI inteira.
        if self._vector_store and self._vector_store.is_populated:
            if self._check_kb_freshness():
                logger.info(
                    "[KB] Cache vetorial atualizado. "
                    "Nenhuma chamada a API GLPI necessaria."
                )
                return

        try:
            self._kb = GLPIKnowledgeBase(glpi_url, glpi_token, glpi_app_token)

            if self._kb.all_articles and self._vector_store:
                if self._vector_store.is_populated:
                    logger.info(
                        "[KB] Artigos modificados detectados. Re-sincronizando..."
                    )
                self._vector_store.sync_from_glpi(self._kb)
                self._save_kb_sync_info()
                logger.info("[KB] Base de conhecimento indexada com sucesso.")
            elif self._kb.all_articles:
                logger.info(
                    "[KB] Artigos carregados "
                    "(busca por palavras-chave como fallback)."
                )
            elif self._vector_store and self._vector_store.is_populated:
                logger.info("[KB] Nenhum artigo novo. Mantendo cache vetorial.")
            else:
                logger.info("[KB] Nenhum artigo encontrado na base de conhecimento.")
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
                    "   O sistema funcionara apenas com seu conhecimento proprio."
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
