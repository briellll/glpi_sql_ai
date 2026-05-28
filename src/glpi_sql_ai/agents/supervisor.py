"""
Agente supervisor: classifica intenção, valida escopo e roteia para o worker correto.

Graph:
  classify_intent -> guard_scope -> route -> sql_worker | solutions_worker | END
"""

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from ..chains import create_intent_classifier_chain, create_scope_guard_chain
from ..config import AppContext
from ..console import result_box, warn
from ..prompts import get_intent_classifier_instructions, get_scope_guard_instructions
from .solutions_worker import build_solutions_worker_graph
from .sql_worker import build_sql_worker_graph


class SupervisorState(TypedDict):
    question: str
    memory_context: str
    intent: str
    scope_valid: bool
    answer: str


def build_supervisor_graph(ctx: AppContext):
    """Constroi o grafo supervisor com workers acoplados e validacao de escopo."""

    sql_worker_app = build_sql_worker_graph(ctx)
    solutions_worker_app = build_solutions_worker_graph(ctx)

    def classify_intent(state: SupervisorState) -> dict:
        chain = create_intent_classifier_chain(ctx.llm_sql)
        intent = chain.invoke({
            "question": state["question"],
            "intent_instructions": get_intent_classifier_instructions(),
            "memory_context": state.get("memory_context", ""),
        })
        intent = intent.strip().lower()
        if intent not in ("database_query", "get_solutions"):
            intent = "database_query"
        return {"intent": intent}

    def guard_scope(state: SupervisorState) -> dict:
        chain = create_scope_guard_chain(ctx.llm_sql)
        scope = chain.invoke({
            "question": state["question"],
            "scope_instructions": get_scope_guard_instructions(),
            "memory_context": state.get("memory_context", ""),
        })
        scope = scope.strip().lower()

        if scope == "out_of_scope":
            warn(
                "Pergunta fora do escopo de helpdesk/GLPI. "
                "Responda apenas sobre chamados, tickets, tecnicos "
                "e suporte de TI."
            )
            answer = (
                "Desculpe, sou um assistente especializado em helpdesk e "
                "suporte de TI integrado ao GLPI. Posso ajudar com consultas "
                "sobre chamados, tecnicos, setores, base de conhecimento e "
                "topicos relacionados a service desk. "
                "Reformule sua pergunta para o contexto de TI."
            )
            result_box(answer, title="Resposta")
            return {"scope_valid": False, "answer": answer}
        return {"scope_valid": True}

    def route(
        state: SupervisorState,
    ) -> Literal["sql_worker", "solutions_worker", "__end__"]:
        if not state.get("scope_valid", False):
            return END
        if state["intent"] == "get_solutions":
            return "solutions_worker"
        return "sql_worker"

    def run_sql_worker(state: SupervisorState) -> dict:
        result = sql_worker_app.invoke({
            "question": state["question"],
            "memory_context": state.get("memory_context", ""),
        })
        return {"answer": result["answer"]}

    def run_solutions_worker(state: SupervisorState) -> dict:
        result = solutions_worker_app.invoke({
            "question": state["question"],
            "memory_context": state.get("memory_context", ""),
        })
        return {"answer": result["answer"]}

    graph = StateGraph(SupervisorState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("guard_scope", guard_scope)
    graph.add_node("sql_worker", run_sql_worker)
    graph.add_node("solutions_worker", run_solutions_worker)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "guard_scope")
    graph.add_conditional_edges("guard_scope", route)
    graph.add_edge("sql_worker", END)
    graph.add_edge("solutions_worker", END)

    return graph.compile()
