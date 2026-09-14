"""Unit: helpers puros de services.vertex_client (offline, sem chamar a API)."""

import pytest

from services import vertex_client as vc

pytestmark = pytest.mark.unit


def test_messages_to_transcript():
    msgs = [
        {"role": "system", "content": "regras"},
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "ola"},
    ]
    out = vc._messagesToTranscript(msgs)
    assert out == "SYSTEM: regras\n\nUSER: oi\n\nASSISTANT: ola"


def test_limit_phrases():
    texto = "Primeira frase. Segunda frase. Terceira frase."
    assert vc._limit_phrases(texto, max_phrases=2) == "Primeira frase. Segunda frase."
    assert vc._limit_phrases("", max_phrases=2) == ""


class _FakePart:
    def __init__(self, text):
        self.text = text


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts):
        self.content = _FakeContent(parts)


class _FakeResponse:
    def __init__(self, *, text=None, parts=None):
        self.text = text
        self.candidates = [_FakeCandidate(parts)] if parts is not None else []


def test_collect_response_text_direto():
    assert vc._collect_response_text(_FakeResponse(text="resposta direta")) == "resposta direta"


def test_collect_response_text_via_candidates():
    resp = _FakeResponse(parts=[_FakePart("parte 1"), _FakePart("parte 2")])
    assert vc._collect_response_text(resp) == "parte 1 parte 2"


def test_collect_response_text_none():
    assert vc._collect_response_text(None) == ""


def test_load_vertex_cfg_from_disk_le_config_local():
    # Depende de app/config.py + service_account.json (arquivo local, sem rede).
    cfg = vc._load_vertex_cfg_from_disk()
    assert cfg["project"]
    assert cfg["serviceAccount"].get("private_key")
    assert cfg["serviceAccount"].get("client_email")
