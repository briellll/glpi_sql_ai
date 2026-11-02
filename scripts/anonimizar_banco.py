"""
Anonimizacao final do banco de testes do GLPI.

Remove dados pessoais e credenciais reais remanescentes (e-mails, telefones,
logins, LDAP, notificacoes, logs). Chamados e artigos da base de conhecimento
sao sinteticos e nao sao tocados.

Uso:
    poetry run python scripts/anonimizar_banco.py
"""

import mysql.connector

from rebuild_synthetic_data import DB, log

# usuarios de sistema do GLPI + usuario da API do sistema
PRESERVAR = (2, 3, 4, 5, 6)
EXCLUSAO = "id NOT IN (" + ",".join(str(i) for i in PRESERVAR) + ") AND name <> 'api'"

TABELAS_CONTATO = [
    "glpi_computers",
    "glpi_monitors",
    "glpi_peripherals",
    "glpi_printers",
    "glpi_phones",
    "glpi_networkequipments",
    "glpi_plugin_printercounters_snmpsets",
]

TABELAS_TRUNCATE = [
    "glpi_queuednotifications",
    "glpi_events",
    "glpi_logs",
    "glpi_crontasklogs",
    "glpi_ticketsatisfactions",
    "glpi_plugin_satisfaction_surveyanswers",
    "glpi_documents",
    "glpi_documents_items",
    "glpi_notepads",
    "glpi_reminders",
    "glpi_problems",
    "glpi_problems_tickets",
    "glpi_projects",
    "glpi_projecttasks",
]


def aplicar(c, rotulo, sql):
    try:
        c.execute(sql)
        log(f"  {rotulo}")
    except Exception as e:
        log(f"  (skip {rotulo}: {e})")


def contar(c, rotulo, sql):
    try:
        c.execute(sql)
        log(f"  {rotulo}: {c.fetchone()[0]}")
    except Exception as e:
        log(f"  (skip {rotulo}: {e})")


def anonimizar():
    log("=" * 60)
    log("  Anonimizacao do banco de testes - GLPI SQL AI")
    log("=" * 60)

    cn = mysql.connector.connect(**DB)
    c = cn.cursor()
    c.execute("SET FOREIGN_KEY_CHECKS=0")

    # 1. usuarios: login, senha, LDAP, contatos e tokens
    log("\n[1] glpi_users")
    aplicar(
        c,
        "usuarios nao preservados anonimizados",
        "UPDATE glpi_users SET name = CONCAT('usuario', id), password = NULL, "
        "user_dn = NULL, registration_number = NULL, phone = '', phone2 = '', "
        "mobile = '', comment = NULL, personal_token = NULL, api_token = NULL "
        f"WHERE {EXCLUSAO}",
    )

    # 2. e-mails dos usuarios
    log("\n[2] glpi_useremails")
    aplicar(
        c,
        "emails substituidos por dominio de exemplo",
        "UPDATE glpi_useremails SET email = "
        "CONCAT('usuario', users_id, '@exemplo.example')",
    )

    # 3. e-mails de saida das entidades
    log("\n[3] glpi_entities")
    aplicar(
        c,
        "emails institucionais substituidos",
        "UPDATE glpi_entities SET admin_email = 'suporte@exemplo.example', "
        "from_email = 'suporte@exemplo.example', "
        "noreply_email = 'suporte@exemplo.example', "
        "replyto_email = 'suporte@exemplo.example', "
        "admin_email_name = 'Suporte TI', from_email_name = 'Suporte TI', "
        "noreply_email_name = 'Suporte TI', replyto_email_name = 'Suporte TI'",
    )

    # 4. campos de contato dos ativos
    log("\n[4] contatos dos ativos")
    for t in TABELAS_CONTATO:
        for col in ("contact", "contact_num"):
            aplicar(c, f"{t}.{col} = ''", f"UPDATE {t} SET {col} = ''")

    # 5. tabelas com dados pessoais ou historico
    log("\n[5] TRUNCATE")
    for t in TABELAS_TRUNCATE:
        try:
            c.execute(f"TRUNCATE TABLE {t}")
            log(f"  TRUNCATE {t}")
        except Exception as e:
            log(f"  (skip {t}: {e})")

    # 6. credenciais e notificacoes
    log("\n[6] credenciais")
    aplicar(
        c,
        "LDAP desativado e sem credenciais",
        "UPDATE glpi_authldaps SET rootdn = '', rootdn_passwd = '', is_active = 0",
    )
    aplicar(
        c,
        "senhas de smtp/proxy removidas",
        "UPDATE glpi_configs SET value = '' WHERE name IN "
        "('smtp_passwd','smtp_username','proxy_passwd','proxy_user')",
    )
    aplicar(
        c,
        "notificacoes desativadas",
        "UPDATE glpi_configs SET value = '0' WHERE name = 'use_notifications'",
    )

    # 6b. e-mails institucionais restantes (configuracao, tags e modelos)
    aplicar(
        c,
        "emails de configuracao substituidos",
        "UPDATE glpi_configs SET value = 'suporte@exemplo.example' WHERE name IN "
        "('admin_email','from_email','noreply_email','replyto_email','username') "
        "AND value LIKE '%@%'",
    )
    aplicar(
        c,
        "tag de assunto das notificacoes limpa",
        "UPDATE glpi_entities SET notification_subject_tag = '' "
        "WHERE notification_subject_tag LIKE '%@%'",
    )
    aplicar(
        c,
        "emails em modelos de acompanhamento substituidos",
        "UPDATE glpi_itilfollowuptemplates SET content = REGEXP_REPLACE(content, "
        "'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{2,}', 'suporte@exemplo.example')",
    )

    c.execute("SET FOREIGN_KEY_CHECKS=1")
    cn.commit()

    # 7. verificacao
    log("\n== VERIFICACAO ==")
    contar(
        c,
        "emails fora de '@exemplo.example'",
        "SELECT COUNT(*) FROM glpi_useremails "
        "WHERE email NOT LIKE '%@exemplo.example'",
    )
    contar(
        c,
        "usuarios com phone/phone2/mobile preenchido",
        "SELECT COUNT(*) FROM glpi_users "
        "WHERE phone <> '' OR phone2 <> '' OR mobile <> ''",
    )
    contar(
        c,
        "usuarios com user_dn preenchido",
        "SELECT COUNT(*) FROM glpi_users "
        "WHERE user_dn IS NOT NULL AND user_dn <> ''",
    )
    contar(c, "tickets (esperado 40)", "SELECT COUNT(*) FROM glpi_tickets")
    contar(
        c,
        "knowbaseitems (esperado 30)",
        "SELECT COUNT(*) FROM glpi_knowbaseitems",
    )

    c.close()
    cn.close()

    log("\nConcluido. Banco de testes anonimizado.")


if __name__ == "__main__":
    anonimizar()
