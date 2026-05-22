"""
Seed script para ambiente de teste controlado do GLPI SQL AI.

Cria chamados via SQL direto e artigos da base de conhecimento via SQL
(contornando a API do GLPI que derruba o MySQL com buffer pool de 16 MB).

Etapas:
  1. Validar dados de referencia existentes
  2. Inserir 7 chamados de teste (glpi_tickets + glpi_tickets_users)
  3. Inserir 6 artigos da KB (glpi_knowbaseitems + glpi_knowbaseitems_profiles)
  4. Reindexar base vetorial via KBVectorStore
"""

import logging
import os
import sys
from datetime import datetime, timedelta

import mysql.connector
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

load_dotenv(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "glpidb"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "connection_timeout": 5,
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


# ============================================================
# ETAPA 1: Validar dados de referencia
# ============================================================

def validate_references(conn) -> dict:
    """Verifica se os dados de referencia necessarios existem."""
    c = conn.cursor()
    refs = {}

    queries = {
        "user_zilma": "SELECT id FROM glpi_users WHERE id = 8",
        "user_yasmin": "SELECT id FROM glpi_users WHERE id = 9",
        "user_yan": "SELECT id FROM glpi_users WHERE id = 10",
        "user_yago": "SELECT id FROM glpi_users WHERE id = 11",
        "user_william": "SELECT id FROM glpi_users WHERE id = 12",
        "user_weslley": "SELECT id FROM glpi_users WHERE id = 13",
        "user_welen": "SELECT id FROM glpi_users WHERE id = 14",
        "user_waneza": "SELECT id FROM glpi_users WHERE id = 15",
        "user_walter": "SELECT id FROM glpi_users WHERE id = 17",
        "user_vivaldo": "SELECT id FROM glpi_users WHERE id = 18",
        "user_vitoria": "SELECT id FROM glpi_users WHERE id = 19",
        "loc_apoio": "SELECT id FROM glpi_locations WHERE id = 6",
        "loc_cadastro": "SELECT id FROM glpi_locations WHERE id = 9",
        "loc_almox": "SELECT id FROM glpi_locations WHERE id = 4",
        "loc_admin": "SELECT id FROM glpi_locations WHERE id = 2",
        "loc_atend": "SELECT id FROM glpi_locations WHERE id = 7",
        "loc_audit": "SELECT id FROM glpi_locations WHERE id = 8",
        "cat_computador": "SELECT id FROM glpi_itilcategories WHERE id = 57",
        "cat_login": "SELECT id FROM glpi_itilcategories WHERE id = 52",
        "cat_multimidia": "SELECT id FROM glpi_itilcategories WHERE id = 58",
        "cat_email": "SELECT id FROM glpi_itilcategories WHERE id = 54",
        "cat_acesso_remoto": "SELECT id FROM glpi_itilcategories WHERE id = 50",
        "cat_telefonia": "SELECT id FROM glpi_itilcategories WHERE id = 56",
        "cat_certificado": "SELECT id FROM glpi_itilcategories WHERE id = 51",
        "entity_apoio": "SELECT id FROM glpi_entities WHERE id = 2",
    }

    missing = []
    for name, query in queries.items():
        c.execute(query)
        row = c.fetchone()
        if row:
            refs[name] = row[0]
        else:
            missing.append(name)
    c.close()

    if missing:
        logger.error("Dados de referencia faltando: %s", ", ".join(missing))
        sys.exit(1)

    logger.info("Referencias validadas: %d itens OK", len(refs))
    return refs


# ============================================================
# ETAPA 2: Criar chamados de teste
# ============================================================

def create_test_tickets(conn, refs: dict) -> list[int]:
    """Cria 7 chamados de teste e retorna os IDs."""
    c = conn.cursor()

    now = datetime.now()
    entity = refs["entity_apoio"]  # 2 = APOIO

    tickets = [
        {
            "name": "Computador extremamente lento ao iniciar",
            "content": "Usuario relata que o computador demora mais de 10 minutos para iniciar. "
                       "Ja foi feita limpeza de disco mas o problema persiste.",
            "status": 2,  # Em atendimento
            "priority": 3, "urgency": 3, "impact": 3,
            "itilcategories_id": refs["cat_computador"],
            "locations_id": refs["loc_apoio"],
            "requester": refs["user_zilma"],
            "technician": refs["user_yan"],
            "days_ago": 5,
        },
        {
            "name": "Usuario nao consegue fazer login no sistema",
            "content": "Usuario Yasmin reporta que ao tentar logar no sistema aparece "
                       "'credenciais invalidas'. Ja tentou resetar senha mas nao recebeu o email.",
            "status": 1,  # Novo
            "priority": 4, "urgency": 4, "impact": 3,
            "itilcategories_id": refs["cat_login"],
            "locations_id": refs["loc_cadastro"],
            "requester": refs["user_yasmin"],
            "technician": None,
            "days_ago": 2,
        },
        {
            "name": "Impressora nao conecta na rede",
            "content": "Impressora do almoxarifado esta offline. LED de rede piscando. "
                       "Tecnico ja verificou cabo de rede e switch.",
            "status": 3,  # Pendente
            "priority": 2, "urgency": 2, "impact": 2,
            "itilcategories_id": refs["cat_multimidia"],
            "locations_id": refs["loc_almox"],
            "requester": refs["user_yago"],
            "technician": refs["user_weslley"],
            "days_ago": 7,
        },
        {
            "name": "Servico de e-mail fora do ar para todo setor",
            "content": "Nenhum usuario do setor Apoio consegue acessar o Outlook. "
                       "Erro: 'O Microsoft Outlook nao pode ser iniciado'.",
            "status": 2,  # Em atendimento
            "priority": 5, "urgency": 5, "impact": 4,
            "itilcategories_id": refs["cat_email"],
            "locations_id": refs["loc_apoio"],
            "requester": refs["user_welen"],
            "technician": refs["user_william"],
            "days_ago": 1,
            "sla_breach": True,
        },
        {
            "name": "Acesso remoto VPN nao estabelece conexao",
            "content": "Usuario nao consegue conectar na VPN para trabalho remoto. "
                       "Token do VPN retorna erro de autenticacao.",
            "status": 5,  # Solucionado
            "priority": 3, "urgency": 3, "impact": 2,
            "itilcategories_id": refs["cat_acesso_remoto"],
            "locations_id": refs["loc_admin"],
            "requester": refs["user_vivaldo"],
            "technician": refs["user_walter"],
            "days_ago": 10,
        },
        {
            "name": "Ramal telefonico sem audio",
            "content": "Ramal 234 do setor de Atendimento esta mudo. "
                       "Tecnico trocou o aparelho e problema persiste.",
            "status": 6,  # Fechado
            "priority": 2, "urgency": 2, "impact": 1,
            "itilcategories_id": refs["cat_telefonia"],
            "locations_id": refs["loc_atend"],
            "requester": refs["user_vitoria"],
            "technician": refs["user_vivaldo"],
            "days_ago": 15,
        },
        {
            "name": "Certificado digital vencido - NF-e bloqueada",
            "content": "Certificado digital A1 do setor de Auditoria venceu ontem. "
                       "Notas fiscais eletronicas nao podem ser emitidas.",
            "status": 1,  # Novo
            "priority": 4, "urgency": 4, "impact": 4,
            "itilcategories_id": refs["cat_certificado"],
            "locations_id": refs["loc_audit"],
            "requester": refs["user_waneza"],
            "technician": None,
            "days_ago": 0,
        },
    ]

    inserted_ids = []
    for ticket in tickets:
        date_creation = now - timedelta(days=ticket["days_ago"])
        date_creation_str = date_creation.strftime("%Y-%m-%d %H:%M:%S")
        date_mod_str = (date_creation + timedelta(hours=ticket["days_ago"] * 2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # SLA breach flag (chamados atrasados)
        solve_delay_stat = 3600 if ticket.get("sla_breach") else 0
        takeintoaccount_delay_stat = 1800 if ticket.get("sla_breach") else 0

        c.execute(
            """INSERT INTO glpi_tickets
               (entities_id, name, content, status, priority, urgency, impact,
                itilcategories_id, locations_id, date_creation, date_mod,
                solve_delay_stat, takeintoaccount_delay_stat, is_deleted)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)""",
            (
                entity,
                ticket["name"],
                ticket["content"],
                ticket["status"],
                ticket["priority"],
                ticket["urgency"],
                ticket["impact"],
                ticket["itilcategories_id"],
                ticket["locations_id"],
                date_creation_str,
                date_mod_str,
                solve_delay_stat,
                takeintoaccount_delay_stat,
            ),
        )
        ticket_id = c.lastrowid

        # Vincula solicitante (type=1)
        c.execute(
            "INSERT INTO glpi_tickets_users (tickets_id, users_id, type) VALUES (%s, %s, 1)",
            (ticket_id, ticket["requester"]),
        )

        # Vincula tecnico (type=2), se houver
        if ticket.get("technician"):
            c.execute(
                "INSERT INTO glpi_tickets_users (tickets_id, users_id, type) VALUES (%s, %s, 2)",
                (ticket_id, ticket["technician"]),
            )

        inserted_ids.append(ticket_id)
        logger.info(
            "  Ticket #%d: '%s' [status=%d]",
            ticket_id, ticket["name"], ticket["status"],
        )

    conn.commit()
    c.close()
    logger.info("Total: %d chamados criados", len(inserted_ids))
    return inserted_ids


# ============================================================
# ETAPA 3: Criar artigos da base de conhecimento
# ============================================================

KB_ARTICLES = [
    {
        "name": "Computador lento - diagnostico e solucao",
        "answer": (
            "<p><strong>Procedimento para diagnosticar computador lento:</strong></p>"
            "<ol>"
            "<li>Verifique os programas que iniciam com o Windows (msconfig). Desabilite "
            "aplicativos desnecessarios.</li>"
            "<li>Execute o Gerenciador de Tarefas e verifique o uso de CPU, memoria e disco.</li>"
            "<li>Limpe arquivos temporarios com o utilitario Limpeza de Disco do Windows.</li>"
            "<li>Verifique se o antivirus esta executando varredura completa em horario comercial.</li>"
            "<li>Execute o comando <code>chkdsk /f</code> para verificar erros no disco.</li>"
            "<li>Caso a lentidao persista, considere upgrade de memoria RAM ou troca para SSD.</li>"
            "</ol>"
            "<p><em>Ref: Procedimento TI-SUP-001</em></p>"
        ),
    },
    {
        "name": "Reset de senha e desbloqueio de usuario",
        "answer": (
            "<p><strong>Procedimento para reset de senha:</strong></p>"
            "<ol>"
            "<li>Acesse o Active Directory (ADUC) com credenciais administrativas.</li>"
            "<li>Localize o usuario na OU correspondente ao setor.</li>"
            "<li>Clique com botao direito > Redefinir Senha.</li>"
            "<li>Informe uma senha temporaria seguindo a politica de senhas.</li>"
            "<li>Marque a opcao 'O usuario deve alterar a senha no proximo logon'.</li>"
            "<li>Se necessario, desbloqueie a conta em Account > Unlock Account.</li>"
            "<li>Orientar o usuario a acessar o portal de autoatendimento para trocas futuras.</li>"
            "</ol>"
            "<p><strong>Causas comuns de bloqueio:</strong> multiplas tentativas de senha incorreta, "
            "conta expirada, sincronizacao de senha entre sistemas.</p>"
        ),
    },
    {
        "name": "Impressora de rede - troubleshooting",
        "answer": (
            "<p><strong>Procedimento para solucionar problemas de impressora de rede:</strong></p>"
            "<ol>"
            "<li>Verifique se a impressora esta ligada e conectada ao ponto de rede. "
            "LED de rede deve estar aceso e estavel.</li>"
            "<li>Execute <code>ping</code> para o IP da impressora a partir do computador do usuario.</li>"
            "<li>Acesse a interface web da impressora para verificar status dos suprimentos "
            "e configuracoes de rede.</li>"
            "<li>Remova e reinstale a impressora no computador do usuario via Painel de Controle.</li>"
            "<li>Verifique a fila de impressao no servidor de impressao.</li>"
            "<li>Caso necessario, reinicie o servico Spooler de Impressao: "
            "<code>services.msc > Print Spooler > Reiniciar</code>.</li>"
            "</ol>"
            "<p><strong>Causas comuns:</strong> cabo de rede desconectado, IP conflitante, "
            "driver corrompido, fila de impressao travada.</p>"
        ),
    },
    {
        "name": "E-mail Outlook - problemas comuns e solucoes",
        "answer": (
            "<p><strong>Procedimento para solucionar problemas de e-mail/Outlook:</strong></p>"
            "<ol>"
            "<li>Verifique a conectividade de rede. O Outlook requer acesso ao servidor Exchange.</li>"
            "<li>Tente acessar o Outlook Web Access (OWA) via navegador para isolar o problema.</li>"
            "<li>Crie um novo perfil do Outlook: Painel de Controle > Mail > Mostrar Perfis > Adicionar.</li>"
            "<li>Limpe o cache de credenciais: Painel de Controle > Gerenciador de Credenciais > "
            "Remover credenciais do Windows relacionadas ao Outlook.</li>"
            "<li>Execute o Assistente de Reparacao do Office (Microsoft Support and Recovery Assistant).</li>"
            "<li>Como ultimo recurso, repare a instalacao do Office via Programas e Recursos.</li>"
            "</ol>"
            "<p><strong>Verificacao do servidor:</strong> confirmar se o servidor Exchange esta "
            "operacional e se ha espaco em disco suficiente no banco de dados de e-mails.</p>"
        ),
    },
    {
        "name": "Configuracao de VPN para acesso remoto",
        "answer": (
            "<p><strong>Procedimento para configurar e solucionar problemas de VPN:</strong></p>"
            "<ol>"
            "<li>Verifique se o cliente VPN (FortiClient/OpenVPN/AnyConnect) esta instalado "
            "e atualizado.</li>"
            "<li>Confirme as credenciais de acesso: usuario de rede + senha + token (se aplicavel).</li>"
            "<li>Verifique a URL ou IP do servidor VPN nas configuracoes do cliente.</li>"
            "<li>Teste a conectividade basica com <code>ping</code> para o servidor VPN.</li>"
            "<li>Verifique se o firewall local nao esta bloqueando a porta da VPN "
            "(geralmente UDP 443, 500 ou 4500).</li>"
            "<li>Sincronize o token RSA/SecurID caso esteja fora de sincronia.</li>"
            "<li>Reinicie o servico do cliente VPN e tente novamente.</li>"
            "</ol>"
            "<p><em>Em caso de falha persistente, abrir chamado para a equipe de Redes.</em></p>"
        ),
    },
    {
        "name": "Renovacao de certificado digital A1/A3",
        "answer": (
            "<p><strong>Procedimento para renovacao de certificado digital:</strong></p>"
            "<ol>"
            "<li>Identifique o tipo de certificado: A1 (arquivo) ou A3 (token/cartao).</li>"
            "<li>Acesse o site da Autoridade Certificadora (ex: Serasa, Certisign, "
            "ICP-Brasil) com o token conectado.</li>"
            "<li>No portal, localize a opcao 'Renovar Certificado' e siga o assistente.</li>"
            "<li>Sera necessario validar a identidade por videoconferencia ou presencialmente "
            "(dependendo da AC).</li>"
            "<li>Apos aprovacao, faca o download do novo certificado e instale no repositorio "
            "do Windows.</li>"
            "<li>Atualize a cadeia de certificados (ICP-Brasil) se necessario.</li>"
            "<li>Teste a emissao de uma NF-e de homologacao para validar.</li>"
            "</ol>"
            "<p><strong>Atencao:</strong> certificados A1 tem validade de 1 ano. "
            "Programe a renovacao com pelo menos 30 dias de antecedencia.</p>"
            "<p><em>Contato do suporte da AC: disponivel na intranet.</em></p>"
        ),
    },
]


def create_kb_articles(conn, refs: dict) -> list[int]:
    """Cria artigos da base de conhecimento diretamente no banco."""
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Usa o primeiro usuario admin disponivel como autor dos artigos
    c.execute(
        "SELECT id FROM glpi_users WHERE name = 'glpi' AND is_active = 1 AND is_deleted = 0 LIMIT 1"
    )
    admin_row = c.fetchone()
    author_id = admin_row[0] if admin_row else 2  # fallback: glpi user (id=2)

    inserted_ids = []

    for article in KB_ARTICLES:
        c.execute(
            """INSERT INTO glpi_knowbaseitems
               (name, answer, users_id, view, is_faq,
                date_creation, date_mod)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                article["name"],
                article["answer"],
                author_id,
                1,  # view (visibilidade)
                1,  # is_faq
                now,
                now,
            ),
        )
        article_id = c.lastrowid

        # Vincula ao perfil Super-Admin (id=4) na entidade APOIO (id=2)
        c.execute(
            """INSERT INTO glpi_knowbaseitems_profiles
               (knowbaseitems_id, profiles_id, entities_id, is_recursive,
                no_entity_restriction)
               VALUES (%s, %s, %s, %s, %s)""",
            (article_id, 4, refs["entity_apoio"], 0, 0),
        )

        inserted_ids.append(article_id)
        logger.info("  Artigo KB #%d: '%s'", article_id, article["name"])

    conn.commit()
    c.close()
    logger.info("Total: %d artigos criados", len(inserted_ids))
    return inserted_ids


# ============================================================
# ETAPA 4: Reindexar base vetorial
# ============================================================

def sync_vector_store(article_ids: list[int]):
    """Indexa os artigos criados diretamente no ChromaDB via leitura do banco."""
    from glpi_sql_ai.config import AppContext

    logger.info("Reindexando base vetorial...")
    ctx = AppContext()
    ctx.initialize()

    if not ctx.vector_store:
        logger.warning("VectorStore indisponivel. Pulando sync vetorial.")
        return

    # Lendo artigos diretamente do banco (bypass GLPI API)
    conn = get_conn()
    c = conn.cursor()
    placeholders = ", ".join(["%s"] * len(article_ids))
    c.execute(
        f"SELECT id, name, answer FROM glpi_knowbaseitems WHERE id IN ({placeholders})",
        tuple(article_ids),
    )
    rows = c.fetchall()
    conn.close()

    articles = [
        {"id": row[0], "name": row[1] or "", "answer": row[2] or ""}
        for row in rows
    ]

    if not articles:
        logger.warning("Nenhum artigo encontrado para indexar.")
        return

    count = ctx.vector_store.index_articles(articles)
    logger.info("Base vetorial sincronizada: %d artigos indexados.", count)


# ============================================================
# MAIN
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("  GLPI SQL AI - Seed de ambiente de teste")
    logger.info("=" * 60)

    conn = get_conn()
    logger.info("MySQL conectado: %s@%s/%s",
                DB_CONFIG["user"], DB_CONFIG["host"], DB_CONFIG["database"])

    try:
        # Etapa 1
        refs = validate_references(conn)

        # Etapa 2
        ticket_ids = create_test_tickets(conn, refs)

        # Etapa 3
        article_ids = create_kb_articles(conn, refs)

    finally:
        conn.close()

    # Etapa 4 (opcional, precisa do OPENAI_API_KEY)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            sync_vector_store(article_ids)
        except Exception as e:
            logger.warning("Falha na sincronizacao vetorial: %s", e)
    else:
        logger.warning("OPENAI_API_KEY nao configurada. Pulando sync vetorial.")

    logger.info("=" * 60)
    logger.info("Seed concluido!")
    logger.info("  Chamados criados: %s", ticket_ids)
    logger.info("  Artigos KB criados: %s", article_ids)
    logger.info("  Execute: poetry run python -m glpi_sql_ai.main")
    logger.info("  E teste perguntas como:")
    logger.info("    - quantos chamados atrasados existem?")
    logger.info("    - solucoes para o chamado %d", ticket_ids[0])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
