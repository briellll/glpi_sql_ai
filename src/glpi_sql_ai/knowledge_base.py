"""
Módulo responsável por buscar e processar artigos da base de conhecimento do GLPI.
Oferece funções para recuperar informações relevantes de documentos, PDFs e textos.
"""

import logging
import re
from html import unescape
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class GLPIKnowledgeBase:
    """Gerencia acesso à base de conhecimento do GLPI via API REST."""

    def __init__(self, glpi_url: str, user_token: str):
        self.glpi_url = glpi_url.rstrip("/")
        self.user_token = user_token
        self.headers = {"Content-Type": "application/json"}
        self.session_token = None
        self.all_articles = []
        self._init_session()

    def _init_session(self) -> bool:
        try:
            url = f"{self.glpi_url}/apirest.php/initSession"
            params = {"user_token": self.user_token}
            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                if self.session_token:
                    self.headers["Session-Token"] = self.session_token
                    self._load_all_articles()
                    return True
        except requests.exceptions.RequestException as e:
            logger.warning("Erro de conexão com a API do GLPI: %s", e)
        except Exception as e:
            logger.warning("Falha inesperada ao iniciar sessão do GLPI: %s", e)

        return False

    def _load_all_articles(self) -> bool:
        if not self.session_token:
            return False

        try:
            url = f"{self.glpi_url}/apirest.php/KnowbaseItem"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                self.all_articles = response.json()
                logger.info(
                    "%d artigos da Base de Conhecimento carregados.",
                    len(self.all_articles),
                )
                return True
        except Exception as e:
            logger.warning(
                "Não foi possível carregar artigos da Base de Conhecimento: %s", e
            )

        return False

    def search_articles(self, query: str, limit: int = 5) -> list[dict]:
        if not self.all_articles or not query:
            return []

        ignore_words = {"sem", "com", "para", "de", "do", "da", "me",
                        "ajuda", "erro", "ao", "na", "no"}
        tokens = [
            w.lower()
            for w in query.split()
            if len(w) > 2 and w.lower() not in ignore_words
        ]

        if not tokens:
            return []

        scored_results = []

        for article in self.all_articles:
            name = article.get("name", "").lower()
            answer = article.get("answer", "").lower()

            score = 0
            for word in tokens:
                if word in name:
                    score += 3
                if word in answer:
                    score += 1

            if score > 0:
                scored_results.append({"article": article, "score": score})

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return [item["article"] for item in scored_results[:limit]]

    def get_article_content(self, article_id: int) -> Optional[dict]:
        if not self.session_token:
            return None

        try:
            url = f"{self.glpi_url}/apirest.php/KnowbaseItem/{article_id}"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                article = response.json()
                if "answer" in article and article["answer"]:
                    article["answer"] = unescape(article["answer"])
                if "name" in article and article["name"]:
                    article["name"] = unescape(article["name"])
                return article
        except Exception:
            pass

        return None

    def close_session(self) -> bool:
        if not self.session_token:
            return False

        try:
            url = f"{self.glpi_url}/apirest.php/killSession"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning("Erro ao encerrar sessão com o GLPI: %s", e)

        return False


def get_knowledge_base_context(vector_store, title, category, description) -> str:
    """
    Busca artigos relevantes na base de conhecimento usando busca semântica.

    Args:
        vector_store: Instância de KBVectorStore
        title: Título do chamado
        category: Categoria do chamado
        description: Descrição do chamado

    Returns:
        Contexto formatado ou "NÃO_ENCONTRADO"
    """
    if not vector_store or not vector_store.is_populated:
        return "NÃO_ENCONTRADO"

    query = f"{title} {category} {description[:100]}"
    results = vector_store.search(query, k=3)

    if not results:
        return "NÃO_ENCONTRADO"

    context = "## Informações da Base de Conhecimento do GLPI:\n\n"
    for i, item in enumerate(results, 1):
        clean_content = re.sub(r"<[^>]+>", "", item["content"])
        context += (
            f"**Artigo {i}:** {item['title']}\n{clean_content[:1500]}...\n\n"
        )
    return context
