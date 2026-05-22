"""
Módulo de busca vetorial para a base de conhecimento do GLPI.
Utiliza ChromaDB + OpenAI Embeddings para busca semântica em artigos da KB.
"""

import logging
import os
from typing import Optional

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# Suprime avisos de telemetria do ChromaDB (bug no PostHog interno)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class KBVectorStore:
    """
    Vector store para artigos da base de conhecimento do GLPI.
    Substitui o keyword scoring por busca semântica com embeddings.
    """

    def __init__(
        self,
        api_key: str,
        persist_dir: str = None,
        collection_name: str = "glpi_kb_articles",
    ):
        if persist_dir is None:
            persist_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "..", "chroma_db"
            )

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key,
        )
        self.persist_dir = os.path.abspath(persist_dir)
        self.collection_name = collection_name
        self._vector_store: Optional[Chroma] = None

    def _get_or_create(self) -> Chroma:
        if self._vector_store is not None:
            return self._vector_store
        self._vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
        )
        return self._vector_store

    @property
    def is_populated(self) -> bool:
        """Verifica se há documentos indexados."""
        try:
            vs = self._get_or_create()
            return len(vs.get(limit=1)["ids"]) > 0
        except Exception:
            return False

    def index_articles(self, articles: list[dict]) -> int:
        """
        Indexa artigos no vector store.

        Args:
            articles: Lista de dicionários com id, name, answer

        Returns:
            Número de artigos indexados
        """
        documents = []
        ids = []

        for article in articles:
            article_id = article.get("id")
            title = article.get("name", "")
            content = article.get("answer", "")

            if not title and not content:
                continue

            text = f"{title}\n\n{content}"
            documents.append(
                Document(
                    page_content=text,
                    metadata={"id": str(article_id), "title": title},
                )
            )
            ids.append(str(article_id))

        if not documents:
            return 0

        vs = self._get_or_create()

        existing = vs.get(limit=1)["ids"]
        if existing:
            logger.info("Substituindo índice existente...")
            vs.delete_collection()
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_dir,
            )
            vs = self._vector_store

        vs.add_documents(documents, ids=ids)
        logger.info("Indexados %d artigos na base vetorial.", len(documents))
        return len(documents)

    def search(self, query: str, k: int = 3) -> list[dict]:
        """
        Busca artigos relevantes por similaridade semântica.

        Args:
            query: Texto de busca
            k: Número máximo de resultados

        Returns:
            Lista de dicionários com title, content, score
        """
        vs = self._get_or_create()

        if not self.is_populated:
            return []

        results = vs.similarity_search_with_score(query, k=k)
        articles = []
        for doc, score in results:
            articles.append({
                "title": doc.metadata.get("title", ""),
                "content": doc.page_content,
                "score": float(score),
            })
        return articles

    def sync_from_glpi(self, kb_client) -> bool:
        """
        Sincroniza artigos da API GLPI para o vector store.

        Args:
            kb_client: Instância de GLPIKnowledgeBase já conectada

        Returns:
            True se sincronizou com sucesso
        """
        try:
            if not kb_client.all_articles:
                logger.info(
                    "Nenhum artigo para sincronizar (KB vazia ou não conectada)."
                )
                return False
            self.index_articles(kb_client.all_articles)
            return True
        except Exception as e:
            logger.error("Erro ao sincronizar artigos: %s", e)
            return False
