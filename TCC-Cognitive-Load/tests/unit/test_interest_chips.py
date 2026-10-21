"""Unit: services.interest_chips (funções puras, offline)."""

import pytest

from services.interest_chips import (
    INTEREST_THEMES,
    MAX_THEMES,
    deserialize_structured,
    serialize_interests,
    validate_selection,
)

pytestmark = pytest.mark.unit


def test_serialize_tema_com_detalhe():
    texto, estruturado = serialize_interests(["Esportes"], {"Esportes": "jogo vôlei"})
    assert texto == "Esportes (jogo vôlei)"
    assert estruturado == [{"tema": "Esportes", "detalhe": "jogo vôlei"}]


def test_serialize_tema_sem_detalhe_nao_tem_parenteses():
    texto, estruturado = serialize_interests(["Música"], {})
    assert texto == "Música"
    assert estruturado == [{"tema": "Música", "detalhe": ""}]


def test_serialize_varios_temas_mantem_ordem():
    texto, estruturado = serialize_interests(
        ["Jogos", "Leitura"], {"Jogos": "RPG", "Leitura": ""}
    )
    assert texto == "Jogos (RPG); Leitura"
    assert estruturado == [
        {"tema": "Jogos", "detalhe": "RPG"},
        {"tema": "Leitura", "detalhe": ""},
    ]


def test_serialize_sem_nenhum_tema():
    assert serialize_interests([], {}) == ("", [])
    assert serialize_interests(None, None) == ("", [])


def test_serialize_trunca_em_max_themes():
    texto, estruturado = serialize_interests(
        INTEREST_THEMES[: MAX_THEMES + 2], {}
    )
    assert len(estruturado) == MAX_THEMES


def test_validate_selection_ok():
    assert validate_selection(["Esportes", "Música"], {}) is None


def test_validate_selection_mais_de_tres_temas():
    erro = validate_selection(INTEREST_THEMES[:4], {})
    assert erro == f"Máximo de {MAX_THEMES} temas."


def test_validate_selection_outro_sem_descricao():
    erro = validate_selection(["Outro"], {})
    assert erro is not None
    assert "Outro" in erro


def test_validate_selection_outro_com_descricao():
    assert validate_selection(["Outro"], {"Outro": "colecionar discos"}) is None


def test_deserialize_structured_reconstroi_selecao_e_detalhes():
    selected, details = deserialize_structured(
        [{"tema": "Esportes", "detalhe": "jogo vôlei"}, {"tema": "Música", "detalhe": ""}]
    )
    assert selected == ["Esportes", "Música"]
    assert details == {"Esportes": "jogo vôlei"}


def test_deserialize_structured_ignora_tema_desconhecido_e_duplicado():
    selected, details = deserialize_structured(
        [
            {"tema": "Esportes", "detalhe": "x"},
            {"tema": "Não existe", "detalhe": "y"},
            {"tema": "Esportes", "detalhe": "z"},
        ]
    )
    assert selected == ["Esportes"]
    assert details == {"Esportes": "x"}


def test_deserialize_structured_vazio():
    assert deserialize_structured(None) == ([], {})
    assert deserialize_structured([]) == ([], {})
