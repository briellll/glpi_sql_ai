
from .chains import sql_chain, final_chain, run_query

def run_application():
    """
    Função principal que executa as perguntas contra as chains.
    """
    try:
        # Lista de perguntas para testar
        perguntas = [
            "top 3 setores que mais abriram chamados para o setor de TI",
            "qual o quinto setor que mais abriu chamados para o TI",
        ]

        print("\n🚀 Executando perguntas...")
        for p in perguntas:
            print("="*80)
            print(f"💬 Pergunta: {p}")

            # Etapa 1: Gerar a query SQL
            sql_query = sql_chain.invoke({"question": p})
            print(f"🔍 SQL GERADO PELA IA:\n{sql_query}\n")
            # Etapa 2: Executar a query no banco
            db_response = run_query(sql_query)
            #print(f"📄 Resposta do Banco: {db_response}\n")
            # Etapa 3: Gerar a resposta final amigável
            final_answer = final_chain.invoke({
                "question": p,
                "query": sql_query,
                "response": db_response
            })
            print(f"✅ Resposta Final: {final_answer}")

    except Exception as e:
        print(f"\n❌ Ocorreu um erro: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("▶️  Iniciando a aplicação...")
    run_application()