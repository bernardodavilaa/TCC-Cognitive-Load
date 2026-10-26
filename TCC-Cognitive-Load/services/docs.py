# services/docs.py
from datetime import datetime
import os
from xml.sax.saxutils import escape as _xmlEscape

import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


def _pdfSafeText(text: str) -> str:
    """Escapa o texto pro mini-XML que o Paragraph do ReportLab entende
    antes de inserir `<br/>` -- sem isso, qualquer `&algumacoisa;` no meio
    do texto (comum em código C: `&variavel;`, ex. `scanf("%d", &x);`) é
    interpretado como entidade XML e corrompe o PDF (achado real: nome de
    variável virou um quadrado preto num PDF de aluna real)."""
    return _xmlEscape(str(text)).replace("\n", "<br/>")


def extractPdfText(filePath: str) -> str:
    textParts = []
    with fitz.open(filePath) as doc:
        for page in doc:
            textParts.append(page.get_text("text"))
    text = "\n".join(textParts)
    return text[:20000]


def createChatPdf(history, docsState):
    # use um diretório local válido
    outDir = "./output_pdfs"
    os.makedirs(outDir, exist_ok=True)  # garante que a pasta exista

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outPath = os.path.join(outDir, f"chat_{timestamp}.pdf")

    doc = SimpleDocTemplate(outPath, pagesize=letter, leftMargin=36,
                            rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    body = []

    titleStyle = ParagraphStyle(
        "title", parent=styles["Heading1"], alignment=1, spaceAfter=12)
    metaStyle = ParagraphStyle(
        "meta", parent=styles["Normal"], fontSize=10, textColor="#555555", spaceAfter=6)
    userStyle = ParagraphStyle(
        "user", parent=styles["Normal"], spaceBefore=6, spaceAfter=6)
    asstStyle = ParagraphStyle(
        "asst", parent=styles["Normal"], textColor="#1E3A8A", spaceBefore=6, spaceAfter=12)

    body.append(Paragraph("Relatório de Conversa", titleStyle))
    body.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", metaStyle))
    body.append(Spacer(1, 0.2 * inch))

    if isinstance(docsState, dict) and docsState:
        body.append(
            Paragraph("<b>Documentos ativos (amostra):</b>", styles["Heading3"]))
        for name, content in docsState.items():
            preview = (content[:600] +
                       "...") if len(content) > 600 else content
            body.append(Paragraph(
                f"<b>{_xmlEscape(str(name))}</b><br/>{_pdfSafeText(preview)}", styles["Normal"]))
            body.append(Spacer(1, 0.1 * inch))
        body.append(PageBreak())

    body.append(Paragraph("<b>Conversa:</b>", styles["Heading3"]))
    if isinstance(history, list):
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if content is None:
                continue
            content = _pdfSafeText(content)
            if role == "user":
                body.append(Paragraph(f"<b>Usuário</b>: {content}", userStyle))
            elif role == "assistant":
                body.append(
                    Paragraph(f"<b>Assistente</b>: {content}", asstStyle))
            else:
                body.append(
                    Paragraph(f"<b>{_xmlEscape(str(role or 'mensagem'))}</b>: {content}", styles["Normal"]))

    doc.build(body)
    return outPath
