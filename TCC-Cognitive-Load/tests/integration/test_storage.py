"""Integração: round-trip de arquivo no Supabase Storage."""

import pytest

from services.supabase_client import (
    SupabaseOperationError,
    delete_file_from_bucket,
    download_file_from_bucket,
    upload_file_to_bucket,
)
from tests._helpers import make_pdf, tag

pytestmark = pytest.mark.integration


@pytest.fixture
def creds(cfg):
    return cfg.SUPABASE_URL, cfg.SUPABASE_SERVICE_ROLE_KEY


def test_upload_download_delete_roundtrip(creds, cfg, tmp_path):
    url, key = creds
    bucket = cfg.SUPABASE_CHAT_BUCKET
    local = make_pdf(tmp_path / "chat.pdf", "conteudo pytest storage")
    remote = f"pytest/{tag()}.pdf"

    stored = upload_file_to_bucket(
        url, key, bucket=bucket, file_path=local, storage_path=remote,
        content_type="application/pdf", upsert=True,
    )
    try:
        data = download_file_from_bucket(url, key, bucket=bucket, storage_path=remote)
        assert isinstance(data, bytes) and data == open(local, "rb").read()
    finally:
        delete_file_from_bucket(url, key, bucket=bucket, storage_path=remote)

    with pytest.raises(SupabaseOperationError):
        download_file_from_bucket(url, key, bucket=bucket, storage_path=remote)
