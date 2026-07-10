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


def _format_cell(value) -> str:
    """Formata um valor de célula para apresentação limpa ao formatador."""
    import datetime as _dt

    if value is None:
        return "N/D"
    if isinstance(value, _dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, _dt.date):
        return value.strftime("%Y-%m-%d")
    return unescape(str(value))


def run_query(db, query: str) -> str:
    """Executa a query e retorna um resultado limpo, rotulado por coluna.

    Diferentemente do dump cru de tuplas (que confundia o formatador final e
    o levava a reportar "nenhum resultado" para conjuntos multi-linha), esta
    versão devolve os nomes das colunas e os valores já formatados (datas
    legíveis, HTML decodificado), tornando a formatação final determinística
    e confiável.
    """
    cleaned = query.strip().replace("```sql", "").replace("```", "").strip()

    # exec_driver_sql: passa o SQL direto ao driver, sem interpretar ':' ou '%'
    # como parâmetros (comum em literais de data/hora e cláusulas LIKE).
    with db._engine.connect() as conn:
        proxy = conn.exec_driver_sql(cleaned)
        if proxy.returns_rows:
            columns = list(proxy.keys())
            rows = proxy.fetchall()
        else:
            columns, rows = [], []

    if not rows:
        return "[]"

    header = " | ".join(columns)
    body = "\n".join(" | ".join(_format_cell(v) for v in row) for row in rows)
    return f"{len(rows)} linha(s) retornada(s).\nColunas: {header}\n{body}"


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
