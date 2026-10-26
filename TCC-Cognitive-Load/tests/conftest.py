"""Fixtures compartilhadas.

Camadas:
- unit        : nada aqui é necessário (offline).
- integration : usa `cfg`, `sb_client`, `entities`.
- e2e         : usa `app_server` (app in-process, Vertex stubbada) + `page` + `login`.
- vertex      : usa `cfg` e chama a API real.
"""

from __future__ import annotations

import importlib
import importlib.util
import socket
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests._helpers import TEST_PASSWORD, tag

ROOT = Path(__file__).resolve().parent.parent
SEED_USERS = ("admin", "professor", "aluno")


# --------------------------------------------------------------------------- #
# Config / cliente Supabase
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def cfg():
    import app.config as config

    return config


@pytest.fixture(scope="session")
def sb_client(cfg):
    from services.supabase.common import _get_client

    try:
        return _get_client(cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Supabase indisponível: {exc}")


@pytest.fixture(scope="session")
def _hash_pw():
    from services.auth_store import _hashPw

    return _hashPw


# --------------------------------------------------------------------------- #
# Credenciais conhecidas para os usuários seed (restauradas no teardown)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def seed_credentials(sb_client, _hash_pw):
    rows = (
        sb_client.table("users")
        .select("id,username,password_hash")
        .in_("username", list(SEED_USERS))
        .execute()
        .data
        or []
    )
    if len(rows) < len(SEED_USERS):
        found = {r["username"] for r in rows}
        pytest.skip(f"Usuários seed ausentes no Supabase: {set(SEED_USERS) - found}")

    originals = {r["username"]: r["password_hash"] for r in rows}
    new_hash = _hash_pw(TEST_PASSWORD)
    for uname in originals:
        sb_client.table("users").update({"password_hash": new_hash}).eq(
            "username", uname
        ).execute()

    yield {uname: (uname, TEST_PASSWORD) for uname in originals}

    for uname, original_hash in originals.items():
        sb_client.table("users").update({"password_hash": original_hash}).eq(
            "username", uname
        ).execute()


@pytest.fixture(scope="session")
def seed_room(sb_client):
    """A sala seed (a primeira/única criada pelo usuário) + seus vínculos."""
    rooms = sb_client.table("classrooms").select("*").order("id").execute().data or []
    if not rooms:
        pytest.skip("Nenhuma sala seed no Supabase.")
    room = rooms[0]
    subjects = (
        sb_client.table("classroom_subjects")
        .select("*")
        .eq("classroom_id", room["id"])
        .execute()
        .data
        or []
    )
    return {"room": room, "subjects": subjects}


# --------------------------------------------------------------------------- #
# Registro de entidades criadas por teste (cleanup LIFO)
# --------------------------------------------------------------------------- #
class Entities:
    def __init__(self, sb, hash_pw):
        self.sb = sb
        self._hash_pw = hash_pw
        self._cleanups = []  # list[callable]

    def on_cleanup(self, fn):
        self._cleanups.append(fn)

    def _del_by_id(self, table, id_):
        self.on_cleanup(lambda: self.sb.table(table).delete().eq("id", id_).execute())

    def make_user(self, role="student", extra=""):
        t = tag(extra)
        row = (
            self.sb.table("users")
            .insert(
                {
                    "username": t,
                    "full_name": f"Pytest {t}",
                    "email": f"{t}@pytest.local",
                    "password_hash": self._hash_pw(TEST_PASSWORD),
                    "role": role,
                }
            )
            .execute()
            .data[0]
        )
        self._del_by_id("users", row["id"])
        return row

    def make_classroom(self, created_by, *, theme_locked=False, **over):
        t = tag("sala_")
        payload = {
            "name": t,
            "description": "sala de teste pytest",
            "theme_name": over.get("theme_name", "Lógica de Programação"),
            "theme_locked": theme_locked,
            "created_by": created_by,
        }
        payload.update({k: v for k, v in over.items() if k != "theme_name"})
        row = self.sb.table("classrooms").insert(payload).execute().data[0]
        self._del_by_id("classrooms", row["id"])
        return row

    def make_subject(self, classroom_id, created_by, name=None):
        row = (
            self.sb.table("classroom_subjects")
            .insert(
                {
                    "classroom_id": classroom_id,
                    "name": name or tag("sub_"),
                    "created_by": created_by,
                }
            )
            .execute()
            .data[0]
        )
        self._del_by_id("classroom_subjects", row["id"])
        return row

    def enrol_student(self, classroom_id, student_id, status="active"):
        self.sb.table("classroom_students").upsert(
            {
                "classroom_id": classroom_id,
                "student_id": student_id,
                "status": status,
            },
            on_conflict="classroom_id,student_id",
        ).execute()
        self.on_cleanup(
            lambda: self.sb.table("classroom_students")
            .delete()
            .eq("classroom_id", classroom_id)
            .eq("student_id", student_id)
            .execute()
        )

    def add_teacher(self, classroom_id, teacher_id, role_label=None):
        payload = {"classroom_id": classroom_id, "teacher_id": teacher_id}
        if role_label:
            payload["role_label"] = role_label
        self.sb.table("classroom_teachers").upsert(
            payload, on_conflict="classroom_id,teacher_id"
        ).execute()
        self.on_cleanup(
            lambda: self.sb.table("classroom_teachers")
            .delete()
            .eq("classroom_id", classroom_id)
            .eq("teacher_id", teacher_id)
            .execute()
        )

    def track_chat(self, chat_id, *, bucket=None, storage_path=None):
        """Registra a remoção de um chat (linha + objeto no Storage)."""

        def _cleanup():
            if bucket and storage_path:
                try:
                    self.sb.storage.from_(bucket).remove([storage_path])
                except Exception:
                    pass
            self.sb.table("chats").delete().eq("id", chat_id).execute()

        self.on_cleanup(_cleanup)

    def cleanup(self):
        for fn in reversed(self._cleanups):
            try:
                fn()
            except Exception as exc:  # pragma: no cover
                print(f"[entities] falha no cleanup: {exc}")
        self._cleanups.clear()


@pytest.fixture
def entities(sb_client, _hash_pw):
    reg = Entities(sb_client, _hash_pw)
    yield reg
    reg.cleanup()


# --------------------------------------------------------------------------- #
# App Gradio in-process com a Vertex AI stubbada (para o E2E)
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _fake_stream(messages, cfg, adv, finish_reason_holder=None):
    last_user = ""
    for m in messages:
        if (m.get("role") or "").lower() == "user":
            last_user = m.get("content") or ""
    if finish_reason_holder is not None:
        finish_reason_holder[:] = ["STOP"]
    yield f"[resposta simulada] recebi: {last_user}".strip()


def _fake_summary(messages, cfg, *, max_phrases=2):
    return "Resumo simulado do chat."


def _fake_evaluation(transcript, cfg, *, subjects=None):
    subs = subjects or ["Tema"]
    return {
        "subjects": [
            {"subject": str(s), "grade": 70.0, "comment": "avaliação simulada"}
            for s in subs
            if s
        ],
        "overview": "Avaliação automática simulada.",
        "overallGrade": 70.0,
        "raw": "{}",
    }


@pytest.fixture(scope="session")
def app_server(cfg, seed_credentials):
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()

    # Carrega app.py da raiz (é script; o pacote app/ não expõe build_app).
    spec = importlib.util.spec_from_file_location("tcc_app_main", ROOT / "app.py")
    main = importlib.util.module_from_spec(spec)
    sys.modules["tcc_app_main"] = main
    spec.loader.exec_module(main)

    import app.pages.chat as chat_page
    import app.pages.history_shared as history_page
    import app.pages.student as student_page

    mp.setattr(chat_page, "_streamFromVertex", _fake_stream)
    mp.setattr(student_page, "summarize_chat_history", _fake_summary)
    mp.setattr(history_page, "generate_chat_evaluation", _fake_evaluation)

    demo = main.build_app()
    port = _free_port()
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        prevent_thread_lock=True,
        quiet=True,
        show_error=True,
        share=False,
        inbrowser=False,
    )

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base, timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:  # pragma: no cover
        demo.close()
        mp.undo()
        pytest.fail("app Gradio não subiu a tempo")

    yield base

    demo.close()
    mp.undo()
