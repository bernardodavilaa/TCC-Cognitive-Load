"""Integração: perfil cognitivo-afetivo do aluno (Supabase real)."""

import pytest

from services.supabase_client import fetch_student_profile, upsert_student_profile
from tests._helpers import tag

pytestmark = pytest.mark.integration


@pytest.fixture
def profile_student(cfg, entities):
    row = entities.make_user(role="student")
    return row["id"]


def test_upsert_e_fetch_perfil(cfg, profile_student):
    student_id = profile_student

    upsert_student_profile(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_PROFILE_TABLE,
        student_id,
        curso_periodo="Ciência da Computação, 2º período",
        contato_previo="não",
        interesses="futebol, games",
        estilo_preferido="simples",
        detalhamento_preferido="detalhadas",
        autoavaliacao=2,
    )

    profile = fetch_student_profile(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, cfg.SUPABASE_PROFILE_TABLE, student_id
    )
    assert profile is not None
    assert profile["curso_periodo"] == "Ciência da Computação, 2º período"
    assert profile["contato_previo"] == "não"
    assert profile["interesses"] == "futebol, games"
    assert profile["estilo_preferido"] == "simples"
    assert profile["detalhamento_preferido"] == "detalhadas"
    assert profile["autoavaliacao"] == 2


def test_upsert_atualiza_sem_duplicar(cfg, sb_client, profile_student):
    student_id = profile_student

    upsert_student_profile(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_PROFILE_TABLE,
        student_id,
        interesses="música",
        autoavaliacao=1,
    )
    upsert_student_profile(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_PROFILE_TABLE,
        student_id,
        interesses="música, xadrez",
        autoavaliacao=4,
    )

    rows = (
        sb_client.table(cfg.SUPABASE_PROFILE_TABLE)
        .select("*")
        .eq("student_id", student_id)
        .execute()
        .data
    )
    assert len(rows) == 1
    assert rows[0]["interesses"] == "música, xadrez"
    assert rows[0]["autoavaliacao"] == 4


def test_upsert_e_fetch_interesses_estruturado(cfg, profile_student):
    student_id = profile_student
    estruturado = [
        {"tema": "Esportes", "detalhe": "jogo vôlei nos fins de semana"},
        {"tema": "Música", "detalhe": ""},
    ]

    upsert_student_profile(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_PROFILE_TABLE,
        student_id,
        interesses="Esportes (jogo vôlei nos fins de semana); Música",
        interesses_estruturado=estruturado,
    )

    profile = fetch_student_profile(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, cfg.SUPABASE_PROFILE_TABLE, student_id
    )
    assert profile["interesses_estruturado"] == estruturado


def test_fetch_perfil_inexistente(cfg):
    assert (
        fetch_student_profile(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            cfg.SUPABASE_PROFILE_TABLE,
            "00000000-0000-0000-0000-000000000000",
        )
        is None
    )
