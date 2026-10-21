# services/interest_chips.py
"""Catálogo de "temas de interesse" (chips) e serialização pros dois
formatos consumidos a jusante:

- a string livre `"Tema (detalhe); Tema2"` que o prompt base (Augusto) já lê
  via `interesses` em `services.script_builder.buildCustomScript` -- nenhuma
  mudança é necessária lá, o grupo controle continua recebendo exatamente o
  mesmo tipo de texto que recebia antes;
- a lista estruturada `[{"tema": ..., "detalhe": ...}]`, persistida separada
  pra análise e pra pré-preencher o formulário em sessões futuras.

Função pura, sem I/O, sem depender do Gradio -- fácil de testar isolada.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

INTEREST_THEMES: List[str] = [
    "Esportes",
    "Música",
    "Jogos",
    "Séries e filmes",
    "Culinária",
    "Leitura",
    "Arte e desenho",
    "Viagens",
    "Academia e treino",
    "Tecnologia",
    "Animais",
    "Outro",
]

MAX_THEMES = 3

# Nenhum exemplo usa futebol de propósito -- é o exemplo mais repetido nas
# demonstrações do projeto e não deve enviesar o que o aluno escreve aqui.
INTEREST_PLACEHOLDERS: Dict[str, str] = {
    "Esportes": "Ex: qual modalidade você pratica ou acompanha",
    "Música": "Ex: estilos ou artistas que você mais escuta",
    "Jogos": "Ex: que tipo de jogo ou qual jogo em especial",
    "Séries e filmes": "Ex: gêneros ou títulos favoritos",
    "Culinária": "Ex: tipo de comida ou receita que gosta de preparar",
    "Leitura": "Ex: gêneros ou livros que você costuma ler",
    "Arte e desenho": "Ex: técnica ou estilo que você pratica",
    "Viagens": "Ex: lugares que já conheceu ou quer conhecer",
    "Academia e treino": "Ex: modalidade de treino ou objetivo atual",
    "Tecnologia": "Ex: área de tecnologia que mais te interessa",
    "Animais": "Ex: tipo de animal ou pet que você tem",
    "Outro": "Descreva seu interesse (obrigatório)",
}


def serialize_interests(
    selected: Optional[List[str]], details: Optional[Dict[str, str]]
) -> Tuple[str, List[Dict[str, str]]]:
    """Monta (a) a string livre que o prompt base já lê e (b) a lista
    estruturada persistida separadamente pra análise."""

    selected = list(selected or [])[:MAX_THEMES]
    details = details or {}
    parts: List[str] = []
    structured: List[Dict[str, str]] = []
    for theme in selected:
        detail = (details.get(theme) or "").strip()
        structured.append({"tema": theme, "detalhe": detail})
        parts.append(f"{theme} ({detail})" if detail else theme)
    return "; ".join(parts), structured


def validate_selection(
    selected: Optional[List[str]], details: Optional[Dict[str, str]]
) -> Optional[str]:
    """Retorna uma mensagem de erro, ou None se a seleção é válida.

    Regras: no máximo `MAX_THEMES` temas; "Outro" exige descrição, já que
    não tem rótulo próprio pro PAGE ancorar a analogia.
    """

    selected = list(selected or [])
    if len(selected) > MAX_THEMES:
        return f"Máximo de {MAX_THEMES} temas."
    details = details or {}
    if "Outro" in selected and not (details.get("Outro") or "").strip():
        return 'Descreva o interesse em "Outro" antes de continuar.'
    return None


def deserialize_structured(
    structured: Optional[List[Dict[str, str]]]
) -> Tuple[List[str], Dict[str, str]]:
    """Reconstrói (selecionados, detalhes) a partir do JSON persistido --
    usado pra pré-preencher o formulário quando o aluno já tem perfil salvo
    de uma sessão anterior."""

    structured = structured or []
    selected: List[str] = []
    details: Dict[str, str] = {}
    for item in structured:
        theme = (item or {}).get("tema")
        if not theme or theme not in INTEREST_THEMES or theme in selected:
            continue
        selected.append(theme)
        detail = (item.get("detalhe") or "").strip()
        if detail:
            details[theme] = detail
    return selected[:MAX_THEMES], details
