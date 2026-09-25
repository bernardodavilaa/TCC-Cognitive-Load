"""Configuração central da aplicação.

Este arquivo NÃO é versionado (está listado no .gitignore). Cada ambiente
deve preencher as credenciais abaixo, seja editando os valores padrão ou
definindo as variáveis de ambiente correspondentes (recomendado).

Credenciais necessárias:
  1. Supabase  -> SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
  2. Vertex AI -> JSON da conta de serviço do Google Cloud
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Carrega um arquivo .env simples para os.environ (sem sobrescrever)."""

    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv(_ROOT / ".env")


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
# Painel do Supabase -> Project Settings -> API
#   * Project URL           -> SUPABASE_URL
#   * Project API keys / service_role (secret) -> SUPABASE_SERVICE_ROLE_KEY
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://SEU_PROJETO.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or "SUPABASE_SERVICE_ROLE_KEY"
)

# Tabela de usuários criada por DB/databaseCreationSQL.sql
SUPABASE_USERS_TABLE = os.environ.get("SUPABASE_USERS_TABLE", "users")

# Tabela de perfil cognitivo-afetivo (persistência entre sessões p/ o PAGE)
SUPABASE_PROFILE_TABLE = os.environ.get(
    "SUPABASE_PROFILE_TABLE", "perfil_cognitivo_afetivo"
)

# Rastreabilidade de acesso (login) e avaliação pós-chat (Paas/Likert)
SUPABASE_ACCESS_LOGS_TABLE = os.environ.get(
    "SUPABASE_ACCESS_LOGS_TABLE", "access_logs"
)
SUPABASE_EVALUATIONS_TABLE = os.environ.get(
    "SUPABASE_EVALUATIONS_TABLE", "student_evaluations"
)

# Buckets do Supabase Storage (crie-os no painel -> Storage e mantenha os
# mesmos nomes aqui). O prefixo é apenas a "pasta" raiz dentro do bucket.
SUPABASE_CHAT_BUCKET = os.environ.get("SUPABASE_CHAT_BUCKET", "chat-pdfs")
SUPABASE_CHAT_STORAGE_PREFIX = os.environ.get("SUPABASE_CHAT_STORAGE_PREFIX", "chats")
SUPABASE_CLASS_DOCS_BUCKET = os.environ.get(
    "SUPABASE_CLASS_DOCS_BUCKET", "classroom-documents"
)
SUPABASE_CLASS_DOCS_PREFIX = os.environ.get(
    "SUPABASE_CLASS_DOCS_PREFIX", "classrooms"
)


# ---------------------------------------------------------------------------
# Mapeamento de papéis (rótulo em PT-BR usado na UI  <->  enum do banco)
# ---------------------------------------------------------------------------
ROLE_PT_TO_DB = {
    "aluno": "student",
    "professor": "teacher",
    "admin": "admin",
    "administrador": "admin",
}

ROLE_DB_TO_PT = {
    "student": "aluno",
    "teacher": "professor",
    "admin": "admin",
}


# ---------------------------------------------------------------------------
# Vertex AI - conta de serviço do Google Cloud
# ---------------------------------------------------------------------------
def _load_service_account() -> dict:
    """Carrega o JSON da conta de serviço a partir de várias origens.

    Ordem de tentativa:
      1. GOOGLE_APPLICATION_CREDENTIALS / VERTEX_SERVICE_ACCOUNT_FILE -> caminho de arquivo
      2. VERTEX_SERVICE_ACCOUNT_JSON -> conteúdo JSON completo em variável de ambiente
      3. Campos individuais GCP_* (ver README)
      4. Arquivo service_account.json na raiz do projeto

    Nunca levanta exceção: se nada for encontrado, devolve {} e a aplicação
    inicia mostrando um aviso de "Vertex indisponível".
    """

    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get(
        "VERTEX_SERVICE_ACCOUNT_FILE"
    )
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = _ROOT / candidate
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raw = os.environ.get("VERTEX_SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    if os.environ.get("GCP_PROJECT_ID"):
        return {
            "type": "service_account",
            "project_id": os.environ["GCP_PROJECT_ID"],
            "private_key_id": os.environ.get("GCP_PRIVATE_KEY_ID", ""),
            # Em .env a chave normalmente vem com "\n" literais.
            "private_key": os.environ.get("GCP_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.environ.get("GCP_CLIENT_EMAIL", ""),
            "client_id": os.environ.get("GCP_CLIENT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("GCP_CLIENT_X509_CERT_URL", ""),
        }

    for candidate in ("service_account.json", "supakeys.json"):
        default_file = _ROOT / candidate
        if default_file.is_file():
            try:
                data = json.loads(default_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("project_id"):
                    return data
            except (json.JSONDecodeError, OSError):
                continue

    return {}


VERTEX_SERVICE_ACCOUNT = _load_service_account()

# Região e modelo do Vertex (opcionais)
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash")
