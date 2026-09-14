"""Integração: operações de sala/membros/subtemas (camada admin) no Supabase real."""

import pytest

from services.supabase_client import (
    create_classroom_record,
    create_subject_record,
    delete_classroom_record,
    fetch_classroom_domain,
    list_all_chats,
    remove_classroom_student,
    remove_classroom_teacher,
    update_classroom_record,
    update_subject_active,
    upsert_classroom_student,
    upsert_classroom_teacher,
)
from tests._helpers import tag

pytestmark = pytest.mark.integration


@pytest.fixture
def creds(cfg):
    return cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY


@pytest.fixture
def classroom(creds, sb_client, entities):
    url, key = creds
    owner = entities.make_user(role="teacher", extra="owner_")
    row = create_classroom_record(
        url,
        key,
        name=tag("sala_"),
        description="pytest",
        theme_name="Estruturas de Dados",
        theme_locked=False,
        created_by=owner["id"],
    )
    entities.on_cleanup(
        lambda: sb_client.table("classrooms").delete().eq("id", row["id"]).execute()
    )
    return {"row": row, "owner": owner}


def test_create_update_delete_classroom(creds, sb_client):
    url, key = creds
    owner = (
        sb_client.table("users").select("id").eq("username", "professor").execute().data[0]
    )
    row = create_classroom_record(
        url,
        key,
        name=tag("crud_"),
        description="antes",
        theme_name="X",
        theme_locked=False,
        created_by=owner["id"],
    )
    try:
        update_classroom_record(url, key, row["id"], description="depois")
        got = sb_client.table("classrooms").select("description").eq(
            "id", row["id"]
        ).execute().data[0]
        assert got["description"] == "depois"
    finally:
        delete_classroom_record(url, key, row["id"])

    assert (
        sb_client.table("classrooms").select("id").eq("id", row["id"]).execute().data == []
    )


def test_teacher_membership(creds, sb_client, classroom, entities):
    url, key = creds
    cid = classroom["row"]["id"]
    teacher = entities.make_user(role="teacher", extra="cot_")

    upsert_classroom_teacher(url, key, classroom_id=cid, teacher_id=teacher["id"], role_label="co_teacher")
    rows = sb_client.table("classroom_teachers").select("*").eq("classroom_id", cid).eq(
        "teacher_id", teacher["id"]
    ).execute().data
    assert rows and rows[0]["role_label"] == "co_teacher"

    remove_classroom_teacher(url, key, classroom_id=cid, teacher_id=teacher["id"])
    assert (
        sb_client.table("classroom_teachers").select("*").eq("classroom_id", cid).eq(
            "teacher_id", teacher["id"]
        ).execute().data
        == []
    )


def test_student_membership_soft_and_hard_remove(creds, sb_client, classroom, entities):
    url, key = creds
    cid = classroom["row"]["id"]
    student = entities.make_user(role="student", extra="mem_")

    upsert_classroom_student(url, key, classroom_id=cid, student_id=student["id"])
    entities.on_cleanup(
        lambda: sb_client.table("classroom_students").delete().eq("classroom_id", cid).eq(
            "student_id", student["id"]
        ).execute()
    )

    remove_classroom_student(url, key, classroom_id=cid, student_id=student["id"])  # soft
    row = sb_client.table("classroom_students").select("status").eq("classroom_id", cid).eq(
        "student_id", student["id"]
    ).execute().data[0]
    assert row["status"] == "removed"

    remove_classroom_student(url, key, classroom_id=cid, student_id=student["id"], hard=True)
    assert (
        sb_client.table("classroom_students").select("*").eq("classroom_id", cid).eq(
            "student_id", student["id"]
        ).execute().data
        == []
    )


def test_subject_create_and_toggle_active(creds, sb_client, classroom):
    url, key = creds
    cid = classroom["row"]["id"]
    subject = create_subject_record(
        url, key, classroom_id=cid, name=tag("sub_"), created_by=classroom["owner"]["id"]
    )
    try:
        update_subject_active(url, key, subject_id=subject["id"], is_active=False)
        got = sb_client.table("classroom_subjects").select("is_active").eq(
            "id", subject["id"]
        ).execute().data[0]
        assert got["is_active"] is False
    finally:
        sb_client.table("classroom_subjects").delete().eq("id", subject["id"]).execute()


def test_fetch_classroom_domain_shape(creds, sb_client, classroom, entities):
    url, key = creds
    cid = classroom["row"]["id"]
    student = entities.make_user(role="student", extra="dom_")
    entities.enrol_student(cid, student["id"])

    classrooms, subjects_by_class = fetch_classroom_domain(url, key)
    mine = next((c for c in classrooms if c["id"] == cid), None)
    assert mine is not None
    for field in ("teachers", "students", "documents", "owner_login", "theme_name"):
        assert field in mine
    assert isinstance(subjects_by_class, dict)


def test_list_all_chats_returns_list(creds):
    url, key = creds
    chats = list_all_chats(url, key, limit=5)
    assert isinstance(chats, list)
