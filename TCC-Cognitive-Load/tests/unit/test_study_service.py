"""Unit: funções puras de services.supabase.study (sem I/O)."""

import pytest

from services.supabase.study import classify_message, classify_stratum

pytestmark = pytest.mark.unit


# -------------------- classify_stratum (RF-A2) --------------------

def test_classify_stratum_nenhuma_experiencia():
    assert classify_stratum("Não", "Não") == "nenhuma"


@pytest.mark.parametrize(
    "e1,e3",
    [
        ("Um pouco", "Não"),
        ("Sim", "Não"),
        ("Não", "Sim"),
        ("Sim", "Sim"),
    ],
)
def test_classify_stratum_alguma_experiencia(e1, e3):
    assert classify_stratum(e1, e3) == "alguma"


def test_classify_stratum_case_insensitive():
    assert classify_stratum("não", "não") == "nenhuma"


# -------------------- classify_message (RF-B5, heurística) --------------------

def test_classify_message_curta_vira_outra():
    assert classify_message("ok") == "outra"
    assert classify_message("obrigado!") == "outra"
    assert classify_message("") == "outra"


def test_classify_message_longa_vira_teorica():
    assert classify_message("O que é um loop for e quando devo usar ele?") == "teorica"


def test_classify_message_respeita_min_words_customizado():
    assert classify_message("uma duas tres quatro", min_words=3) == "teorica"
    assert classify_message("uma duas", min_words=3) == "outra"
