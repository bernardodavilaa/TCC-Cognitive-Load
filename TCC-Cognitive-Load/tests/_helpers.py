"""Utilidades compartilhadas pelos testes."""

from __future__ import annotations

import uuid

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

TEST_PASSWORD = "pytest-secret-123"
PREFIX = "pytest_"


def tag(extra: str = "") -> str:
    """Identificador único e reconhecível para dados de teste."""
    return f"{PREFIX}{extra}{uuid.uuid4().hex[:8]}"


def make_pdf(path: str, text: str = "Material de teste pytest") -> str:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return str(path)
