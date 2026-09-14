"""Unit: services.docs (extração e geração de PDF, offline)."""

import os

import fitz
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from services.docs import createChatPdf, extractPdfText

pytestmark = pytest.mark.unit


@pytest.fixture
def pdf_simples(tmp_path):
    path = tmp_path / "material.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Conteudo de teste do material da sala")
    c.showPage()
    c.save()
    return str(path)


def test_extract_pdf_text(pdf_simples):
    texto = extractPdfText(pdf_simples)
    assert "Conteudo de teste do material" in texto
    assert len(texto) <= 20000


def test_create_chat_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    history = [
        {"role": "user", "content": "O que e um ponteiro?"},
        {"role": "assistant", "content": "E uma variavel que guarda um endereco."},
    ]
    out = createChatPdf(history, {"anotacoes.txt": "linha1\nlinha2"})

    assert os.path.isfile(out)
    with fitz.open(out) as doc:
        full = "\n".join(page.get_text("text") for page in doc)
    assert "Relatório de Conversa" in full
    assert "O que e um ponteiro?" in full
    assert "endereco" in full
