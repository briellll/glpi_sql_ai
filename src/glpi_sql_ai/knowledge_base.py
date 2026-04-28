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

    # No arquivo knowledge_base.py

    def search_articles(self, query: str, limit: int = 5) -> list[dict]:
        if not self.all_articles or not query:
            return []

        # 1. Filtro rigoroso de palavras irrelevantes
        ignore_words = {"sem", "com", "para", "de", "do", "da", "me", "ajuda", "erro", "ao", "na", "no"}
        tokens = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in ignore_words]

        if not tokens:
            return []

        scored_results = []

        # 2. Avaliação de Relevância (Scoring)
        for article in self.all_articles:
            name = article.get("name", "").lower()
            answer = article.get("answer", "").lower()

            score = 0
            for word in tokens:
                if word in name:
                    score += 3  # Peso Ouro: Se a palavra está no Título, vale 3 pontos!
                if word in answer:
                    score += 1  # Peso Prata: Se está no corpo do texto, vale 1 ponto.

            # 3. Se o artigo pontuou, entra para a lista de candidatos
            if score > 0:
                scored_results.append({
                    "article": article,
                    "score": score
                })

        # 4. O Pulo do Gato: Ordena a lista do maior Score para o menor (Ranking)
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # 5. Retorna apenas os 'limit' melhores artigos para a IA ler
        return [item["article"] for item in scored_results[:limit]]

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


def get_knowledge_base_context(kb, title, category, description) -> str:
    # Agora buscamos pelo TÍTULO e pela DESCRIÇÃO separadamente para aumentar o Recall
    search_terms = [title, description[:60]]

    results = []
    processed_ids = set()

    for term in search_terms:
        articles = kb.search_articles(term)
        for art in articles:
            if art['id'] not in processed_ids:
                detail = kb.get_article_content(art['id'])
                if detail:
                    results.append({"title": detail['name'], "content": detail['answer']})
                    processed_ids.add(art['id'])

    if not results: return "NÃO_ENCONTRADO"

    context = "## Informações da Base de Conhecimento do GLPI:\n\n"
    for i, item in enumerate(results[:3], 1):
        clean_content = re.sub(r'<[^>]+>', '', item['content']) # Limpa HTML
        context += f"**Artigo {i}:** {item['title']}\n{clean_content[:500]}...\n\n"
    return context