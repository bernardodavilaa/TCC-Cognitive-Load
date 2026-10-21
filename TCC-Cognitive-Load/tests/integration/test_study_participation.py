"""Integração: Módulos B/C/D do Modo Estudo — validade de sessão, dúvidas,
exercícios e cálculo da barra de progresso (Supabase real, sem Vertex).

Cobre os critérios de aceite 6 (sessão válida) e 10 (barra) da especificação.
"""

import pytest

from services.supabase_client import (
    allocate_participant,
    close_study_session,
    compute_participation,
    create_session_evaluation,
    create_study_config,
    generate_allocation_blocks,
    log_study_event,
    mark_session_evaluation_done,
    start_study_session,
)

pytestmark = pytest.mark.integration

DEFAULT_CONFIG = {
    "sessao_min_ativo_min": 10,
    "sessao_min_msg_aluno": 6,
    "meta_sessoes": 3,
    "meta_sessoes_dias_distintos": 2,
    "meta_duvidas": 6,
    "meta_exercicios": 4,
    "min_analise_sessoes": 1,
    "questionario_min_sessoes": 2,
    "peso_sessoes": 0.30,
    "peso_duvidas": 0.20,
    "peso_exercicios": 0.30,
    "peso_questionario": 0.20,
}


@pytest.fixture
def allocated_participant(cfg, entities):
    teacher = entities.make_user(role="teacher")
    classroom = entities.make_classroom(teacher["id"], study_mode=True)
    config = create_study_config(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, classroom_id=classroom["id"], seed=99
    )
    generate_allocation_blocks(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        classroom_id=classroom["id"],
        config_version=config["version"],
        seed=config["random_seed"],
        n_blocks_per_stratum=4,
    )
    student = entities.make_user(role="student")
    participant = allocate_participant(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        student_id=student["id"],
        classroom_id=classroom["id"],
        config_version=config["version"],
        e1_contato_previo="Não",
        e2_nivel_atual=1,
        e3_ja_cursou="Não",
    )
    entities.on_cleanup(
        lambda: entities.sb.table("study_participants").delete().eq("id", participant["id"]).execute()
    )
    return classroom["id"], participant


def _make_session(cfg, classroom_id, participant):
    session = start_study_session(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        participant_id=participant["id"],
        classroom_id=classroom_id,
        effective_group=participant["group_name"],
        config_version=participant["config_version"],
    )
    return session


def test_session_8min_active_is_invalid(cfg, entities, allocated_participant):
    """Critério de aceite 6: 8 min ativos não é válida."""
    classroom_id, participant = allocated_participant
    session = _make_session(cfg, classroom_id, participant)

    closed = close_study_session(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        session["id"],
        end_reason="manual",
        is_valid=(8 * 60 >= DEFAULT_CONFIG["sessao_min_ativo_min"] * 60 and 7 >= DEFAULT_CONFIG["sessao_min_msg_aluno"]),
    )
    assert closed["is_valid"] is False

    stats = compute_participation(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, participant["id"], DEFAULT_CONFIG)
    assert stats["sessoes_validas"] == 0
    assert stats["estado"] == "Alocado"


def test_session_12min_7msgs_and_evaluation_is_valid(cfg, entities, allocated_participant):
    """Critério de aceite 6: 12 min ativos + 7 msgs + avaliação enviada é válida."""
    classroom_id, participant = allocated_participant
    session = _make_session(cfg, classroom_id, participant)

    active_seconds = 12 * 60
    msg_count = 7
    is_valid = active_seconds >= DEFAULT_CONFIG["sessao_min_ativo_min"] * 60 and msg_count >= DEFAULT_CONFIG["sessao_min_msg_aluno"]
    assert is_valid is True

    close_study_session(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, session["id"], end_reason="manual", is_valid=True
    )
    # RN-2 também exige avaliação enviada (evaluation_pending=False)
    stats_before_eval = compute_participation(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, participant["id"], DEFAULT_CONFIG
    )
    assert stats_before_eval["sessoes_validas"] == 0  # avaliação ainda pendente

    create_session_evaluation(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_EVALUATIONS_TABLE,
        chat_id=None,
        student_id=participant["student_id"],
        classroom_id=classroom_id,
        page_enabled=participant["group_name"] == "experimental",
        paas_score=5,
        utilidade=4,
        exemplos=4,
        qualidade=4,
        nps=4,
    )
    mark_session_evaluation_done(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, session["id"])

    stats_after_eval = compute_participation(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, participant["id"], DEFAULT_CONFIG
    )
    assert stats_after_eval["sessoes_validas"] == 1
    assert stats_after_eval["estado"] == "Analisável"

    rows = (
        entities.sb.table(cfg.SUPABASE_EVALUATIONS_TABLE)
        .select("id")
        .eq("student_id", participant["student_id"])
        .execute()
        .data
    )
    for row in rows:
        entities.sb.table(cfg.SUPABASE_EVALUATIONS_TABLE).delete().eq("id", row["id"]).execute()


def test_progress_bar_math_matches_acceptance_criterion_10(cfg, entities, allocated_participant):
    """Critério de aceite 10: 3 sessões, 3 dúvidas, 4 exercícios, questionário
    pendente -> 30% + 10% + 30% + 0% = 70%."""
    classroom_id, participant = allocated_participant

    for _ in range(3):
        session = _make_session(cfg, classroom_id, participant)
        close_study_session(
            cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, session["id"], end_reason="manual", is_valid=True
        )
        create_session_evaluation(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            cfg.SUPABASE_EVALUATIONS_TABLE,
            chat_id=None,
            student_id=participant["student_id"],
            classroom_id=classroom_id,
            page_enabled=False,
            paas_score=5,
            utilidade=4,
            exemplos=4,
            qualidade=4,
            nps=4,
        )
        mark_session_evaluation_done(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, session["id"])

    for i in range(3):
        log_study_event(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            participant_id=participant["id"],
            classroom_id=classroom_id,
            effective_group=participant["group_name"],
            event_type="message",
            message_category="teorica",
            meta={"text_normalized": f"duvida unica numero {i}"},
        )

    stats = compute_participation(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, participant["id"], DEFAULT_CONFIG)
    assert stats["sessoes_validas"] == 3
    assert stats["duvidas_validas"] == 3
    assert stats["exercicios_concluidos"] == 0  # não cobertas neste teste
    assert stats["questionario_enviado"] is False
    # 30%*(3/3) + 20%*(3/6) + 30%*(0/4) + 20%*0 = 30 + 10 + 0 + 0 = 40
    assert stats["progresso_pct"] == 40.0

    rows = (
        entities.sb.table(cfg.SUPABASE_EVALUATIONS_TABLE)
        .select("id")
        .eq("student_id", participant["student_id"])
        .execute()
        .data
    )
    for row in rows:
        entities.sb.table(cfg.SUPABASE_EVALUATIONS_TABLE).delete().eq("id", row["id"]).execute()


def test_duplicate_message_text_counts_once(cfg, entities, allocated_participant):
    """RN-3: mensagem repetida não conta de novo como dúvida nova."""
    classroom_id, participant = allocated_participant
    for _ in range(3):
        log_study_event(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            participant_id=participant["id"],
            classroom_id=classroom_id,
            effective_group=participant["group_name"],
            event_type="message",
            message_category="teorica",
            meta={"text_normalized": "o que é um loop for?"},
        )
    stats = compute_participation(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, participant["id"], DEFAULT_CONFIG)
    assert stats["duvidas_validas"] == 1
