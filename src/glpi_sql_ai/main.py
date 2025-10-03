
# Importa as chains e funções necessárias de nossos módulos locais
from .chains import sql_chain, final_chain, run_query

def run_chat_application():
    """
    Inicia um loop de chat interativo para consultar a base de dados.
    """
    print("="*80)
    print("🤖 Olá! Sou seu assistente de banco de dados GLPI.")
    print("   Faça uma pergunta sobre os chamados ou digite 'sair' para terminar.")
    print("="*80)

    # Loop infinito para manter o chat ativo
    while True:
        try:
            # 1. Obter a pergunta do usuário a partir do terminal
            user_question = input("Você: ")

            # 2. Criar uma condição de saída do chat
            if user_question.lower() in ["sair", "exit", "fim", "quit"]:
                print("🤖 Até a próxima!")
                break

            # Etapa 1: Gerar a query SQL
            sql_query = sql_chain.invoke({"question": user_question})
            print(f"🔍 SQL GERADO PELA IA:\n{sql_query}\n")
            # Etapa 2: Executar a query no banco
            db_response = run_query(sql_query)

            # Etapa 3: Gerar a resposta final amigável
            final_answer = final_chain.invoke({
                "question": user_question,
                "query": sql_query,
                "response": db_response
            })

            # 4. Imprimir a resposta do bot na tela
            print(f"🤖 Assistente: {final_answer}")
            print("-" * 80)

        except Exception as e:
            # O try/except dentro do loop garante que o chat não morra se houver um erro
            print(f"\n❌ Ocorreu um erro ao processar sua pergunta: {type(e).__name__}: {e}")
            print("🤖 Por favor, tente fazer a pergunta de outra forma.")
            print("-" * 80)

if __name__ == "__main__":
    print("▶️  Iniciando a aplicação...")
    run_chat_application()