"""Modo Estudo: alocação balanceada por aluno, sessões/eventos, participação,
questionário final e apoio ao painel do pesquisador.

Perfis: alunos (alocação, sessão, eventos) e pesquisador/admin (painel,
export). Ver especificacao_funcional_modo_estudo.md para as regras (RF-*/
RN-*) que cada função implementa.
"""

from __future__ import annotations

import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from postgrest.exceptions import APIError

from .common import SupabaseOperationError, _get_client, _handle_api_error

STRATA = ("nenhuma", "alguma")
GROUPS = ("controle", "experimental")
_ANON_ALPHABET = string.ascii_uppercase + string.digits


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Módulo A — configuração do estudo e alocação balanceada
# ============================================================

def classify_stratum(e1_contato_previo: str, e3_ja_cursou: str) -> str:
    """RF-A2: único indicador binário de experiência prévia."""
    no_contact = (e1_contato_previo or "").strip().lower() == "não"
    not_retaken = (e3_ja_cursou or "").strip().lower() == "não"
    return "nenhuma" if (no_contact and not_retaken) else "alguma"


def fetch_latest_study_config(url: str, key: str, classroom_id: str) -> Optional[Dict[str, Any]]:
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_config")
            .select("*")
            .eq("classroom_id", classroom_id)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


