"""Unit: services.page_prompt_builder.build_page_messages (função pura, offline)."""

import pytest

from services.page_prompt_builder import (
    _describe_udl_format,
    _describe_zpd_support,
    _infer_bloom_level,
    build_page_messages,
)

pytestmark = pytest.mark.unit


def _profile(**over):
    base = {
        "learning_style": "simples",
        "detail_level": "detalhadas",
        "hobbies": "futebol",
        "prior_experience": "um pouco",
        "self_rating": 3,
    }
    base.update(over)
    return base


def test_retorna_messages_system_e_user():
    out = build_page_messages("Uma variável guarda um valor.", _profile(), subject="Algoritmos")
    assert len(out) == 2
    assert out[0]["role"] == "system"
    assert out[1]["role"] == "user"


def test_resposta_original_preservada_no_user():
    out = build_page_messages("TEXTO_BASE_UNICO", _profile())
    assert "TEXTO_BASE_UNICO" in out[1]["content"]


def test_subject_incluido_no_system():
    out = build_page_messages("x", _profile(), subject="Ponteiros em C")
    assert "Ponteiros em C" in out[0]["content"]


def test_hobbies_incluidos_quando_presentes():
    out = build_page_messages("x", _profile(hobbies="música, games"))
    assert "música, games" in out[0]["content"]


def test_hobbies_ausentes_usa_fallback_generico():
    out = build_page_messages("x", _profile(hobbies=""))
    assert "não declarou interesses específicos" in out[0]["content"]


def test_profile_none_nao_quebra():
    out = build_page_messages("x", None)
    assert len(out) == 2
    assert "não declarou interesses específicos" in out[0]["content"]


# --- Taxonomia de Bloom -----------------------------------------------------

def test_bloom_iniciante_sem_contato_previo():
    assert "lembrar e compreender" in _infer_bloom_level("não", None)


def test_bloom_autoavaliacao_baixa_forca_iniciante():
    assert "lembrar e compreender" in _infer_bloom_level("sim", 1)


def test_bloom_avancado_exige_contato_previo_e_nota_alta():
    assert "aplicar e analisar" in _infer_bloom_level("sim", 5)


def test_bloom_default_intermediario():
    assert "compreender e aplicar" in _infer_bloom_level(None, None)
    assert "compreender e aplicar" in _infer_bloom_level("um pouco", 3)


# --- ZPD ---------------------------------------------------------------------

def test_zpd_suporte_alto_quando_nota_baixa_ou_ausente():
    assert "bastante suporte" in _describe_zpd_support(2)
    assert "bastante suporte" in _describe_zpd_support(None)


def test_zpd_suporte_minimo_quando_nota_alta():
    assert "suporte mínimo" in _describe_zpd_support(5)


def test_zpd_suporte_moderado_no_meio():
    assert "suporte moderado" in _describe_zpd_support(3)


# --- UDL -----------------------------------------------------------------

def test_udl_tecnica_vs_simples():
    assert "linguagem técnica" in _describe_udl_format("técnicas", "detalhadas")
    assert "linguagem simples" in _describe_udl_format("simples", "detalhadas")


def test_udl_curtas_vs_detalhadas():
    assert "direto e conciso" in _describe_udl_format("simples", "curtas")
    assert "passo a passo" in _describe_udl_format("simples", "detalhadas")
