"""
Ponto de entrada da aplicação. Contém apenas o loop principal do chatbot.
"""

from .services import (
    classify_user_intent,
    process_solutions_request,
    process_database_query,
)


def run_chat_application() -> None:
    """
    Inicia um loop de chat interativo para consultar a base de dados.
    """
    print("=" * 80)
    print("🤖 Olá! Sou seu assistente de banco de dados GLPI.")
    print("   Faça uma pergunta sobre os chamados ou digite 'sair' para terminar.")
    print("=" * 80)

    while True:
        try:
            user_question = input("Você: ")

            if user_question.lower() in ["sair", "exit", "fim", "quit"]:
                print("🤖 Até a próxima!")
                break

            print("🤔 Analisando sua pergunta...")
            intent = classify_user_intent(user_question)

            if intent == "get_solutions":
                process_solutions_request(user_question)
            elif intent == "database_query":
                process_database_query(user_question)
            else:
                print(f"⚠️  Não consegui entender sua intenção. Resposta: {intent}")
                print("-" * 80)

        except Exception as e:
            print(
                f"\n❌ Ocorreu um erro ao processar sua pergunta: "
                f"{type(e).__name__}: {e}"
            )
            print("🤖 Por favor, tente fazer a pergunta de outra forma.")
            print("-" * 80)


if __name__ == "__main__":
    print("▶️  Iniciando a aplicação...")
    run_chat_application()