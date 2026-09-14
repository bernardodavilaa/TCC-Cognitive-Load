"""Integração: registro/consulta de chats e acesso a materiais (camada student)."""

import time

import pytest

from services.supabase_client import (
    SupabaseOperationError,
    create_chat_record,
    create_classroom_record,
    fetch_student_document_metadata,
    list_student_chats,
)
from tests._helpers import tag

pytestmark = pytest.mark.integration


@pytest.fixture
def creds(cfg):
    return cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY


@pytest.fixture
def room_with_student(creds, sb_client, entities):
    url, key = creds
    owner = entities.make_user(role="teacher", extra="s_owner_")
    student = entities.make_user(role="student", extra="s_stud_")
    room = create_classroom_record(
        url, key, name=tag("sroom_"), description="pytest", theme_name="Recursão",
        theme_locked=False, created_by=owner["id"],
    )
    entities.on_cleanup(
        lambda: sb_client.table("classrooms").delete().eq("id", room["id"]).execute()
    )
    entities.enrol_student(room["id"], student["id"])
    return {"room": room, "student": student, "owner": owner}


def test_create_chat_record_and_list(creds, sb_client, room_with_student, entities):
    url, key = creds
    cid = room_with_student["room"]["id"]
    sid = room_with_student["student"]["id"]
    now = int(time.time())

    result = create_chat_record(
        url, key,
        student_id=sid, classroom_id=cid,
        started_at=now - 60, ended_at=now,
        chat_history=[{"role": "user", "content": "oi"}],
        storage_chat_id=tag("chat_"), storage_path_id=tag("chat_"),
        storage_bucket="chat-histories", storage_path="pytest/x.pdf",
        chat_title="Sessão pytest", subject_free_text="NONE",
        topic_source="Recursão", summary="Resumo pytest",
        subject_titles=["Recursão", "Casos base"],
        student_goal="revisar", student_interest="jogos",
        is_adhoc_chat=False, store_messages=False,
    )
    chat_id = result["chat"]["id"]
    entities.on_cleanup(
        lambda: sb_client.table("chats").delete().eq("id", chat_id).execute()
    )

    row = sb_client.table("chats").select("content,summary,topic_source").eq(
        "id", chat_id
    ).execute().data[0]
    assert row["summary"] == "Resumo pytest"
    assert row["content"]["subjects"] == ["Recursão", "Casos base"]
    assert row["content"]["student_goal"] == "revisar"
    assert row["content"]["bucket"] == "chat-histories"

    listed = list_student_chats(url, key, student_id=sid)
    assert any(c["id"] == chat_id for c in listed)


def test_document_access_control(creds, sb_client, room_with_student, entities):
    url, key = creds
    cid = room_with_student["room"]["id"]
    member = room_with_student["student"]
    outsider = entities.make_user(role="student", extra="out_")

    doc = sb_client.table("classroom_documents").insert(
        {
            "classroom_id": cid,
            "uploaded_by": room_with_student["owner"]["id"],
            "file_name": "material.pdf",
            "storage_path": "class-documents/pytest/material.pdf",
            "description": "pytest",
        }
    ).execute().data[0]
    entities.on_cleanup(
        lambda: sb_client.table("classroom_documents").delete().eq("id", doc["id"]).execute()
    )

    ok = fetch_student_document_metadata(
        url, key, student_id=member["id"], document_id=doc["id"]
    )
    assert ok["file_name"] == "material.pdf"

    with pytest.raises(SupabaseOperationError):
        fetch_student_document_metadata(
            url, key, student_id=outsider["id"], document_id=doc["id"]
        )
