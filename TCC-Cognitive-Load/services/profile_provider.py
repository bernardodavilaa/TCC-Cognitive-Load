# services/profile_provider.py
"""Provedor provisório do perfil cognitivo-afetivo do aluno.

Este módulo é um substituto temporário para o Agente de Perfil
Cognitivo-Afetivo (Módulo 1 do TCC, ainda não implementado). Ele monta o
perfil a partir dos campos já coletados no formulário de configuração do
chat da sala, por sessão — sem persistência entre sessões.

Quando o Agente de Perfil existir, `build_interim_profile` deve ser trocada
por uma função que busca o perfil persistido na tabela
`perfil_cognitivo_afetivo` do Supabase, mantendo o mesmo formato de dict de
saída — sem exigir mudanças em `page_prompt_builder.py` ou em `bot()`.
"""
from __future__ import annotations

from typing import Optional


def build_interim_profile(
    estilo: Optional[str],
    detalhamento: Optional[str],
    interesses: Optional[str],
    prior_experience: Optional[str],
    self_rating,
) -> dict:
    """Normaliza os campos do formulário de sala num dict de perfil.

    `self_rating` é aceito como int, str numérica ou None/"" (não informado);
    é sempre limitado ao intervalo 1-5.
    """

    try:
        rating = (
            int(self_rating)
            if self_rating is not None and str(self_rating).strip() != ""
            else None
        )
    except (TypeError, ValueError):
        rating = None
    if rating is not None:
        rating = max(1, min(5, rating))

    return {
        "learning_style": (estilo or "").strip(),
        "detail_level": (detalhamento or "").strip(),
        "hobbies": (interesses or "").strip(),
        "prior_experience": (prior_experience or "").strip(),
        "self_rating": rating,
    }
