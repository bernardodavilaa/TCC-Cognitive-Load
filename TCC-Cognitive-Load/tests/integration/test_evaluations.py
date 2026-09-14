"""Integração: comentários e avaliações automáticas de chat."""

import time

import pytest

from services.supabase_client import (
    SupabaseOperationError,
    add_chat_comment,
    create_chat_record,
    create_classroom_record,
    enrich_chats_with_evaluations,
    fetch_chat_evaluations_for_ids,
    fetch_latest_auto_evaluations,
    record_auto_chat_evaluation,
)
from tests._helpers import tag

pytestmark = pytest.mark.integration


@pytest.fixture
def creds(cfg):
    return cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY


@pytest.fixture
def chat(creds, sb_client, entities):
    url, key = creds
    owner = entities.make_user(role="teacher", extra="e_owner_")
    student = entities.make_user(role="student", extra="e_stud_")
    room = create_classroom_record(
        url, key, name=tag("eroom_"), description="pytest", theme_name="POO",
        theme_locked=False, created_by=owner["id"],
    )
    entities.on_cleanup(
        lambda: sb_client.table("classrooms").delete().eq("id", room["id"]).execute()
    )
    entities.enrol_student(room["id"], student["id"])
    now = int(time.time())
    res = create_chat_record(
        url, key, student_id=student["id"], classroom_id=room["id"],
        started_at=now - 30, ended_at=now, topic_source="POO",
        subject_free_text="NONE", subject_titles=["Herança"],
        is_adhoc_chat=False, store_messages=False,
    )
    chat_id = res["chat"]["id"]
    entities.on_cleanup(
        lambda: sb_client.table("chats").delete().eq("id", chat_id).execute()
    )
    return {"id": chat_id, "teacher": owner}


def test_add_chat_comment_valida_nota(creds, chat):
    url, key = creds
    with pytest.raises(SupabaseOperationError):
        add_chat_comment(
            url, key, chat_id=chat["id"], author_id=chat["teacher"]["id"],
            author_login="prof", author_name="Prof", text="ok", score="abc",
        )

    entry = add_chat_comment(
        url, key, chat_id=chat["id"], author_id=chat["teacher"]["id"],
        author_login="prof", author_name="Prof", text="Bom progresso", score=82,
    )
    assert entry["text"] == "Bom progresso"
    assert entry["score"] == 82.0


def test_auto_evaluation_roundtrip(creds, sb_client, chat):
    url, key = creds
    # Espelha o que app/pages/history_shared.generate_auto_evaluation persiste:
    # o texto principal vai em extra_payload["overview"] (os leitores procuram essa chave).
    record_auto_chat_evaluation(
        url, key, chat_id=chat["id"],
        evaluation_text="Visão geral simulada.", evaluation_score=64.0,
        extra_payload={
            "overview": "Visão geral simulada.",
            "overallGrade": 64.0,
            "subjects": [{"subject": "Herança", "grade": 64, "comment": "ok"}],
        },
    )

    latest = fetch_latest_auto_evaluations(sb_client, [chat["id"]])
    assert chat["id"] in latest
    assert latest[chat["id"]]["overview"] == "Visão geral simulada."

    manual = fetch_chat_evaluations_for_ids(sb_client, [chat["id"]])
    assert isinstance(manual, dict)

    enriched = enrich_chats_with_evaluations(sb_client, [{"id": chat["id"]}])
    assert enriched[0]["auto_evaluation"] == "Visão geral simulada."
