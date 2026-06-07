"""
SQL Worker Agent: gera SQL, executa, e auto-corrige em caso de erro.

Graph:
  generate_sql -> execute_sql -> route -> fix_sql (loop) | format_answer -> END
"""

from typing import Literal, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from ..chains import create_final_chain, create_sql_chain, run_query
from ..config import AppContext
from ..console import display, fail, status
from ..prompts import FIX_SQL_TEMPLATE, get_system_instructions

MAX_ATTEMPTS = 3


class SQLWorkerState(TypedDict):
    question: str
    memory_context: str
    sql: str
    result: str
    error: str
    attempts: int
    answer: str


def build_sql_worker_graph(ctx: AppContext):
    """Constroi o grafo do SQL worker com auto-correcao."""

    def generate_sql(state: SQLWorkerState) -> dict:
        status("SQL", "Gerando consulta...")
        chain = create_sql_chain(ctx.llm_sql)
        sql = chain.invoke({
            "question": state["question"],
            "system_instructions": get_system_instructions(),
            "memory_context": state.get("memory_context", ""),
        })
        return {"sql": sql, "attempts": state.get("attempts", 0) + 1}

    def execute_sql(state: SQLWorkerState) -> dict:
        status("SQL", "Executando no banco...")
        try:
            result = run_query(ctx.db, state["sql"])
            return {"result": result, "error": ""}
        except Exception as e:
            return {"result": "", "error": str(e)}

    def route_after_execute(state: SQLWorkerState) -> Literal["fix_sql", "format_answer"]:
        if state.get("error") and state["attempts"] < MAX_ATTEMPTS:
            return "fix_sql"
        return "format_answer"

    def fix_sql(state: SQLWorkerState) -> dict:
        a = state["attempts"] + 1
        status("SQL", f"Corrigindo consulta (tentativa {a}/{MAX_ATTEMPTS})...",
               tag_color="\033[93m")
        prompt = ChatPromptTemplate.from_messages([
            ("system", FIX_SQL_TEMPLATE),
            ("human", "{question}"),
        ])
        chain = prompt | ctx.llm_sql | StrOutputParser()
        fixed = chain.invoke({
            "sql": state["sql"],
            "error": state["error"],
            "question": state["question"],
        })
        return {
            "sql": fixed.strip().replace("```sql", "").replace("```", "").strip(),
            "attempts": state["attempts"] + 1,
        }

    def format_answer(state: SQLWorkerState) -> dict:
        if state.get("error"):
            fail(
                f"Nao foi possivel executar a consulta apos "
                f"{state['attempts']} tentativas.\n"
                f"Erro: {state['error']}"
            )
            return {"answer": state["error"]}

        chain = create_final_chain(ctx.llm_sql)
        answer = chain.invoke({
            "question": state["question"],
            "response": state["result"],
        })

        display(answer, title="Resultado", color="\033[96m")

        return {"answer": answer}

    graph = StateGraph(SQLWorkerState)

    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("fix_sql", fix_sql)
    graph.add_node("format_answer", format_answer)

    graph.set_entry_point("generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_conditional_edges("execute_sql", route_after_execute)
    graph.add_edge("fix_sql", "execute_sql")
    graph.add_edge("format_answer", END)

    return graph.compile()
