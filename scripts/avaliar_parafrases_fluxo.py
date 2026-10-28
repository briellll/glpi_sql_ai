"""
Avaliacao do fluxo completo (busca + geracao) para as parafrases P01-P12.

Para cada parafrase, simula um chamado cujo texto e a propria parafrase,
executa as etapas de busca e geracao do solutions_worker e classifica qual
artigo recuperado o modelo utilizou na resposta final.

Uso:
    poetry run python scripts/avaliar_parafrases_fluxo.py
"""

import os
import unicodedata

from avaliar_rag import (
    CASOS,
    KB_NAO_ENCONTRADO,
    RESULTADOS_DIR,
    extrair_titulos,
)

from glpi_sql_ai.chains import create_solutions_chain
from glpi_sql_ai.config import AppContext
from glpi_sql_ai.knowledge_base import get_knowledge_base_context
from glpi_sql_ai.prompts import get_solutions_instructions

EXECUCOES = 3
RECUSA = "Não identifiquei nenhuma informação"

CASOS_PARAFRASE = [
    (caso_id, consulta, esperado)
    for caso_id, consulta, esperado in CASOS
    if caso_id.startswith("P")
]

LINHAS = []


def out(texto=""):
    """Imprime na tela e guarda a linha para o relatorio final."""
    print(texto, flush=True)
    LINHAS.append(str(texto))


def normalizar(texto):
    """Remove acentos e caixa para comparacao de titulos na resposta."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def classificar(resposta, titulos):
    """Identifica recusa ou quais titulos recuperados aparecem na resposta."""
    normalizada = normalizar(resposta)
    if normalizar(RECUSA) in normalizada:
        return "RECUSA"

    usados = [titulo for titulo in titulos if normalizar(titulo) in normalizada]
    return "; ".join(usados) if usados else "(nenhum)"


def salvar_resposta(caso_id, run, consulta, esperado, artigos, resposta):
    """Grava uma execucao em resultados/fluxo_<ID>_r<n>.txt."""
    lista_artigos = "\n".join(f"- {artigo}" for artigo in artigos) or "- (nenhum)"
    conteudo = (
        f"Caso {caso_id} - execucao {run}\n"
        f"Consulta: {consulta}\n"
        f"Esperado: {esperado}\n\n"
        f"Artigos recuperados (ordem):\n{lista_artigos}\n\n"
        f"Resposta:\n{resposta}\n"
    )
    caminho = os.path.join(RESULTADOS_DIR, f"fluxo_{caso_id}_r{run}.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def avaliar_fluxo(ctx):
    """Reproduz busca e geracao do solutions_worker para cada parafrase."""
    os.makedirs(RESULTADOS_DIR, exist_ok=True)

    out("=" * 70)
    out("FLUXO - Busca + geracao para as parafrases P01-P12")
    out("=" * 70)
    out("ID | run | esperado | recuperados | classificacao")

    for caso_id, consulta, esperado in CASOS_PARAFRASE:
        for run in range(1, EXECUCOES + 1):
            # 1. Busca: titulo = parafrase, categoria e descricao vazias
            kb_content = get_knowledge_base_context(
                ctx.vector_store, consulta, "", ""
            )
            kb_context = (
                KB_NAO_ENCONTRADO
                if kb_content == "NÃO_ENCONTRADO"
                else kb_content
            )
            artigos = extrair_titulos(kb_context)

            # 2. Geracao: mesma entrada usada por generate_solutions
            chain = create_solutions_chain(ctx.llm_creative)
            resposta = chain.invoke({
                "ticket_id": caso_id,
                "title": consulta,
                "description": consulta,
                "category": "Nao categorizado",
                "status": "Novo",
                "date_creation": "",
                "solvedate": "",
                "question": f"solucoes para o chamado {caso_id}",
                "kb_context": kb_context,
                "solutions_instructions": get_solutions_instructions(),
                "memory_context": "",
            })

            # 3. Classificacao automatica da resposta
            classe = classificar(resposta, artigos)
            salvar_resposta(
                caso_id, run, consulta, esperado, artigos, resposta
            )

            recuperados = "; ".join(artigos) or "(nenhum)"
            out(f"{caso_id} | {run} | {esperado} | {recuperados} | {classe}")


def main():
    ctx = AppContext()
    ctx.initialize()
    try:
        avaliar_fluxo(ctx)
    finally:
        ctx.shutdown()

    caminho = os.path.join(RESULTADOS_DIR, "relatorio_fluxo.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(LINHAS) + "\n")
    print(f"\nRelatorio salvo em {caminho}", flush=True)


if __name__ == "__main__":
    main()
