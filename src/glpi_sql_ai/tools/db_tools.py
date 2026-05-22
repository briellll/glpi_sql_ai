"""
Ferramentas de banco de dados para uso dos agents.
Encapsulam acesso a SQL e busca de chamados.
"""

from ..chains import get_ticket_details as _get_ticket_details
from ..chains import run_query as _run_query


def execute_sql(db, query: str) -> str:
    """Executa uma query SQL e retorna o resultado como string."""
    return _run_query(db, query)


def fetch_ticket_details(db, ticket_id: str) -> str:
    """Busca detalhes de um chamado pelo ID."""
    return _get_ticket_details(db, ticket_id)
