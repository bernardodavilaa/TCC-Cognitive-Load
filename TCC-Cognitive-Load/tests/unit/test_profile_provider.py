"""Unit: services.profile_provider.build_interim_profile (função pura, offline)."""

import pytest

from services.profile_provider import build_interim_profile

pytestmark = pytest.mark.unit


def test_normaliza_campos_basicos():
    profile = build_interim_profile("técnicas", "detalhadas", "  futebol, games  ", "sim", 4)
    assert profile == {
        "learning_style": "técnicas",
        "detail_level": "detalhadas",
        "hobbies": "futebol, games",
        "prior_experience": "sim",
        "self_rating": 4,
    }


def test_self_rating_ausente_vira_none():
    assert build_interim_profile("simples", "curtas", "", None, None)["self_rating"] is None
    assert build_interim_profile("simples", "curtas", "", None, "")["self_rating"] is None


def test_self_rating_aceita_string_numerica():
    assert build_interim_profile("simples", "curtas", "", "sim", "3")["self_rating"] == 3


def test_self_rating_invalido_vira_none():
    assert build_interim_profile("simples", "curtas", "", "sim", "abc")["self_rating"] is None


def test_self_rating_e_limitado_a_1_5():
    assert build_interim_profile("simples", "curtas", "", "sim", 0)["self_rating"] == 1
    assert build_interim_profile("simples", "curtas", "", "sim", 99)["self_rating"] == 5


def test_campos_none_viram_string_vazia():
    profile = build_interim_profile(None, None, None, None, None)
    assert profile["learning_style"] == ""
    assert profile["detail_level"] == ""
    assert profile["hobbies"] == ""
    assert profile["prior_experience"] == ""
