from langchain_core.output_parsers import StrOutputParser


from .config import db, llm
from .prompts import sql_prompt, final_prompt

print("⚙️  Montando as chains de execução...")

# --- FUNÇÕES AUXILIARES ---
def run_query(query: str) -> str:
    """Executa a query no banco após uma limpeza final."""
    cleaned_query = query.strip().replace("```sql", "").replace("```", "").strip()
    return db.run(cleaned_query) # type: ignore

# --- DEFINIÇÃO DAS CHAINS ---

# Chain 1: Responsável apenas por gerar o código SQL.
sql_chain = sql_prompt | llm | StrOutputParser()

# Chain 2: Responsável por pegar os dados e formular a resposta final em português.
final_chain = final_prompt | llm | StrOutputParser()