def create_study_config(
    url: str,
    key: str,
    *,
    classroom_id: str,
    seed: Optional[int] = None,
    justification: Optional[str] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """RN-8: nova versão em vez de editar a vigente. `seed` fica registrado
    (RI-5) para a geração dos blocos de alocação ser reproduzível/auditável.
    """
    prev = fetch_latest_study_config(url, key, classroom_id)
    next_version = (prev["version"] + 1) if prev else 1
    payload: Dict[str, Any] = {
        "classroom_id": classroom_id,
        "version": next_version,
        "random_seed": seed if seed is not None else secrets.randbits(63),
        "justification": justification,
    }
    payload.update(overrides)

    client = _get_client(url, key)
    try:
        resp = client.table("study_config").insert(payload).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def generate_allocation_blocks(
    url: str,
    key: str,
    *,
    classroom_id: str,
    config_version: int,
    seed: int,
    n_blocks_per_stratum: int,
    block_size: int = 2,
) -> int:
    """RF-A3: blocos permutados, semente fixa. Cada bloco tem `block_size`
    posições (metade controle, metade experimental) em ordem embaralhada
    pela semente. Idempotente o bastante na prática: chamar de novo com o
    mesmo (classroom_id, config_version) falha por violação de unicidade em
    vez de duplicar blocos.
    """
    rng = random.Random(seed)
    client = _get_client(url, key)
    total_inserted = 0
    for stratum in STRATA:
        rows: List[Dict[str, Any]] = []
        for block_index in range(n_blocks_per_stratum):
            half = block_size // 2
            arm = (["controle"] * half) + (["experimental"] * (block_size - half))
            rng.shuffle(arm)
            for position, group_name in enumerate(arm):
                rows.append(
                    {
                        "classroom_id": classroom_id,
                        "config_version": config_version,
                        "stratum": stratum,
                        "block_index": block_index,
                        "position": position,
                        "group_name": group_name,
                    }
                )
        try:
            resp = client.table("study_allocation_blocks").insert(rows).execute()
        except APIError as err:
            raise _handle_api_error(err) from err
        except Exception as exc:
            raise SupabaseOperationError(str(exc)) from exc
        total_inserted += len(resp.data or [])
    return total_inserted


def _generate_anon_code(client, max_attempts: int = 10) -> str:
    for _ in range(max_attempts):
        code = "P-" + "".join(secrets.choice(_ANON_ALPHABET) for _ in range(4))
        existing = (
            client.table("study_participants")
            .select("id")
            .eq("anon_code", code)
            .limit(1)
            .execute()
        )
        if not (existing.data or []):
            return code
    raise SupabaseOperationError("Não foi possível gerar um código anônimo único.")


def claim_next_allocation_slot(
    url: str,
    key: str,
    *,
    classroom_id: str,
    config_version: int,
    stratum: str,
    student_id: str,
    max_attempts: int = 8,
) -> Optional[Dict[str, Any]]:
    """RF-A5: reivindica o próximo slot livre do estrato de forma segura sob
    concorrência. O client supabase-py não expõe ORDER/LIMIT em UPDATE, então
    usamos SELECT (candidato) + UPDATE condicional (`claimed_by IS NULL`) com
    retry: se dois alunos competirem pelo mesmo slot, só um UPDATE afeta a
    linha (o outro recebe 0 linhas e tenta o próximo candidato).
    Retorna None se os blocos do estrato estiverem esgotados (RF-A9).
    """
    client = _get_client(url, key)
    for _ in range(max_attempts):
        try:
            candidates = (
                client.table("study_allocation_blocks")
                .select("id,group_name,block_index,position")
                .eq("classroom_id", classroom_id)
                .eq("config_version", config_version)
                .eq("stratum", stratum)
                .is_("claimed_by", "null")
                .order("block_index")
                .order("position")
                .limit(1)
                .execute()
            )
        except APIError as err:
            raise _handle_api_error(err) from err
        except Exception as exc:
            raise SupabaseOperationError(str(exc)) from exc

        rows = candidates.data or []
        if not rows:
            return None
        slot_id = rows[0]["id"]

        try:
            claimed = (
                client.table("study_allocation_blocks")
                .update({"claimed_by": student_id, "claimed_at": _now_iso()})
                .eq("id", slot_id)
                .is_("claimed_by", "null")
                .execute()
            )
        except APIError as err:
            raise _handle_api_error(err) from err
        except Exception as exc:
            raise SupabaseOperationError(str(exc)) from exc

        if claimed.data:
            return claimed.data[0]
        # perdeu a corrida pro mesmo slot; tenta de novo (próximo candidato)
    raise SupabaseOperationError(
        "Não foi possível alocar agora (concorrência alta). Tente novamente."
    )


def fetch_participant_by_student(url: str, key: str, student_id: str) -> Optional[Dict[str, Any]]:
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_participants")
            .select("*")
            .eq("student_id", student_id)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


def allocate_participant(
    url: str,
    key: str,
    *,
    student_id: str,
    classroom_id: str,
    config_version: int,
    e1_contato_previo: str,
    e2_nivel_atual: int,
    e3_ja_cursou: str,
) -> Dict[str, Any]:
    """RF-A1/RF-A4: aloca ao concluir a etapa inicial. Idempotente — se o
    aluno já tem alocação, devolve a existente em vez de alocar de novo.
    """
    existing = fetch_participant_by_student(url, key, student_id)
    if existing:
        return existing

    stratum = classify_stratum(e1_contato_previo, e3_ja_cursou)
    slot = claim_next_allocation_slot(
        url,
        key,
        classroom_id=classroom_id,
        config_version=config_version,
        stratum=stratum,
        student_id=student_id,
    )
    if slot is None:
        raise SupabaseOperationError(
            "Blocos de alocação esgotados para este estrato. Avise o pesquisador."
        )

    client = _get_client(url, key)
    anon_code = _generate_anon_code(client)
    payload = {
        "student_id": student_id,
        "classroom_id": classroom_id,
        "anon_code": anon_code,
        "stratum": stratum,
        "group_name": slot["group_name"],
        "block_id": slot["id"],
        "config_version": config_version,
        "e1_contato_previo": e1_contato_previo,
        "e2_nivel_atual": int(e2_nivel_atual),
        "e3_ja_cursou": e3_ja_cursou,
    }
    try:
        resp = client.table("study_participants").insert(payload).execute()
    except APIError as err:
        # RF-A4: se outra aba/concorrência já inseriu entre o check e o
        # insert, devolve a alocação existente em vez de propagar erro.
        existing_after = fetch_participant_by_student(url, key, student_id)
        if existing_after:
            return existing_after
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def fetch_balance_report(url: str, key: str, classroom_id: str) -> List[Dict[str, Any]]:
    """RF-A10: contagem por grupo x estrato."""
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_participants")
            .select("stratum,group_name")
            .eq("classroom_id", classroom_id)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    counts: Dict[tuple, int] = {}
    for row in resp.data or []:
        key_tuple = (row.get("stratum"), row.get("group_name"))
        counts[key_tuple] = counts.get(key_tuple, 0) + 1
    return [
        {"stratum": stratum, "group_name": group_name, "count": counts.get((stratum, group_name), 0)}
        for stratum in STRATA
        for group_name in GROUPS
    ]


# ============================================================
# Módulo B — sessões, exercícios, eventos (append-only)
# ============================================================

def classify_message(text: str, *, min_words: int = 5) -> str:
    """RF-B5: classificação teórica x outra. Heurística simples (placeholder
    explícito — método final é decisão em aberto, seção 13.2 da spec):
    mensagens curtas/sem conteúdo (cumprimentos, "ok", "obrigado") viram
    "outra"; o resto vira "teorica". Exercícios são classificados à parte
    pelo modo exercício explícito (RF-B4), não por este heurístico.
    """
    words = (text or "").strip().split()
    if len(words) < min_words:
        return "outra"
    return "teorica"


def fetch_open_session(url: str, key: str, participant_id: str) -> Optional[Dict[str, Any]]:
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_sessions")
            .select("*")
            .eq("participant_id", participant_id)
            .is_("ended_at", "null")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


def start_study_session(
    url: str,
    key: str,
    *,
    participant_id: str,
    classroom_id: str,
    effective_group: str,
    config_version: int,
) -> Dict[str, Any]:
    """RF-B1: início na 1ª mensagem. Reaproveita sessão aberta se existir
    (evita duplicar ao reenviar o formulário/recarregar a página)."""
    open_session = fetch_open_session(url, key, participant_id)
    if open_session:
        return open_session

    payload = {
        "participant_id": participant_id,
        "classroom_id": classroom_id,
        "effective_group": effective_group,
        "config_version": config_version,
    }
    client = _get_client(url, key)
    try:
        resp = client.table("study_sessions").insert(payload).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def touch_session_activity(
    url: str,
    key: str,
    session_id: str,
    *,
    active_seconds: int,
    student_message_count: int,
    had_fallback: Optional[bool] = None,
) -> Dict[str, Any]:
    """Atualiza os contadores da sessão aberta. O chamador calcula
    `active_seconds`/`student_message_count` já somados (RF-B2: cada
    intervalo limitado a IDLE_CAP_MIN) e manda o total acumulado."""
    payload: Dict[str, Any] = {
        "active_seconds": active_seconds,
        "student_message_count": student_message_count,
        "last_activity_at": _now_iso(),
    }
    if had_fallback:
        payload["had_fallback"] = True
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_sessions").update(payload).eq("id", session_id).execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def close_study_session(
    url: str,
    key: str,
    session_id: str,
    *,
    end_reason: str,
    is_valid: bool,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """RF-B1/RN-2: fecha a sessão e grava se ela é válida. `evaluation_pending`
    só vira False quando a avaliação pós-sessão é enviada (RF-B3)."""
    payload: Dict[str, Any] = {
        "ended_at": _now_iso(),
        "end_reason": end_reason,
        "is_valid": is_valid,
    }
    if chat_id:
        payload["chat_id"] = chat_id
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_sessions").update(payload).eq("id", session_id).execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def mark_session_evaluation_done(url: str, key: str, session_id: str) -> None:
    client = _get_client(url, key)
    try:
        client.table("study_sessions").update({"evaluation_pending": False}).eq(
            "id", session_id
        ).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc


def close_abandoned_sessions(
    url: str,
    key: str,
    *,
    participant_id: str,
    config: Dict[str, Any],
    idle_minutes: int = 30,
) -> List[Dict[str, Any]]:
    """RF-B3 (versão mínima, sem gr.Timer): no próximo acesso do aluno,
    fecha sessões abertas há mais de `idle_minutes` desde a última
    atividade registrada (aba fechada sem "Encerrar Chat"). Usa a mesma
    regra de validade de RN-2 a partir do que já foi acumulado em
    active_seconds/student_message_count. Retorna as sessões fechadas
    (para o chamador decidir se mostra avaliação pendente)."""
    client = _get_client(url, key)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=idle_minutes)).isoformat()
    try:
        resp = (
            client.table("study_sessions")
            .select("*")
            .eq("participant_id", participant_id)
            .is_("ended_at", "null")
            .lt("last_activity_at", cutoff)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    min_active_s = int(config.get("sessao_min_ativo_min", 10)) * 60
    min_msgs = int(config.get("sessao_min_msg_aluno", 6))
    closed = []
    for session in resp.data or []:
        is_valid = (
            int(session.get("active_seconds") or 0) >= min_active_s
            and int(session.get("student_message_count") or 0) >= min_msgs
        )
        updated = close_study_session(
            url, key, session["id"], end_reason="idle_timeout", is_valid=is_valid
        )
        closed.append(updated)
    return closed


def admin_validate_session(url: str, key: str, session_id: str, *, note: Optional[str] = None) -> Dict[str, Any]:
    """Validação manual pelo admin (mitigação do risco de "ninguém perder
    pontos por erro do sistema"): marca uma sessão como válida mesmo que a
    atividade registrada não bata com os mínimos, por exemplo quando uma
    falha técnica (não do aluno) interrompeu a sessão."""
    client = _get_client(url, key)
    try:
        current = client.table("study_sessions").select("*").eq("id", session_id).limit(1).execute()
        resp = client.table("study_sessions").update({"is_valid": True}).eq("id", session_id).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    row = (current.data or [{}])[0]
    if row.get("participant_id") and row.get("classroom_id"):
        try:
            log_study_event(
                url, key,
                participant_id=row["participant_id"],
                classroom_id=row["classroom_id"],
                effective_group=row.get("effective_group", "controle"),
                event_type="session_end",
                session_id=session_id,
                meta={"admin_manual_validation": True, "note": note},
            )
        except Exception:
            pass
    return (resp.data or [{"is_valid": True}])[0]


def fetch_pending_evaluation_session(url: str, key: str, participant_id: str) -> Optional[Dict[str, Any]]:
    """RF-B3: sessão encerrada sem avaliação, pra exibir no próximo login
    antes de abrir qualquer novo chat."""
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_sessions")
            .select("*")
            .eq("participant_id", participant_id)
            .eq("evaluation_pending", True)
            .not_.is_("ended_at", "null")
            .order("ended_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


def log_study_event(
    url: str,
    key: str,
    *,
    participant_id: str,
    classroom_id: str,
    effective_group: str,
    event_type: str,
    session_id: Optional[str] = None,
    exercise_id: Optional[str] = None,
    message_category: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """RF-B6/RI-2: log append-only. Nunca levanta pro chamador quebrar o
    fluxo principal por causa de log — only best-effort (mesma convenção de
    log_access_event em common.py)."""
    payload = {
        "participant_id": participant_id,
        "classroom_id": classroom_id,
        "effective_group": effective_group,
        "event_type": event_type,
        "session_id": session_id,
        "exercise_id": exercise_id,
        "message_category": message_category,
        "meta": meta or {},
    }
    client = _get_client(url, key)
    try:
        client.table("study_events").insert(payload).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc


def start_exercise(url: str, key: str, *, session_id: str, participant_id: str) -> Dict[str, Any]:
    payload = {"session_id": session_id, "participant_id": participant_id}
    client = _get_client(url, key)
    try:
        resp = client.table("study_exercises").insert(payload).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def end_exercise(
    url: str,
    key: str,
    exercise_id: str,
    *,
    status: str,
    student_message_count: int,
    motivo_desistencia: Optional[str] = None,
) -> Dict[str, Any]:
    """RF-B4/RN-4: só conta como concluído com >= EX_MIN_MSG_ALUNO mensagens
    do aluno — quem decide isso é o chamador (student.py), que já sabe o
    parâmetro vigente; esta função só grava o que foi decidido."""
    payload: Dict[str, Any] = {
        "ended_at": _now_iso(),
        "status": status,
        "student_message_count": student_message_count,
    }
    if motivo_desistencia:
        payload["motivo_desistencia"] = motivo_desistencia
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_exercises").update(payload).eq("id", exercise_id).execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


def fetch_open_exercise(url: str, key: str, session_id: str) -> Optional[Dict[str, Any]]:
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_exercises")
            .select("*")
            .eq("session_id", session_id)
            .is_("ended_at", "null")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


# ============================================================
# Módulo C — participação (cálculo em runtime, sem tabela própria)
# ============================================================

def compute_participation(url: str, key: str, participant_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """RN-2 a RN-6: conta sessões válidas, dúvidas válidas (via study_events),
    exercícios concluídos, e deriva o estado do participante. Tudo calculado
    a partir de study_sessions/study_events/study_final_questionnaire — sem
    persistir um "estado" próprio, pra nunca dessincronizar da fonte."""
    client = _get_client(url, key)
    try:
        sessions_resp = (
            client.table("study_sessions")
            .select("id,is_valid,evaluation_pending,started_at,ended_at")
            .eq("participant_id", participant_id)
            .execute()
        )
        events_resp = (
            client.table("study_events")
            .select("event_type,message_category,meta,created_at")
            .eq("participant_id", participant_id)
            .execute()
        )
        exercises_resp = (
            client.table("study_exercises")
            .select("status")
            .eq("participant_id", participant_id)
            .execute()
        )
        quest_resp = (
            client.table("study_final_questionnaire")
            .select("id")
            .eq("participant_id", participant_id)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    sessions = sessions_resp.data or []
    # RN-2: além da atividade mínima (is_valid), exige avaliação enviada.
    valid_sessions = [
        s for s in sessions if s.get("is_valid") and not s.get("evaluation_pending")
    ]
    distinct_days = {
        (s.get("ended_at") or s.get("started_at") or "")[:10] for s in valid_sessions
    }

    seen_texts: set = set()
    duvidas_validas = 0
    preencheu_interesses = False
    for ev in events_resp.data or []:
        if ev.get("event_type") == "message" and ev.get("message_category") == "teorica":
            text_key = ((ev.get("meta") or {}).get("text_normalized")) or ev.get("created_at")
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            duvidas_validas += 1
        elif ev.get("event_type") == "config_applied":
            if int((ev.get("meta") or {}).get("n_temas_interesse", 0) or 0) >= 1:
                preencheu_interesses = True

    exercicios_concluidos = sum(
        1 for e in exercises_resp.data or [] if e.get("status") == "concluido"
    )
    questionario_enviado = bool(quest_resp.data)

    n_sessoes_validas = len(valid_sessions)
    meta_sessoes = config.get("meta_sessoes", 3)
    meta_dias = config.get("meta_sessoes_dias_distintos", 2)
    meta_duvidas = config.get("meta_duvidas", 6)
    meta_exercicios = config.get("meta_exercicios", 4)
    min_analise = config.get("min_analise_sessoes", 1)

    is_analisavel = n_sessoes_validas >= min_analise
    is_completo = (
        n_sessoes_validas >= meta_sessoes
        and len(distinct_days) >= meta_dias
        and duvidas_validas >= meta_duvidas
        and exercicios_concluidos >= meta_exercicios
        and questionario_enviado
    )
    estado = "Completo" if is_completo else ("Analisável" if is_analisavel else "Alocado")

    peso_sessoes = float(config.get("peso_sessoes", 0.25))
    peso_duvidas = float(config.get("peso_duvidas", 0.15))
    peso_exercicios = float(config.get("peso_exercicios", 0.25))
    peso_questionario = float(config.get("peso_questionario", 0.20))
    peso_interesses = float(config.get("peso_interesses", 0.15))

    # Metas podem ser 0 (ex.: meta_exercicios=0 como mitigação enquanto o
    # modo exercício está indisponível) -- trata como "item satisfeito" e
    # redistribui o peso proporcionalmente entre os itens restantes, em vez
    # de dividir por zero.
    itens = [
        (meta_sessoes, min(n_sessoes_validas / meta_sessoes, 1.0) if meta_sessoes else 1.0, peso_sessoes),
        (meta_duvidas, min(duvidas_validas / meta_duvidas, 1.0) if meta_duvidas else 1.0, peso_duvidas),
        (meta_exercicios, min(exercicios_concluidos / meta_exercicios, 1.0) if meta_exercicios else 1.0, peso_exercicios),
        (1, 1.0 if questionario_enviado else 0.0, peso_questionario),
        (1, 1.0 if preencheu_interesses else 0.0, peso_interesses),
    ]
    peso_ativo_total = sum(peso for meta, _frac, peso in itens if meta)
    peso_zerado_total = sum(peso for meta, _frac, peso in itens if not meta)
    progresso_pct = round(
        100
        * sum(
            (peso + (peso / peso_ativo_total * peso_zerado_total if meta and peso_ativo_total else 0)) * frac
            for meta, frac, peso in itens
            if meta
        ),
        1,
    )

    return {
        "sessoes_validas": n_sessoes_validas,
        "sessoes_dias_distintos": len(distinct_days),
        "duvidas_validas": duvidas_validas,
        "exercicios_concluidos": exercicios_concluidos,
        "questionario_enviado": questionario_enviado,
        "preencheu_interesses": preencheu_interesses,
        "estado": estado,
        "progresso_pct": progresso_pct,
        "questionario_liberado": n_sessoes_validas >= config.get("questionario_min_sessoes", 2),
    }


# ============================================================
# Módulo E — questionário final
# ============================================================

def fetch_final_questionnaire(url: str, key: str, participant_id: str) -> Optional[Dict[str, Any]]:
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_final_questionnaire")
            .select("*")
            .eq("participant_id", participant_id)
            .limit(1)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    rows = resp.data or []
    return rows[0] if rows else None


def submit_final_questionnaire(
    url: str,
    key: str,
    *,
    participant_id: str,
    group_name: str,
    q1_ajudou_estudos: int,
    q2_recomendaria: int,
    q3_exemplos_relevantes: int,
    q4_reduziu_ansiedade: int,
    q5_facil_entender: int,
    q6_nps: Optional[int] = None,
    q7_comentario: Optional[str] = None,
) -> Dict[str, Any]:
    """RF-E1: uma resposta por participante (UNIQUE em participant_id)."""
    payload = {
        "participant_id": participant_id,
        "group_name": group_name,
        "q1_ajudou_estudos": int(q1_ajudou_estudos),
        "q2_recomendaria": int(q2_recomendaria),
        "q3_exemplos_relevantes": int(q3_exemplos_relevantes),
        "q4_reduziu_ansiedade": int(q4_reduziu_ansiedade),
        "q5_facil_entender": int(q5_facil_entender),
        "q6_nps": int(q6_nps) if q6_nps is not None else None,
        "q7_comentario": q7_comentario,
    }
    client = _get_client(url, key)
    try:
        resp = client.table("study_final_questionnaire").insert(payload).execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc
    return (resp.data or [payload])[0]


# ============================================================
# Módulo F — painel do pesquisador
# ============================================================

def fetch_participants_overview(url: str, key: str, classroom_id: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """RF-F1: visão por participante (código anônimo, grupo, estrato, estado,
    % progresso, contagens, última atividade)."""
    client = _get_client(url, key)
    try:
        resp = (
            client.table("study_participants")
            .select("id,anon_code,stratum,group_name,allocated_at")
            .eq("classroom_id", classroom_id)
            .execute()
        )
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    overview = []
    for participant in resp.data or []:
        stats = compute_participation(url, key, participant["id"], config)
        overview.append({**participant, **stats})
    return overview


def fetch_credit_list(url: str, key: str, classroom_id: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """RF-F7: nome + situação + pontuação sugerida — sem notas de avaliação
    nem grupo (neutralidade/cegamento). Crédito proporcional ao progresso,
    conforme RN-10 (metade ao ficar analisável, total ao ficar completo)."""
    client = _get_client(url, key)
    try:
        participants_resp = (
            client.table("study_participants")
            .select("id,student_id")
            .eq("classroom_id", classroom_id)
            .execute()
        )
        users_resp = client.table("users").select("id,full_name,email").execute()
    except APIError as err:
        raise _handle_api_error(err) from err
    except Exception as exc:
        raise SupabaseOperationError(str(exc)) from exc

    users_by_id = {u["id"]: u for u in users_resp.data or []}
    rows = []
    for participant in participants_resp.data or []:
        stats = compute_participation(url, key, participant["id"], config)
        user = users_by_id.get(participant["student_id"], {})
        estado = stats["estado"]
        pontuacao = 1.0 if estado == "Completo" else (0.5 if estado == "Analisável" else 0.0)
        rows.append(
            {
                "nome": user.get("full_name"),
                "email": user.get("email"),
                "situacao": estado,
                "pontuacao_sugerida_fracao": pontuacao,
            }
        )
    return rows


__all__ = [
    "STRATA",
    "GROUPS",
    "classify_stratum",
    "fetch_latest_study_config",
    "create_study_config",
    "generate_allocation_blocks",
    "claim_next_allocation_slot",
    "fetch_participant_by_student",
    "allocate_participant",
    "fetch_balance_report",
    "classify_message",
    "fetch_open_session",
    "start_study_session",
    "touch_session_activity",
    "close_study_session",
    "mark_session_evaluation_done",
    "fetch_pending_evaluation_session",
    "close_abandoned_sessions",
    "admin_validate_session",
    "log_study_event",
    "start_exercise",
    "end_exercise",
    "fetch_open_exercise",
    "compute_participation",
    "fetch_final_questionnaire",
    "submit_final_questionnaire",
    "fetch_participants_overview",
    "fetch_credit_list",
]
