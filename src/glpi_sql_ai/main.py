"""
Ponto de entrada da aplicação.
Contém apenas o loop principal do chatbot com inicialização explícita.
"""

import logging
import sys

from .agents.supervisor import build_supervisor_graph
from .config import AppContext
from .memory import ConversationMemory

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_chat_application(ctx: AppContext, memory: ConversationMemory) -> None:
    """
    Inicia um loop de chat interativo usando o grafo supervisor multiagente.

    Args:
        ctx: Contexto da aplicação com dependências inicializadas
        memory: Memória conversacional entre turnos
    """
    supervisor = build_supervisor_graph(ctx)

    print("=" * 80)
    print("Ola! Sou seu assistente de banco de dados GLPI.")
    print("   Faca uma pergunta sobre os chamados ou digite 'sair' para terminar.")
    print("=" * 80)

    while True:
        try:
            user_question = input("Voce: ")

            if user_question.lower() in ["sair", "exit", "fim", "quit"]:
                print("Ate a proxima!")
                break

            memory_context = memory.get_context()

            print("Analisando sua pergunta...")
            result = supervisor.invoke({
                "question": user_question,
                "memory_context": memory_context,
            })

            answer = result.get("answer", "[AVISO] Nao foi possivel gerar uma resposta.")
            memory.add_turn(user_question, answer, result.get("intent", ""))

        except KeyboardInterrupt:
            print("\nAte a proxima!")
            break
        except Exception as e:
            print(
                f"\n[ERRO] Ocorreu um erro ao processar sua pergunta: "
                f"{type(e).__name__}: {e}"
            )
            print("Por favor, tente fazer a pergunta de outra forma.")
            print("-" * 80)


def main() -> None:
    """Ponto de entrada: inicializa contexto e inicia o chat."""
    ctx = AppContext()
    ctx.initialize()
    memory = ConversationMemory()
    run_chat_application(ctx, memory)


if __name__ == "__main__":
    main()
