"""
Módulo responsável pela lógica de negócio da aplicação.
Contém funções para classificar intenções, processar consultas e gerar soluções.
Integra informações da base de conhecimento do GLPI.
"""

import ast
import logging
import re

from .chains import (
    create_final_chain,
    create_intent_classifier_chain,
    create_solutions_chain,
    create_sql_chain,
    get_ticket_details,
    run_query,
)
from .config import AppContext
from .knowledge_base import get_knowledge_base_context
from .prompts import (
    get_intent_classifier_instructions,
    get_solutions_instructions,
    get_system_instructions,
)

logger = logging.getLogger(__name__)


def extract_ticket_id(question: str) -> str | None:
    """
    Extrai o ID do chamado da pergunta do usuário.

    Args:
        question: Pergunta do usuário

    Returns:
        ID do chamado como string ou None se não encontrar
    """
    match = re.search(
        r"(?:id\s*|chamado\s*|ticket\s*)?(\d+)", question, re.IGNORECASE
    )
    return match.group(1) if match else None


def parse_ticket_details(details_str: str) -> dict | None:
    """
    Faz o parsing dos detalhes do chamado retornados do banco.
    Aplica unescape em cada campo de texto para limpar entidades HTML.

    Args:
        details_str: String retornada do banco com formato de lista de tuplas

    Returns:
        Dicionário com detalhes do chamado ou None se houver erro
    """
    from html import unescape as _unescape

    try:
        data = ast.literal_eval(details_str)
        if not data or not data[0]:
            return None

        row = data[0]
        return {
            "ticket_id": row[0],
            "title": _unescape(row[1] or "Sem título"),
            "description": _unescape(row[2] or "Sem descrição"),
            "category": _unescape(row[3] or "Não categorizado"),
            "status": row[4] or "Desconhecido",
            "date_creation": str(row[5] or ""),
            "solvedate": str(row[6] or ""),
        }
    except Exception as e:
        logger.error("Erro ao fazer parsing dos detalhes: %s", e)
        return None


def classify_user_intent(
    ctx: AppContext, question: str, memory_context: str = ""
) -> str:
    """
    Usa a LLM para classificar a intenção do usuário.

    Args:
        ctx: Contexto da aplicação com dependências
        question: Pergunta do usuário
        memory_context: Histórico da conversa para contexto

    Returns:
        "database_query" ou "get_solutions"
    """
    chain = create_intent_classifier_chain(ctx.llm_sql)
    intent = chain.invoke({
        "question": question,
        "intent_instructions": get_intent_classifier_instructions(),
        "memory_context": memory_context,
    })
    return intent.strip().lower()


def process_solutions_request(
    ctx: AppContext, question: str, memory_context: str = ""
) -> str:
    """
    Processa uma solicitação de soluções para um chamado específico.

    Args:
        ctx: Contexto da aplicação com dependências
        question: Pergunta do usuário contendo ID do chamado
        memory_context: Histórico da conversa para contexto

    Returns:
        Resposta gerada (string vazia em caso de erro)
    """
    ticket_id = extract_ticket_id(question)

    if not ticket_id:
        msg = (
            "[AVISO] Nao consegui identificar o ID do chamado. "
            "Por favor, inclua o ID na sua pergunta "
            "(ex: 'solucoes para o chamado 2233')."
        )
        print(msg)
        print("-" * 80)
        return msg

    print(f"[Busca] Buscando detalhes do chamado {ticket_id}...")
    details_str = get_ticket_details(ctx.db, ticket_id)
    ticket_info = parse_ticket_details(details_str)

    if not ticket_info:
        msg = f"[ERRO] Nao consegui encontrar o chamado com ID {ticket_id}."
        print(msg)
        print("-" * 80)
        return msg

    print("[KB] Buscando informacoes na base de conhecimento...")
    kb_context = ""

    kb_content = get_knowledge_base_context(
        ctx.vector_store,
        ticket_info["title"],
        ticket_info["category"],
        ticket_info["description"],
    )
    if kb_content != "NÃO_ENCONTRADO":
        kb_context = kb_content
    else:
        kb_context = (
            "**Observação da Base de Conhecimento:** "
            "Nenhuma informação específica foi encontrada na base de conhecimento "
            "do GLPI para este tipo de problema."
        )

    print(f"[Solucoes] Gerando solucoes para o chamado {ticket_id}...\n")

    solutions_chain = create_solutions_chain(ctx.llm_creative)
    solutions = solutions_chain.invoke({
        "ticket_id": ticket_info["ticket_id"],
        "title": ticket_info["title"],
        "description": ticket_info["description"],
        "category": ticket_info["category"],
        "status": ticket_info["status"],
        "date_creation": ticket_info.get("date_creation", ""),
        "solvedate": ticket_info.get("solvedate", ""),
        "question": question,
        "kb_context": kb_context,
        "solutions_instructions": get_solutions_instructions(),
        "memory_context": memory_context,
    })

    print(f"[Solucoes] Solucoes Sugeridas:\n{solutions}")
    print("-" * 80)
    return solutions


def process_database_query(
    ctx: AppContext, question: str, memory_context: str = ""
) -> str:
    """
    Processa uma consulta de banco de dados.

    Args:
        ctx: Contexto da aplicação com dependências
        question: Pergunta do usuário a ser convertida em SQL
        memory_context: Histórico da conversa para contexto

    Returns:
        Resposta gerada
    """
    sql_chain = create_sql_chain(ctx.llm_sql)
    final_chain = create_final_chain(ctx.llm_sql)

    sql_query = sql_chain.invoke({
        "question": question,
        "system_instructions": get_system_instructions(),
        "memory_context": memory_context,
    })
    db_response = run_query(ctx.db, sql_query)

    final_answer = final_chain.invoke({
        "question": question,
        "response": db_response,
    })

    print(f"Assistente:\n{final_answer}")
    print("-" * 80)
    return final_answer
