"""
Solutions Worker Agent: processa pedidos de solução para chamados.

Graph:
  extract_ticket → get_details → search_kb → generate_solutions → END
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..chains import create_solutions_chain, get_ticket_details
from ..config import AppContext
from ..knowledge_base import get_knowledge_base_context
from ..prompts import get_solutions_instructions
from ..services import extract_ticket_id, parse_ticket_details


class SolutionsWorkerState(TypedDict):
    question: str
    memory_context: str
    ticket_id: str
    ticket_info: dict
    kb_context: str
    answer: str


def build_solutions_worker_graph(ctx: AppContext):
    """Constrói o grafo do solutions worker."""

    def extract_ticket(state: SolutionsWorkerState) -> dict:
        ticket_id = extract_ticket_id(state["question"])
        if not ticket_id:
            msg = (
                "[AVISO] Nao consegui identificar o ID do chamado. "
                "Por favor, inclua o ID na sua pergunta "
                "(ex: 'solucoes para o chamado 2233')."
            )
            print(msg)
            print("-" * 80)
            return {"answer": msg}
        print(f"[Busca] Buscando detalhes do chamado {ticket_id}...")
        return {"ticket_id": ticket_id}

    def get_details(state: SolutionsWorkerState) -> dict:
        if state.get("answer"):
            return {}
        details_str = get_ticket_details(ctx.db, state["ticket_id"])
        ticket_info = parse_ticket_details(details_str)
        if not ticket_info:
            msg = f"[ERRO] Nao consegui encontrar o chamado com ID {state['ticket_id']}."
            print(msg)
            print("-" * 80)
            return {"answer": msg}
        return {"ticket_info": ticket_info}

    def search_kb(state: SolutionsWorkerState) -> dict:
        if state.get("answer"):
            return {}
        print("[KB] Buscando informacoes na base de conhecimento...")
        ticket_info = state["ticket_info"]
        kb_content = get_knowledge_base_context(
            ctx.vector_store,
            ticket_info["title"],
            ticket_info["category"],
            ticket_info["description"],
        )
        if kb_content == "NÃO_ENCONTRADO":
            kb_context = (
                "**Observacao da Base de Conhecimento:** "
                "Nenhuma informacao especifica foi encontrada na base de conhecimento "
                "do GLPI para este tipo de problema."
            )
        else:
            kb_context = kb_content
        return {"kb_context": kb_context}

    def generate_solutions(state: SolutionsWorkerState) -> dict:
        if state.get("answer"):
            return {}
        ticket_info = state["ticket_info"]
        print(f"[Solucoes] Gerando solucoes para o chamado {ticket_info['ticket_id']}...\n")

        chain = create_solutions_chain(ctx.llm_creative)
        solutions = chain.invoke({
            "ticket_id": ticket_info["ticket_id"],
            "title": ticket_info["title"],
            "description": ticket_info["description"],
            "category": ticket_info["category"],
            "priority": ticket_info["priority"],
            "urgency": ticket_info["urgency"],
            "impact": ticket_info["impact"],
            "status": ticket_info["status"],
            "question": state["question"],
            "kb_context": state["kb_context"],
            "solutions_instructions": get_solutions_instructions(),
            "memory_context": state.get("memory_context", ""),
        })

        print(f"[Solucoes] Solucoes Sugeridas:\n{solutions}")
        print("-" * 80)
        return {"answer": solutions}

    graph = StateGraph(SolutionsWorkerState)

    graph.add_node("extract_ticket", extract_ticket)
    graph.add_node("get_details", get_details)
    graph.add_node("search_kb", search_kb)
    graph.add_node("generate_solutions", generate_solutions)

    graph.set_entry_point("extract_ticket")
    graph.add_edge("extract_ticket", "get_details")
    graph.add_edge("get_details", "search_kb")
    graph.add_edge("search_kb", "generate_solutions")
    graph.add_edge("generate_solutions", END)

    return graph.compile()
