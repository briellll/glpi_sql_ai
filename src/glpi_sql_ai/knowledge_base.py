"""
Módulo responsável por buscar e processar artigos da base de conhecimento do GLPI.
Oferece funções para recuperar informações relevantes de documentos, PDFs e textos.
"""

import re
from typing import Optional
import requests
from html import unescape

class GLPIKnowledgeBase:
    """Gerencia acesso à base de conhecimento do GLPI via API REST."""

    def __init__(self, glpi_url: str, user_token: str):
        """
        Inicializa a conexão com a API do GLPI.

        Args:
            glpi_url: URL base do GLPI (ex: "http://localhost/glpi")
            user_token: Token de usuário do GLPI (obtido em Setup > Users > User Token)
        """
        self.glpi_url = glpi_url.rstrip("/")
        self.user_token = user_token
        self.headers = {
            "Content-Type": "application/json",
        }
        self.session_token = None
        self.all_articles = []
        self._init_session()

    def _init_session(self) -> bool:
        """
        Inicializa uma sessão com a API do GLPI usando user_token.

        Returns:
            True se a sessão foi inicializada com sucesso, False caso contrário.
        """
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
            print(f"⚠️  Aviso: Erro de conexão com a API do GLPI: {e}")
        except Exception as e:
            print(f"⚠️  Aviso: Uma falha inesperada ocorreu ao iniciar a sessão do GLPI: {e}")

        return False

    def _load_all_articles(self) -> bool:
        """
        Carrega todos os artigos da KB na memória para busca local.

        Returns:
            True se conseguiu carregar, False caso contrário.
        """
        if not self.session_token:
            return False

        try:
            url = f"{self.glpi_url}/apirest.php/KnowbaseItem"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                self.all_articles = response.json()
                print(f"✅ {len(self.all_articles)} artigos da Base de Conhecimento carregados.")
                return True
        except Exception as e:
            print(f"⚠️  Aviso: Não foi possível carregar os artigos da Base de Conhecimento: {e}")

        return False

    def search_articles(self, query: str, limit: int = 5) -> list[dict]:
        """
        Busca artigos na base de conhecimento por palavras-chave (busca local).

        Args:
            query: Termo de busca.
            limit: Número máximo de resultados (padrão: 5).

        Returns:
            Lista de dicionários com artigos encontrados.
        """
        if not self.all_articles or not query:
            return []

        query_lower = query.lower()
        results = []

        for article in self.all_articles:
            name = article.get("name", "").lower()
            answer = article.get("answer", "").lower()

            if query_lower in name or query_lower in answer:
                results.append(article)
                if len(results) >= limit:
                    break

        return results

    def get_article_content(self, article_id: int) -> Optional[dict]:
        """
        Recupera o conteúdo completo de um artigo pelo ID.

        Args:
            article_id: ID do artigo da base de conhecimento.

        Returns:
            Dicionário com detalhes do artigo ou None se não encontrado.
        """
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
        """
        Encerra a sessão com a API do GLPI.

        Returns:
            True se encerrada com sucesso, False caso contrário.
        """
        if not self.session_token:
            return False

        try:
            url = f"{self.glpi_url}/apirest.php/killSession"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️  Erro ao encerrar sessão com o GLPI: {e}")

        return False


def get_knowledge_base_context(
    kb: GLPIKnowledgeBase, category: str, problem_description: str
) -> str:
    """
    Busca contexto da base de conhecimento baseado na categoria e descrição.
    (LÓGICA DE BUSCA CORRIGIDA E RESTAURADA)

    Args:
        kb: Instância de GLPIKnowledgeBase.
        category: Categoria do chamado.
        problem_description: Descrição do problema.

    Returns:
        String com conteúdo relevante da KB ou um aviso padrão se nada for encontrado.
    """
    # Restaurando a lógica de busca original e mais eficaz
    search_terms = [
        problem_description[:60],  # Aumentei um pouco para mais contexto
        category,
        problem_description.split()[0] if problem_description else "",
    ]

    results = []
    processed_ids = set()

    for term in search_terms:
        if term and len(term) > 2:
            articles = kb.search_articles(term, limit=3)
            for article in articles:
                article_id = article.get("id")
                if article_id and article_id not in processed_ids:
                    article_detail = kb.get_article_content(article_id)
                    if article_detail:
                        answer = article_detail.get("answer", "")
                        clean_content = re.sub(r'<[^>]+>', '', answer)
                        clean_content = re.sub(r'\s+', ' ', clean_content).strip()

                        results.append({
                            "title": article_detail.get("name", "Sem Título"),
                            "content": clean_content,
                        })
                        processed_ids.add(article_id)

    if not results:
        return "NÃO_ENCONTRADO"

    # Formata o contexto para ser enviado ao LLM
    kb_context = "## Informações da Base de Conhecimento do GLPI:\n\n"
    for i, item in enumerate(results[:3], 1):  # Limita a 3 artigos
        kb_context += f"**Artigo {i}:** {item['title']}\n"
        content_preview = item['content'][:500]
        kb_context += f"{content_preview}...\n\n"

    return kb_context