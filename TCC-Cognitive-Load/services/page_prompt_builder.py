# services/page_prompt_builder.py
"""Módulo PAGE de Reformatação Contextual — construção do prompt.

Monta os `messages` para a segunda chamada ao Vertex AI que reformata a
resposta já gerada pelo tutor base, ancorando-a no perfil do aluno e
orientada pelos três referenciais pedagógicos do framework PAGE (LIM et al.,
2025): Taxonomia de Bloom (profundidade), Zona de Desenvolvimento Proximal
de Vygotsky (quantidade de suporte) e Universal Design for Learning
(formato de apresentação).

Função pura, sem I/O — o `messages` retornado é consumido por
`services.vertex_client._streamFromVertex`, a mesma função já usada pela
chamada base.
"""
from __future__ import annotations

from typing import Optional


def _infer_bloom_level(prior_experience: Optional[str], self_rating) -> str:
    """Estima o nível provável da Taxonomia de Bloom a partir de sinais explícitos."""

    prior = (prior_experience or "").strip().lower()
    try:
        rating = int(self_rating) if self_rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None

    if prior in ("não", "nao") or (rating is not None and rating <= 1):
        return "lembrar e compreender (aluno iniciante, sem contato prévio com o tema)"
    if prior == "sim" and rating is not None and rating >= 4:
        return "aplicar e analisar (aluno já possui base sólida no tema)"
    return "compreender e aplicar (aluno com conhecimento parcial ou não informado)"


def _describe_zpd_support(self_rating, ritmo_estudo: Optional[str] = None) -> str:
    """Calibra a quantidade de suporte/scaffolding conforme a ZPD de Vygotsky.

    `ritmo_estudo` é o sinal de triagem (RF novo) de que o aluno sente mais
    dificuldade de ritmo que a média da turma -- quando presente, força
    suporte máximo mesmo que a autoavaliação (`self_rating`) não seja baixa,
    já que um aluno pode superestimar o próprio nível por insegurança.
    """

    necessita_mais_suporte = (ritmo_estudo or "").strip().lower() == "dificuldade"

    try:
        rating = int(self_rating) if self_rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None

    if necessita_mais_suporte or rating is None or rating <= 2:
        base = (
            "ofereça bastante suporte explícito: dicas, decomposição em sub-passos "
            "e um exemplo resolvido antes de pedir qualquer autonomia do aluno."
        )
        if necessita_mais_suporte:
            base += (
                " Vá com calma: quebre em passos ainda menores que o normal, "
                "confirme o entendimento a cada etapa antes de avançar, e não "
                "pressuponha conhecimento de apoio que o aluno pode não ter tido."
            )
        return base
    if rating >= 4:
        return (
            "ofereça suporte mínimo: aponte a direção geral e deixe o aluno aplicar "
            "o raciocínio, evitando entregar passos prontos."
        )
    return (
        "ofereça suporte moderado: uma dica ou decomposição parcial, sem resolver "
        "o problema inteiro pelo aluno."
    )


def _describe_udl_format(
    learning_style: Optional[str],
    detail_level: Optional[str],
    ritmo_estudo: Optional[str] = None,
) -> str:
    """Varia o formato de apresentação conforme os princípios do UDL."""

    style = (learning_style or "").strip().lower()
    detail = (detail_level or "").strip().lower()
    necessita_mais_suporte = (ritmo_estudo or "").strip().lower() == "dificuldade"

    if necessita_mais_suporte:
        # Prevalece sobre o estilo pedido: um aluno com dificuldade pode ter
        # escolhido "técnicas" por insegurança/orgulho, mas o objetivo aqui é
        # reduzir carga cognitiva de verdade.
        base = (
            "use linguagem bem simples e concreta mesmo que o estilo pedido seja "
            "técnico -- evite jargão sem explicar antes, prefira frases curtas e "
            "exemplos do dia a dia que não pressuponham acesso a livros, internet "
            "ou aulas de reforço fora da sala de aula"
        )
    elif style in ("técnicas", "tecnicas"):
        base = "use linguagem técnica precisa, com termos específicos quando pertinente"
    else:
        base = "use linguagem simples e acessível, evitando jargão desnecessário"

    if detail == "curtas":
        base += ", em formato direto e conciso"
    else:
        base += ", com explicação passo a passo quando fizer sentido"

    return base


def build_page_messages(base_response: str, profile: Optional[dict], *, subject: str = "") -> list:
    """Monta os `messages` de reformatação contextual para o Vertex AI.

    `profile` é o dict retornado por `services.profile_provider.build_interim_profile`
    (ou, futuramente, pelo Agente de Perfil Cognitivo-Afetivo persistido).
    """

    profile = profile or {}
    hobbies = (profile.get("hobbies") or "").strip()
    hobbies_detail = (profile.get("hobbies_detail") or "").strip()
    learning_style = profile.get("learning_style")
    detail_level = profile.get("detail_level")
    prior_experience = profile.get("prior_experience")
    self_rating = profile.get("self_rating")
    ritmo_estudo = profile.get("ritmo_estudo")

    bloom_level = _infer_bloom_level(prior_experience, self_rating)
    zpd_support = _describe_zpd_support(self_rating, ritmo_estudo)
    udl_format = _describe_udl_format(learning_style, detail_level, ritmo_estudo)

    if hobbies and hobbies_detail:
        hobbies_line = (
            f"Interesses/hobbies declarados pelo aluno: {hobbies}. "
            f"O próprio aluno descreveu sua experiência assim: \"{hobbies_detail}\". "
            "Use esses detalhes concretos para construir a analogia, não só o rótulo do tema."
        )
    elif hobbies:
        hobbies_line = f"Interesses/hobbies declarados pelo aluno: {hobbies}."
    else:
        hobbies_line = "O aluno não declarou interesses específicos; use exemplos genéricos do cotidiano."

    system_content = (
        "Você é o Módulo PAGE de Reformatação Contextual, uma segunda camada que "
        "reformata (sem alterar o conteúdo técnico de) uma resposta já gerada por "
        "um tutor de programação, ancorando-a no perfil do aluno.\n\n"
        f"Tema da sessão: {subject or 'não informado'}.\n"
        f"{hobbies_line}\n"
        f"Nível provável na Taxonomia de Bloom: {bloom_level}. Calibre a profundidade "
        "da explicação de acordo, sem simplificar nem complicar além do necessário.\n"
        f"Zona de Desenvolvimento Proximal (ZPD): {zpd_support}\n"
        f"Universal Design for Learning (UDL): {udl_format}\n\n"
        "Regras:\n"
        "- Reformate a resposta original substituindo exemplos e analogias abstratas "
        "por referências ancoradas nos interesses do aluno, sem alterar a correção "
        "técnica do conteúdo original.\n"
        "- Não invente informação nova nem remova conteúdo pedagogicamente essencial.\n"
        "- Responda apenas com o texto reformatado final, sem comentários sobre o "
        "processo de reformatação.\n"
        "- Nunca mencione ao aluno que a explicação foi adaptada por causa de "
        "alguma resposta que ele deu em formulário (nível, ritmo de estudo, "
        "interesses, etc.) -- apenas entregue o texto já adaptado, sem comentar "
        "o motivo.\n"
        "- Responda em português do Brasil."
    )

    user_content = f"Resposta original do tutor, a ser reformatada:\n\n{base_response}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
