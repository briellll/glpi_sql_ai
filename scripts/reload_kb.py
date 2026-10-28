"""
Recarrega SOMENTE a base de conhecimento do GLPI.

Substitui os artigos de glpi_knowbaseitems pelos 30 de KB_ARTICLES e reindexa
o ChromaDB. Chamados, usuarios e demais tabelas nao sao alterados.

Uso:
    poetry run python scripts/reload_kb.py
"""

import mysql.connector

from rebuild_synthetic_data import (
    DB,
    KB_ARTICLES,
    NOW,
    log,
    reindex_vector_store,
)

KB_TABLES = [
    "glpi_knowbaseitems",
    "glpi_knowbaseitems_profiles",
    "glpi_knowbaseitems_users",
    "glpi_knowbaseitemtranslations",
    "glpi_knowbaseitems_comments",
    "glpi_knowbaseitems_revisions",
]


def reload_kb():
    log("=" * 60)
    log("  Recarga da base de conhecimento - GLPI SQL AI")
    log("=" * 60)

    cn = mysql.connector.connect(**DB)
    c = cn.cursor()
    c.execute("SET FOREIGN_KEY_CHECKS=0")

    # limpa apenas as tabelas da KB
    for t in KB_TABLES:
        try:
            c.execute(f"TRUNCATE TABLE {t}")
            log(f"  TRUNCATE {t}")
        except Exception as e:
            log(f"  (skip {t}: {e})")

    # reinsere os artigos (mesmo INSERT da secao 4 de rebuild())
    author = 2
    data = NOW.strftime("%Y-%m-%d %H:%M:%S")
    for a in KB_ARTICLES:
        c.execute(
            "INSERT INTO glpi_knowbaseitems (name, answer, users_id, view, is_faq, "
            "date_creation, date_mod) VALUES (%s,%s,%s,1,1,%s,%s)",
            (a["name"], a["answer"], author, data, data),
        )
        kid = c.lastrowid
        c.execute("INSERT INTO glpi_knowbaseitems_profiles "
                  "(knowbaseitems_id, profiles_id, entities_id, is_recursive, no_entity_restriction) "
                  "VALUES (%s,4,1,0,0)", (kid,))
    log(f"  {len(KB_ARTICLES)} artigos de KB inseridos")

    c.execute("SET FOREIGN_KEY_CHECKS=1")
    cn.commit()

    # confirma que apenas a KB mudou
    def count(sql):
        c.execute(sql)
        return c.fetchone()[0]

    log("\n== RESUMO ==")
    log("  knowbaseitems:", count("SELECT COUNT(*) FROM glpi_knowbaseitems"))
    log("  tickets:", count("SELECT COUNT(*) FROM glpi_tickets"))

    c.close()
    cn.close()

    log("\nReindexando base vetorial...")
    reindex_vector_store()
    log("\nConcluido. Base de conhecimento recarregada.")


if __name__ == "__main__":
    reload_kb()
