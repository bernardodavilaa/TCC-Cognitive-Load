"""Integração: cadastro/consulta de usuários no Supabase real."""

import pytest

from services.supabase_client import (
    SupabaseUserExistsError,
    create_user_record,
    fetch_user_record,
    fetch_users_by_role,
)
from tests._helpers import TEST_PASSWORD, tag

pytestmark = pytest.mark.integration


@pytest.fixture
def make_login_user(cfg, sb_client, _hash_pw, entities):
    def _make(role="student"):
        t = tag("auth_")
        email = f"{t}@pytest.local"
        rec = create_user_record(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            cfg.SUPABASE_USERS_TABLE,
            login=email,
            password_hash=_hash_pw(TEST_PASSWORD),
            role=role,
            username=t,
            full_name=f"Pytest {t}",
            display_name=f"Pytest {t}",
        )
        entities.on_cleanup(
            lambda: sb_client.table(cfg.SUPABASE_USERS_TABLE)
            .delete()
            .eq("id", rec.id)
            .execute()
        )
        return t, email, rec

    return _make


def test_create_and_fetch_by_email_and_username(cfg, make_login_user):
    username, email, rec = make_login_user()

    by_email = fetch_user_record(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, cfg.SUPABASE_USERS_TABLE, email
    )
    by_username = fetch_user_record(
        cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY, cfg.SUPABASE_USERS_TABLE, username
    )
    assert by_email is not None and by_email.id == rec.id
    assert by_username is not None and by_username.id == rec.id
    assert by_email.role == "student"


def test_duplicate_email_raises(cfg, make_login_user, _hash_pw):
    _, email, _ = make_login_user()
    with pytest.raises(SupabaseUserExistsError):
        create_user_record(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            cfg.SUPABASE_USERS_TABLE,
            login=email,
            password_hash=_hash_pw("outra"),
            role="student",
            username=tag("dup_"),
            full_name="Dup",
            display_name="Dup",
        )


def test_fetch_users_by_role_inclui_novo_aluno(cfg, make_login_user):
    username, _, _ = make_login_user(role="student")
    alunos = fetch_users_by_role(
        cfg.SUPABASE_URL,
        cfg.SUPABASE_SERVICE_ROLE_KEY,
        cfg.SUPABASE_USERS_TABLE,
        "student",
    )
    assert any(u.username == username for u in alunos)


def test_fetch_user_record_inexistente(cfg):
    assert (
        fetch_user_record(
            cfg.SUPABASE_URL,
            cfg.SUPABASE_SERVICE_ROLE_KEY,
            cfg.SUPABASE_USERS_TABLE,
            "nao-existe@pytest.local",
        )
        is None
    )
