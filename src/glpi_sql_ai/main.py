"""
Ponto de entrada da aplicacao.
Contem apenas o loop principal do chatbot com inicializacao explicita.
"""

import logging
import sys

from .agents.supervisor import build_supervisor_graph
from .config import AppContext
from .console import (
    banner,
    fail,
    prompt_str,
    status,
)
from .memory import ConversationMemory

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_chat_application(ctx: AppContext, memory: ConversationMemory) -> None:
    """
    Inicia um loop de chat interativo usando o grafo supervisor multiagente.

    Args:
        ctx: Contexto da aplicacao com dependencias inicializadas
        memory: Memoria conversacional entre turnos
    """
    supervisor = build_supervisor_graph(ctx)

    banner("GLPI SQL AI", "Pergunte sobre chamados ou peca solucoes tecnicas")

    while True:
        try:
            user_question = input(prompt_str())

            if user_question.lower() in ["sair", "exit", "fim", "quit"]:
                status("OK", "Ate logo!", tag_color="\033[92m")
                break

            if not user_question.strip():
                continue

            memory_context = memory.get_context()

            result = supervisor.invoke({
                "question": user_question,
                "memory_context": memory_context,
            })

            answer = result.get(
                "answer",
                "[AVISO] Nao foi possivel gerar uma resposta.",
            )
            memory.add_turn(user_question, answer, result.get("intent", ""))

        except KeyboardInterrupt:
            print()
            status("OK", "Ate logo!", tag_color="\033[92m")
            break
        except Exception as e:
            print()
            fail(f"{type(e).__name__}: {e}")
            status("Dica", "Tente fazer a pergunta de outra forma.",
                   tag_color="\033[93m")


def main() -> None:
    """Ponto de entrada: inicializa contexto e inicia o chat."""
    ctx = AppContext()
    ctx.initialize()
    memory = ConversationMemory()
    try:
        run_chat_application(ctx, memory)
    finally:
        ctx.shutdown()


if __name__ == "__main__":
    main()
