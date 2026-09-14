"""Unit: services.script_builder.buildCustomScript (função pura, offline)."""

import pytest

from services.script_builder import buildCustomScript

pytestmark = pytest.mark.unit


def _script(**over):
    kwargs = dict(
        assunto="Ponteiros em C",
        estilo="simples",
        detalhamento="detalhadas",
        objetivo="Passar na prova",
        extras="",
    )
    kwargs.update(over)
    return buildCustomScript(
        kwargs["assunto"],
        kwargs["estilo"],
        kwargs["detalhamento"],
        kwargs["objetivo"],
        kwargs["extras"],
        subtemas=kwargs.get("subtemas"),
        interesses=kwargs.get("interesses"),
    )


def test_inclui_assunto_e_objetivo():
    out = _script()
    assert "Tópico: Ponteiros em C." in out
    assert "Objetivo principal: Passar na prova." in out
    assert "Teoria da Carga Cognitiva de Sweller" in out


def test_detalhamento_detalhadas_vs_curtas():
    assert "Respostas detalhadas" in _script(detalhamento="detalhadas")
    assert "Respostas curtas e diretas" in _script(detalhamento="curtas")


def test_estilo_tecnicas_vs_simples():
    assert "Linguagem técnica" in _script(estilo="técnicas")
    assert "Linguagem simples e acessível" in _script(estilo="simples")


def test_subtemas_e_interesses_opcionais():
    base = _script()
    assert "Priorize os subtemas" not in base
    assert "temas de interesse do aluno" not in base

    com = _script(subtemas=["Recursão", "Listas"], interesses="  jogos  ")
    assert "Priorize os subtemas selecionados pelo aluno: Recursão, Listas." in com
    assert "temas de interesse do aluno: jogos." in com


def test_extras_incluido_quando_presente():
    assert "Preferências adicionais: sem inglês" in _script(extras="sem inglês")
    assert "Preferências adicionais" not in _script(extras="")
