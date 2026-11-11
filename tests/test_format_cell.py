"""Testes da formatação de células do resultado das consultas SQL."""

import datetime as dt

from glpi_sql_ai.chains import _format_cell


def test_valor_nulo_vira_nd():
    assert _format_cell(None) == "N/D"


def test_data_e_hora_ficam_legiveis():
    assert _format_cell(dt.datetime(2026, 11, 10, 14, 5, 59)) == "2026-11-10 14:05"


def test_data_sem_hora():
    assert _format_cell(dt.date(2026, 11, 10)) == "2026-11-10"


def test_entidades_html_sao_decodificadas():
    assert _format_cell("Suporte &amp; Redes") == "Suporte & Redes"


def test_numeros_viram_texto():
    assert _format_cell(16) == "16"
