"""Integração: avaliação pós-chat do aluno (escala de Paas + Likert, Supabase real)."""

import pytest

from services.supabase_client import create_session_evaluation

pytestmark = pytest.mark.integration


@pytest.fixture
def eval_student(cfg, entities):
    row = entities.make_user(role="student")
    return row["id"]


def test_create_session_evaluation(cfg, sb_client, eval_student):
    student_id = eval_student

    created = create_session_evaluation(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_EVALUATIONS_TABLE,
        chat_id=None,
        student_id=student_id,
        classroom_id=None,
        page_enabled=True,
        paas_score=7,
        utilidade=4,
        exemplos=5,
        qualidade=4,
        nps=5,
        comentario="Gostei bastante!",
    )
    assert created["student_id"] == student_id

    rows = (
        sb_client.table(cfg.SUPABASE_EVALUATIONS_TABLE)
        .select("*")
        .eq("student_id", student_id)
        .execute()
        .data
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["page_enabled"] is True
    assert row["paas_score"] == 7
    assert row["utilidade"] == 4
    assert row["exemplos"] == 5
    assert row["qualidade"] == 4
    assert row["nps"] == 5
    assert row["comentario"] == "Gostei bastante!"

    sb_client.table(cfg.SUPABASE_EVALUATIONS_TABLE).delete().eq(
        "id", row["id"]
    ).execute()


def test_create_session_evaluation_comentario_opcional(cfg, sb_client, eval_student):
    student_id = eval_student

    created = create_session_evaluation(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_EVALUATIONS_TABLE,
        chat_id=None,
        student_id=student_id,
        classroom_id=None,
        page_enabled=False,
        paas_score=3,
        utilidade=2,
        exemplos=2,
        qualidade=3,
        nps=2,
    )
    assert created["comentario"] is None

    sb_client.table(cfg.SUPABASE_EVALUATIONS_TABLE).delete().eq(
        "id", created["id"]
    ).execute()
