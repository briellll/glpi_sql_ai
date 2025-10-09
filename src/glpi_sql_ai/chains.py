from langchain_core.output_parsers import StrOutputParser

from .config import db, llm
from .prompts import (
    sql_prompt,
    final_prompt,
    solutions_prompt,
    intent_classifier_prompt,
)

print("⚙️  Montando as chains de execução...")

# --- FUNÇÕES AUXILIARES ---
def run_query(query: str) -> str:
    """Executa a query no banco após uma limpeza final."""
    cleaned_query = query.strip().replace("```sql", "").replace("```", "").strip()
    return db.run(cleaned_query)  # type: ignore


def get_ticket_details(ticket_id: str) -> str:
    """Obtém os detalhes de um chamado específico pelo ID."""
    query = f"""
    SELECT
        t.id,
        t.name,
        t.content,
        c.name as category,
        t.priority,
        t.urgency,
        t.impact,
        t.status
    FROM glpi_tickets AS t
    LEFT JOIN glpi_itilcategories AS c ON t.itilcategories_id = c.id
    WHERE t.id = {ticket_id} AND t.entities_id = 1 AND t.is_deleted = 0
    """
    return db.run(query)  # type: ignore


# --- DEFINIÇÃO DAS CHAINS ---

# Chain 1: Responsável apenas por gerar o código SQL.
sql_chain = sql_prompt | llm | StrOutputParser()

# Chain 2: Responsável por pegar os dados e formular a resposta final em português.
final_chain = final_prompt | llm | StrOutputParser()

# Chain 3: Responsável por gerar soluções baseadas no contexto do chamado.
solutions_chain = solutions_prompt | llm | StrOutputParser()

# Chain 4: Responsável por classificar a intenção do usuário.
intent_classifier_chain = intent_classifier_prompt | llm | StrOutputParser()