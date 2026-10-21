"""Integração: alocação sob concorrência REAL (threads paralelas), não só
sequencial. Cobre a preocupação da revisão: com o limite de fila do Gradio
subindo de 1 para 20, disputas por vaga passam a acontecer de verdade em
produção; aqui confirmamos que não duplicam nem corrompem o balanceamento.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from services.supabase_client import (
    allocate_participant,
    create_study_config,
    fetch_balance_report,
    generate_allocation_blocks,
)

pytestmark = pytest.mark.integration


def test_concurrent_allocation_same_stratum_stays_balanced(cfg, entities):
    teacher = entities.make_user(role="teacher")
    classroom = entities.make_classroom(teacher["id"], study_mode=True)
    config = create_study_config(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom_id=classroom["id"], seed=2026
    )
    generate_allocation_blocks(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        classroom_id=classroom["id"],
        config_version=config["version"],
        seed=config["random_seed"],
        n_blocks_per_stratum=10,
    )

    students = [entities.make_user(role="student") for _ in range(10)]

    def _allocate(student):
        return allocate_participant(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            student_id=student["id"],
            classroom_id=classroom["id"],
            config_version=config["version"],
            e1_contato_previo="Não",
            e2_nivel_atual=1,
            e3_ja_cursou="Não",
        )

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_allocate, s) for s in students]
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

    assert not errors, f"alocação concorrente falhou: {errors}"
    assert len(results) == 10

    # cada participante recebeu um block_id distinto (nenhuma vaga duplicada)
    block_ids = [r["block_id"] for r in results]
    assert len(set(block_ids)) == 10, "duas alocações reivindicaram o mesmo slot"

    # cada student_id só tem UM participante (idempotência também sob concorrência)
    student_ids = [r["student_id"] for r in results]
    assert len(set(student_ids)) == 10

    report = fetch_balance_report(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom["id"])
    counts = {row["group_name"]: row["count"] for row in report if row["stratum"] == "nenhuma"}
    assert counts["controle"] + counts["experimental"] == 10
    assert abs(counts["controle"] - counts["experimental"]) <= 1

    for r in results:
        entities.sb.table("study_participants").delete().eq("id", r["id"]).execute()
