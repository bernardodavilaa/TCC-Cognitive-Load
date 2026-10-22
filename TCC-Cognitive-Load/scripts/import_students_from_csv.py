"""Importa o pré-cadastro de alunos (nome, e-mail PUC, matrícula) coletado
via Google Forms para a tabela `users`, como contas prontas para uso.

Login = e-mail institucional; senha inicial = a própria matrícula do aluno
(decisão consciente do projeto: reduzir ao máximo o atrito/risco de falha no
dia do teste, num estudo acadêmico de curta duração).

Uso:
    python scripts/import_students_from_csv.py respostas.csv

O CSV é o export padrão de respostas do Google Forms (Respostas > planilha >
Arquivo > Fazer download > .csv). Ajuste `HEADER_MAP` abaixo se os nomes das
colunas do seu Forms forem diferentes.

Idempotente: pode ser executado de novo com um CSV atualizado sem duplicar
quem já foi importado (e-mail/username são UNIQUE na tabela).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import (  # noqa: E402
    SUPABASE_PROFILE_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
    SUPABASE_USERS_TABLE,
)
from services.auth_store import _hashPw  # noqa: E402
from services.supabase.common import (  # noqa: E402
    SupabaseUserExistsError,
    create_user_record,
    fetch_user_record,
)
from services.supabase.student import upsert_student_profile  # noqa: E402

# Nomes das colunas no CSV exportado do Forms -> chave interna usada aqui.
# Ajuste o lado esquerdo se o cabeçalho do seu Forms for diferente.
HEADER_MAP = {
    "Nome completo": "nome",
    "E-mail institucional PUC": "email",
    "Matrícula (Ex: 776775)": "matricula",
    "Curso e período atual": "curso_periodo",
}


def _normalize_row(raw_row: dict) -> dict:
    row = {}
    for csv_header, key in HEADER_MAP.items():
        row[key] = (raw_row.get(csv_header) or "").strip()
    return row


def main(csv_path: str) -> None:
    path = Path(csv_path)
    if not path.is_file():
        print(f"Arquivo não encontrado: {csv_path}")
        sys.exit(1)

    created = 0
    already_existing = 0
    curso_periodo_atualizado = 0
    errors = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, raw_row in enumerate(reader, start=2):  # linha 1 = cabeçalho
            row = _normalize_row(raw_row)
            nome = row.get("nome", "")
            email = row.get("email", "").lower()
            matricula = row.get("matricula", "")
            curso_periodo = row.get("curso_periodo", "")

            if not nome or not email or not matricula:
                errors.append(f"linha {i}: nome/e-mail/matrícula ausente, pulando")
                continue

            try:
                create_user_record(
                    SUPABASE_URL,
                    SUPABASE_SERVICE_ROLE_KEY,
                    SUPABASE_USERS_TABLE,
                    login=email,
                    password_hash=_hashPw(matricula),
                    role="student",
                    username=email,
                    full_name=nome,
                    matricula=matricula,
                )
                created += 1
            except SupabaseUserExistsError:
                already_existing += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"linha {i} ({email}): {exc}")
                continue

            # Curso/período vem do cadastro, nunca é perguntado de novo
            # dentro do Modo Estudo -- grava aqui (idempotente: roda de novo
            # sem problema, inclusive pra backfill de quem já existia).
            if curso_periodo:
                try:
                    user = fetch_user_record(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_USERS_TABLE, email)
                    if user and user.id:
                        upsert_student_profile(
                            SUPABASE_URL,
                            SUPABASE_SERVICE_ROLE_KEY,
                            SUPABASE_PROFILE_TABLE,
                            user.id,
                            curso_periodo=curso_periodo,
                        )
                        curso_periodo_atualizado += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"linha {i} ({email}): falha ao salvar curso/período ({exc})")

    print(f"Criados: {created}")
    print(f"Já cadastrados (pulados): {already_existing}")
    print(f"Curso/período atualizado: {curso_periodo_atualizado}")
    if errors:
        print(f"Erros ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/import_students_from_csv.py <caminho_do_csv>")
        sys.exit(1)
    main(sys.argv[1])
