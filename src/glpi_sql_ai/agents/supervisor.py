"""
Agente supervisor: classifica a intenção do usuário e roteia para o worker correto.

Graph:
  classify_intent → route → sql_worker | solutions_worker → END
"""

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from ..chains import create_intent_classifier_chain
from ..config import AppContext
from ..prompts import get_intent_classifier_instructions
from .solutions_worker import build_solutions_worker_graph
from .sql_worker import build_sql_worker_graph


class SupervisorState(TypedDict):
    question: str
    memory_context: str
    intent: str
    answer: str


def build_supervisor_graph(ctx: AppContext):
    """Constrói o grafo supervisor com workers acoplados."""

    sql_worker_app = build_sql_worker_graph(ctx)
    solutions_worker_app = build_solutions_worker_graph(ctx)

    def classify_intent(state: SupervisorState) -> dict:
        chain = create_intent_classifier_chain(ctx.llm_sql)
        intent = chain.invoke({
            "question": state["question"],
            "intent_instructions": get_intent_classifier_instructions(),
            "memory_context": state.get("memory_context", ""),
        })
        return {"intent": intent.strip().lower()}

    def route(state: SupervisorState) -> Literal["sql_worker", "solutions_worker"]:
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
    graph.add_node("sql_worker", run_sql_worker)
    graph.add_node("solutions_worker", run_solutions_worker)

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges("classify_intent", route)
    graph.add_edge("sql_worker", END)
    graph.add_edge("solutions_worker", END)

    return graph.compile()
