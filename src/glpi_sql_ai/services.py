"""
Módulo responsável pela lógica de negócio da aplicação.
Contém funções para classificar intenções, processar consultas e gerar soluções.
Integra informações da base de conhecimento do GLPI.
"""

import re
import ast

from .chains import (
    sql_chain,
    final_chain,
    solutions_chain,
    intent_classifier_chain,
    run_query,
    get_ticket_details,
)
from .knowledge_base import get_knowledge_base_context
from .config import kb


def extract_ticket_id(question: str) -> str | None:
    """
    Extrai o ID do chamado da pergunta do usuário.

    Args:
        question: Pergunta do usuário

    Returns:
        ID do chamado como string ou None se não encontrar
    """
    match = re.search(
        r"(?:id\s*|chamado\s*|ticket\s*)?(\d+)",
        question,
        re.IGNORECASE
    )
    return match.group(1) if match else None


def classify_user_intent(question: str) -> str:
    """
    Usa a LLM para classificar a intenção do usuário.

    Args:
        question: Pergunta do usuário

    Returns:
        "database_query" ou "get_solutions"
    """
    intent = intent_classifier_chain.invoke({"question": question})
    return intent.strip().lower()


def parse_ticket_details(details_str: str) -> dict | None:
    """
    Faz o parsing dos detalhes do chamado retornados do banco.

    Args:
        details_str: String retornada do banco com formato de lista de tuplas

    Returns:
        Dicionário com detalhes do chamado ou None se houver erro
    """
    try:
        data = ast.literal_eval(details_str)

        if not data or not data[0]:
            return None

        row = data[0]
        return {
            "ticket_id": row[0],
            "title": row[1] or "Sem título",
            "description": row[2] or "Sem descrição",
            "category": row[3] or "Não categorizado",
            "priority": row[4] or "N/A",
            "urgency": row[5] or "N/A",
            "impact": row[6] or "N/A",
            "status": row[7] or "Desconhecido",
        }
    except Exception as e:
        print(f"❌ Erro ao fazer parsing dos detalhes: {e}")
        return None


def process_solutions_request(question: str) -> None:
    """
    Processa uma solicitação de soluções para um chamado específico.

    Integra informações da base de conhecimento do GLPI com o conhecimento
    próprio da LLM para fornecer soluções mais precisas e contextualizadas.

    Args:
        question: Pergunta do usuário contendo ID do chamado
    """
    ticket_id = extract_ticket_id(question)

    if not ticket_id:
        print(
            "⚠️  Não consegui identificar o ID do chamado. "
            "Por favor, inclua o ID na sua pergunta (ex: 'soluções para o chamado 2233')."
        )
        print("-" * 80)
        return

    print(f"🔍 Buscando detalhes do chamado {ticket_id}...")
    details_str = get_ticket_details(ticket_id)

    ticket_info = parse_ticket_details(details_str)

    if not ticket_info:
        print(f"❌ Não consegui encontrar o chamado com ID {ticket_id}.")
        print("-" * 80)
        return

    # ===== NOVO: Busca informações na base de conhecimento =====
    print(f"📚 Buscando informações na base de conhecimento...")
    kb_context = ""

    if kb:
        kb_content = get_knowledge_base_context(
            kb,
            ticket_info['title'],
            ticket_info["category"],
            ticket_info["description"]
        )
        if kb_content != "NÃO_ENCONTRADO":
            kb_context = kb_content
        else:
            kb_context = (
                "**Observação da Base de Conhecimento:** "
                "Nenhuma informação específica foi encontrada na base de conhecimento "
                "do GLPI para este tipo de problema."
            )
    else:
        kb_context = (
            "**Observação:** A base de conhecimento do GLPI não está disponível "
            "no momento. As soluções serão baseadas apenas no conhecimento da IA."
        )

    print(f"💡 Gerando soluções para o chamado {ticket_id}...\n")

    solutions = solutions_chain.invoke({
        "ticket_id": ticket_info["ticket_id"],
        "title": ticket_info["title"],
        "description": ticket_info["description"],
        "category": ticket_info["category"],
        "priority": ticket_info["priority"],
        "urgency": ticket_info["urgency"],
        "impact": ticket_info["impact"],
        "status": ticket_info["status"],
        "question": question,
        "kb_context": kb_context,
    })

    print(f"💡 Soluções Sugeridas:\n{solutions}")
    print("-" * 80)


def process_database_query(question: str) -> None:
    """
    Processa uma consulta de banco de dados.

    Converte a pergunta em linguagem natural para uma query SQL válida,
    executa no banco de dados e formata a resposta de forma legível.

    Args:
        question: Pergunta do usuário a ser convertida em SQL
    """
    sql_query = sql_chain.invoke({"question": question})
    #print(f"🔍 SQL GERADO PELA IA:\n{sql_query}\n")

    db_response = run_query(sql_query)

    final_answer = final_chain.invoke({
        "question": question,
        "response": db_response,
    })

    print(f"🤖 Assistente:\n{final_answer}")
    print("-" * 80)