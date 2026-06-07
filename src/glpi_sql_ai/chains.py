"""
Funções auxiliares e factories para criação das chains.
Sem side effects em tempo de importação.
"""

import logging
from html import unescape

from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


def create_sql_chain(llm):
    from .prompts import sql_prompt

    return sql_prompt | llm | StrOutputParser()


def create_final_chain(llm):
    from .prompts import final_prompt

    return final_prompt | llm | StrOutputParser()


def create_solutions_chain(llm):
    from .prompts import solutions_prompt

    return solutions_prompt | llm | StrOutputParser()


def create_intent_classifier_chain(llm):
    from .prompts import intent_classifier_prompt

    return intent_classifier_prompt | llm | StrOutputParser()


def create_scope_guard_chain(llm):
    from .prompts import scope_guard_prompt

    return scope_guard_prompt | llm | StrOutputParser()


def run_query(db, query: str) -> str:
    """Executa a query no banco após limpeza final e decodificação HTML."""
    cleaned = query.strip().replace("```sql", "").replace("```", "").strip()
    result = db.run(cleaned)
    return unescape(result)


def get_ticket_details(db, ticket_id: str) -> str:
    """Obtém detalhes de um chamado pelo ID com query parametrizada."""
    query = """
    SELECT
        t.id,
        t.name,
        t.content,
        c.name AS category,
        t.status,
        t.date_creation,
        t.solvedate
    FROM glpi_tickets AS t
    LEFT JOIN glpi_itilcategories AS c ON t.itilcategories_id = c.id
    WHERE t.id = :ticket_id AND t.entities_id = 1 AND t.is_deleted = 0
    """
    return db.run(query, parameters={"ticket_id": ticket_id})


def fetch_ticket_raw(db, ticket_id: str) -> tuple | None:
    """Busca detalhes de um chamado diretamente via engine, retornando tupla nativa."""
    from sqlalchemy import text as sa_text

    query = sa_text("""
        SELECT
            t.id,
            t.name,
            t.content,
            c.name AS category,
            t.status,
            t.date_creation,
            t.solvedate
        FROM glpi_tickets AS t
        LEFT JOIN glpi_itilcategories AS c ON t.itilcategories_id = c.id
        WHERE t.id = :tid AND t.entities_id = 1 AND t.is_deleted = 0
    """)
    with db._engine.connect() as conn:
        row = conn.execute(query, {"tid": ticket_id}).fetchone()
    return tuple(row) if row else None
