"""Regressão: `_load_domain_state` precisa propagar `page_enabled` da sala
crua pro dicionário normalizado em `classrooms_state`.

Bug real encontrado em 2026-10: o PAGE nunca disparava em produção porque
essa normalização descartava `page_enabled`, fazendo `student.py` sempre ler
`None`/`False` independente do que o professor configurou na sala.
"""
from __future__ import annotations

import pytest

from app.pages.admin import _load_domain_state

pytestmark = pytest.mark.integration


def test_load_domain_state_preserves_page_enabled(entities):
    teacher = entities.make_user(role="teacher")
    classroom = entities.make_classroom(teacher["id"], page_enabled=True)

    classrooms, _subjects, warn = _load_domain_state()

    assert not (warn or "").startswith("ERROR")
    match = next((c for c in classrooms if c["id"] == classroom["id"]), None)
    assert match is not None, "sala de teste não apareceu em classrooms_state"
    assert match["page_enabled"] is True
