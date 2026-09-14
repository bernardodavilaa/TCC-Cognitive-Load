"""Unit: services.auth_store (hash e normalização do store legado, offline)."""

import hashlib

import pytest

from services import auth_store

pytestmark = pytest.mark.unit


def test_hash_pw_e_sha256_estavel():
    assert auth_store._hashPw("segredo") == hashlib.sha256(b"segredo").hexdigest()
    assert auth_store._hashPw("segredo") == auth_store._hashPw("segredo")
    assert auth_store._hashPw("") == hashlib.sha256(b"").hexdigest()


def test_normalize_db_keys():
    raw = {
        "  Augusto ": {"pw": "h1", "role": "PROFESSOR"},
        "Maria": "h2",  # formato legado (string)
        "": "ignora-vazio-vira-chave-vazia",
    }
    fixed = auth_store._normalize_db_keys(raw)
    assert fixed["augusto"] == {"pw": "h1", "role": "professor"}
    assert fixed["maria"] == {"pw": "h2", "role": "aluno"}


def test_get_e_set_user_entry():
    db = {}
    auth_store._setUserEntry(db, " Joao ", "hashX", "Professor")
    assert db["joao"] == {"pw": "hashX", "role": "professor"}

    entry = auth_store._getUserEntry(db, "JOAO")
    assert entry == {"pw": "hashX", "role": "professor"}
    assert auth_store._getUserEntry(db, "inexistente") is None


def test_get_user_entry_formato_legado_string():
    entry = auth_store._getUserEntry({"ana": "hash-legado"}, "ana")
    assert entry == {"pw": "hash-legado", "role": "aluno"}
