"""Integração: Modo Estudo — alocação balanceada por aluno (Supabase real).

Cobre os critérios de aceite 1 (balanceamento), 2 (idempotência) e a
imutabilidade de grupo/estrato reforçada por trigger no banco (RI-1).
"""

import pytest

from services.supabase_client import (
    allocate_participant,
    create_study_config,
    fetch_balance_report,
    fetch_participant_by_student,
    generate_allocation_blocks,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def study_room(cfg, entities):
    teacher = entities.make_user(role="teacher")
    classroom = entities.make_classroom(teacher["id"], study_mode=True)
    config = create_study_config(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom_id=classroom["id"], seed=42
    )
    generate_allocation_blocks(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        classroom_id=classroom["id"],
        config_version=config["version"],
        seed=config["random_seed"],
        n_blocks_per_stratum=6,
    )
    return classroom["id"], config["version"]


def test_allocate_participant_is_idempotent(cfg, entities, study_room):
    classroom_id, config_version = study_room
    student = entities.make_user(role="student")

    first = allocate_participant(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        student_id=student["id"],
        classroom_id=classroom_id,
        config_version=config_version,
        e1_contato_previo="Não",
        e2_nivel_atual=2,
        e3_ja_cursou="Não",
    )
    second = allocate_participant(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        student_id=student["id"],
        classroom_id=classroom_id,
        config_version=config_version,
        e1_contato_previo="Sim",  # mudar as respostas não deve mudar a alocação
        e2_nivel_atual=5,
        e3_ja_cursou="Sim",
    )
    assert first["id"] == second["id"]
    assert first["group_name"] == second["group_name"]
    assert first["stratum"] == "nenhuma"  # respeita a 1ª resposta (Não/Não)

    entities.on_cleanup(
        lambda: entities.sb.table("study_participants").delete().eq("id", first["id"]).execute()
    )


def test_allocation_is_balanced_within_stratum(cfg, entities, study_room):
    classroom_id, config_version = study_room
    created_ids = []
    for _ in range(8):
        student = entities.make_user(role="student")
        participant = allocate_participant(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            student_id=student["id"],
            classroom_id=classroom_id,
            config_version=config_version,
            e1_contato_previo="Não",
            e2_nivel_atual=1,
            e3_ja_cursou="Não",
        )
        created_ids.append(participant["id"])

    report = fetch_balance_report(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom_id)
    counts = {row["group_name"]: row["count"] for row in report if row["stratum"] == "nenhuma"}
    assert counts["controle"] + counts["experimental"] == 8
    assert abs(counts["controle"] - counts["experimental"]) <= 1

    for pid in created_ids:
        entities.sb.table("study_participants").delete().eq("id", pid).execute()


def test_group_is_immutable_at_db_level(cfg, entities, study_room):
    classroom_id, config_version = study_room
    student = entities.make_user(role="student")
    participant = allocate_participant(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        student_id=student["id"],
        classroom_id=classroom_id,
        config_version=config_version,
        e1_contato_previo="Não",
        e2_nivel_atual=1,
        e3_ja_cursou="Não",
    )
    entities.on_cleanup(
        lambda: entities.sb.table("study_participants").delete().eq("id", participant["id"]).execute()
    )

    flipped = "experimental" if participant["group_name"] == "controle" else "controle"
    with pytest.raises(Exception):
        entities.sb.table("study_participants").update({"group_name": flipped}).eq(
            "id", participant["id"]
        ).execute()


def test_allocation_exhausted_blocks_returns_none(cfg, entities):
    """RF-A9: blocos esgotados não alocam por padrão, nem travam o chamador."""
    teacher = entities.make_user(role="teacher")
    classroom = entities.make_classroom(teacher["id"], study_mode=True)
    config = create_study_config(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom_id=classroom["id"], seed=7
    )
    generate_allocation_blocks(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        classroom_id=classroom["id"],
        config_version=config["version"],
        seed=config["random_seed"],
        n_blocks_per_stratum=1,  # só 2 vagas no estrato "nenhuma"
    )

    created_ids = []
    for _ in range(2):
        student = entities.make_user(role="student")
        p = allocate_participant(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            student_id=student["id"],
            classroom_id=classroom["id"],
            config_version=config["version"],
            e1_contato_previo="Não",
            e2_nivel_atual=1,
            e3_ja_cursou="Não",
        )
        created_ids.append(p["id"])

    overflow_student = entities.make_user(role="student")
    with pytest.raises(Exception):
        allocate_participant(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            student_id=overflow_student["id"],
            classroom_id=classroom["id"],
            config_version=config["version"],
            e1_contato_previo="Não",
            e2_nivel_atual=1,
            e3_ja_cursou="Não",
        )

    for pid in created_ids:
        entities.sb.table("study_participants").delete().eq("id", pid).execute()
