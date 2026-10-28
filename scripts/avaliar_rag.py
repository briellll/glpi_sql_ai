"""
Avaliacao do pipeline RAG do GLPI SQL AI.

Parte A: testes de recuperacao (top-1) na base vetorial.
Parte B: geracao de solucoes por chamado, com tempo por etapa.

Uso:
    poetry run python scripts/avaliar_rag.py
"""

import os
import sys
import time
from html import unescape

from dotenv import load_dotenv

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(SCRIPTS_DIR, "..")
RESULTADOS_DIR = os.path.join(SCRIPTS_DIR, "resultados")

sys.path.insert(0, os.path.join(RAIZ, "src"))

from glpi_sql_ai.chains import create_solutions_chain, fetch_ticket_raw
from glpi_sql_ai.config import AppContext
from glpi_sql_ai.knowledge_base import get_knowledge_base_context
from glpi_sql_ai.prompts import get_solutions_instructions

load_dotenv(os.path.join(RAIZ, ".env"))

CASOS = [
    ("CT07", "computador lento", "Computador lento - diagnostico e solucao"),
    ("CT08", "reset de senha login", "Reset de senha e desbloqueio de usuario"),
    ("CT09", "impressora rede configuração", "Impressora de rede - troubleshooting"),
    ("CT10", "email outlook fora do ar", "E-mail Outlook - problemas comuns e solucoes"),
    ("CT11", "certificado digital vencido", "Renovacao de certificado digital A1/A3"),
    ("N01", "papel preso na impressora", "Impressora com papel atolado"),
    ("N02", "tela azul com codigo de erro ao ligar o computador", "Tela azul (BSOD) - diagnostico"),
    ("P01", "máquina travando", "Computador lento - diagnostico e solucao"),
    ("P02", "o PC demora uma eternidade para abrir os programas",
     "Computador lento - diagnostico e solucao"),
    ("P03", "não consigo fazer login no Windows, aparece acesso negado",
     "Reset de senha e desbloqueio de usuario"),
    ("P04", "não consigo imprimir na máquina compartilhada do andar",
     "Impressora de rede - troubleshooting"),
    ("P05", "não estou recebendo mensagens na minha caixa de correio",
     "E-mail Outlook - problemas comuns e solucoes"),
    ("P06", "não consigo acessar os sistemas da empresa trabalhando de casa",
     "Configuracao de VPN para acesso remoto"),
    ("P07", "o token do e-CNPJ expirou", "Renovacao de certificado digital A1/A3"),
    ("P08", "apaguei sem querer uma planilha da pasta da rede, dá para recuperar?",
     "Backup e restauracao de arquivos"),
    ("P09", "a internet do setor está muito devagar em todos os computadores",
     "Lentidao na rede local - diagnostico"),
    ("P10", "preciso colocar um programa novo no meu computador, ele é liberado?",
     "Instalacao de software homologado"),
    ("P11", "liguei um equipamento de impressão direto no meu computador pelo cabo "
            "e ele não reconhece", "Configuracao de impressora local USB"),
    ("P12", "a impressora do setor parou de funcionar para todo mundo",
     "Impressora de rede - troubleshooting"),
]

TICKETS = ["10367", "10361", "10362", "10371", "10363", "10368", "10369"]

# mesma observacao usada no no search_kb de solutions_worker
KB_NAO_ENCONTRADO = (
    "**Observacao da Base de Conhecimento:** "
    "Nenhuma informacao especifica foi encontrada na base de conhecimento "
    "do GLPI para este tipo de problema."
)

LINHAS = []


def out(texto=""):
    """Imprime na tela e guarda a linha para o relatorio final."""
    print(texto, flush=True)
    LINHAS.append(str(texto))


def avaliar_recuperacao(ctx):
    """Parte A: mede a precisao top-1 da recuperacao vetorial."""
    out("=" * 70)
    out("PARTE A - Recuperacao na base vetorial (top-1)")
    out("=" * 70)
    out("ID | consulta | esperado | top-1 | sim 1o | top-2 | sim 2o | status")

    ok = 0
    for caso_id, consulta, esperado in CASOS:
        resultados = ctx.vector_store.search(consulta, k=3)
        top1 = resultados[0] if resultados else {}
        top2 = resultados[1] if len(resultados) > 1 else {}

        titulo1 = top1.get("title", "-")
        titulo2 = top2.get("title", "-")
        sim1 = f"{1 - top1['score'] / 2:.3f}" if top1 else "-"
        sim2 = f"{1 - top2['score'] / 2:.3f}" if top2 else "-"

        acertou = titulo1 == esperado
        ok += 1 if acertou else 0

        out(f"{caso_id} | {consulta} | {esperado} | {titulo1} | {sim1} | "
            f"{titulo2} | {sim2} | {'OK' if acertou else 'FALHA'}")

    out("")
    out(f"Total OK: {ok}/{len(CASOS)}")
    return ok


