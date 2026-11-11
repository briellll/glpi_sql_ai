"""Testes da extração do número do chamado a partir da pergunta do usuário."""

import pytest

from glpi_sql_ai.services import extract_ticket_id


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        ("soluções para o chamado 10367", "10367"),
        ("como resolver o chamado #123?", "123"),
        ("me dê ideias para o ticket 789", "789"),
        ("detalhes do chamado nº 45", "45"),
        ("ID 7", "7"),
        ("Soluções para o CHAMADO 99999", "99999"),
    ],
)
def test_extrai_o_numero_do_chamado(pergunta, esperado):
    assert extract_ticket_id(pergunta) == esperado


@pytest.mark.parametrize(
    "pergunta",
    [
        "soluções para o chamado",       # sem número (CT23)
        "soluções para o chamado abc",   # identificador não numérico (CT24)
        "o david 45 abriu um chamado",   # 'id' dentro de outra palavra não conta
        "",
    ],
)
def test_sem_numero_valido_retorna_none(pergunta):
    assert extract_ticket_id(pergunta) is None
