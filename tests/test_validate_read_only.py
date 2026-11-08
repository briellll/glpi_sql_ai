"""Testes do validador de consultas somente leitura (chains.validate_read_only).

Uso:
    poetry run python -m pytest tests -q
"""

import re

import pytest

from glpi_sql_ai.chains import validate_read_only
from glpi_sql_ai.prompts import get_system_instructions

PERMITIDAS = [
    "SELECT COUNT(*) FROM glpi_tickets WHERE status IN (1,2,4)",
    "select id, name from glpi_tickets where entities_id = 1 and is_deleted = 0;",
    "SELECT l.name, COUNT(t.id) AS total FROM glpi_tickets AS t JOIN glpi_locations AS l "
    "ON t.locations_id = l.id WHERE t.entities_id = 1 AND t.is_deleted = 0 "
    "GROUP BY l.name ORDER BY total DESC LIMIT 3",
    "SELECT CONCAT(u.firstname, ' ', u.realname) AS tecnico, COUNT(*) FROM glpi_tickets t "
    "JOIN glpi_tickets_users tu ON tu.tickets_id = t.id AND tu.type = 2 "
    "JOIN glpi_users u ON u.id = tu.users_id WHERE CONCAT(u.firstname,' ',u.realname) LIKE '%Ana%' "
    "GROUP BY tecnico",
    "SELECT * FROM glpi_tickets WHERE DATE(date_creation) = CURDATE()",
    "SELECT * FROM glpi_tickets WHERE MONTH(date_creation) = MONTH(NOW()) "
    "AND YEAR(date_creation) = YEAR(NOW()) AND status = 5",
    "SELECT * FROM glpi_tickets WHERE time_to_resolve < NOW() AND date_creation >= '2026-01-01 00:00:00'",
    "WITH abertos AS (SELECT id FROM glpi_tickets WHERE status = 1) SELECT COUNT(*) FROM abertos",
    "SELECT id FROM glpi_tickets WHERE status = 1 UNION SELECT id FROM glpi_tickets WHERE status = 2",
]

RECUSADAS = [
    "DELETE FROM glpi_tickets WHERE id = 10367",
    "UPDATE glpi_tickets SET status = 6 WHERE id = 10367",
    "INSERT INTO glpi_tickets (name) VALUES ('x')",
    "DROP TABLE glpi_tickets",
    "TRUNCATE TABLE glpi_tickets",
    "CREATE TABLE teste (id INT)",
    "ALTER TABLE glpi_tickets ADD COLUMN x INT",
    "GRANT ALL ON *.* TO 'x'@'%'",
    "SELECT 1; DELETE FROM glpi_tickets",
    "SELECT * FROM glpi_tickets INTO OUTFILE 'C:/tmp/dump.txt'",
    "REPLACE INTO glpi_tickets (id, name) VALUES (1, 'x')",
]


@pytest.mark.parametrize("sql", PERMITIDAS)
def test_consultas_de_leitura_sao_aceitas(sql):
    validate_read_only(sql)


@pytest.mark.parametrize("sql", RECUSADAS)
def test_comandos_de_escrita_sao_recusados(sql):
    with pytest.raises(ValueError):
        validate_read_only(sql)


def test_exemplos_sql_do_prompt_sao_aceitos():
    """Todo SQL de exemplo no prompt de sistema precisa passar no validador."""
    instrucoes = get_system_instructions()
    exemplos = re.findall(r"`(SELECT[^`]+)`", instrucoes)
    assert exemplos, "nenhum exemplo de SELECT encontrado no prompt"
    for sql in exemplos:
        validate_read_only(sql)