def extrair_titulos(contexto):
    """Extrai os titulos dos artigos das linhas '**Artigo N:** Titulo'."""
    titulos = []
    for linha in contexto.splitlines():
        if linha.startswith("**Artigo "):
            titulos.append(linha.split(":**", 1)[1].strip())
    return titulos


def avaliar_solucoes(ctx):
    """Parte B: reproduz as etapas do solutions_worker medindo cada uma."""
    out("")
    out("=" * 70)
    out("PARTE B - Geracao de solucoes")
    out("=" * 70)

    os.makedirs(RESULTADOS_DIR, exist_ok=True)

    for tid in TICKETS:
        # 1. SQL
        t0 = time.perf_counter()
        row = fetch_ticket_raw(ctx.db, str(tid))
        if not row:
            out(f"{tid} | chamado nao encontrado")
            continue
        ticket_info = {
            "ticket_id": row[0],
            "title": unescape(row[1] or "Sem titulo"),
            "description": unescape(row[2] or "Sem descricao"),
            "category": unescape(row[3] or "Nao categorizado"),
            "status": row[4] or "Desconhecido",
            "date_creation": str(row[5] or ""),
            "solvedate": str(row[6] or ""),
        }
        sql_ms = (time.perf_counter() - t0) * 1000

        # 2. KB
        t0 = time.perf_counter()
        kb_content = get_knowledge_base_context(
            ctx.vector_store,
            ticket_info["title"],
            ticket_info["category"],
            ticket_info["description"],
        )
        kb_context = KB_NAO_ENCONTRADO if kb_content == "NÃO_ENCONTRADO" else kb_content
        artigos = extrair_titulos(kb_context)
        kb_ms = (time.perf_counter() - t0) * 1000

        # 3. LLM
        t0 = time.perf_counter()
        # como no worker, a chain e criada dentro da etapa de geracao
        chain = create_solutions_chain(ctx.llm_creative)
        resposta = chain.invoke({
            "ticket_id": ticket_info["ticket_id"],
            "title": ticket_info["title"],
            "description": ticket_info["description"],
            "category": ticket_info["category"],
            "status": ticket_info["status"],
            "date_creation": ticket_info.get("date_creation", ""),
            "solvedate": ticket_info.get("solvedate", ""),
            "question": f"solucoes para o chamado {ticket_info['ticket_id']}",
            "kb_context": kb_context,
            "solutions_instructions": get_solutions_instructions(),
            "memory_context": "",
        })
        llm_ms = (time.perf_counter() - t0) * 1000

        total_s = (sql_ms + kb_ms + llm_ms) / 1000

        # salva a resposta completa do chamado
        lista_artigos = "\n".join(f"- {a}" for a in artigos) or "- (nenhum)"
        conteudo = (
            f"Chamado {tid}\n"
            f"Titulo: {ticket_info['title']}\n\n"
            f"Artigos recuperados:\n{lista_artigos}\n\n"
            f"Resposta:\n{resposta}\n"
        )
        with open(os.path.join(RESULTADOS_DIR, f"solucao_{tid}.txt"),
                  "w", encoding="utf-8") as f:
            f.write(conteudo)

        out(f"{tid} | {ticket_info['title']} | "
            f"{'; '.join(artigos) or '(nenhum)'} | "
            f"SQL {sql_ms:.0f}ms | KB {kb_ms:.0f}ms | LLM {llm_ms:.0f}ms | "
            f"total {total_s:.2f}s")


def main():
    ctx = AppContext()
    ctx.initialize()
    try:
        avaliar_recuperacao(ctx)
        avaliar_solucoes(ctx)
    finally:
        ctx.shutdown()

    caminho = os.path.join(RESULTADOS_DIR, "relatorio.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(LINHAS) + "\n")
    print(f"\nRelatorio salvo em {caminho}", flush=True)


if __name__ == "__main__":
    main()
