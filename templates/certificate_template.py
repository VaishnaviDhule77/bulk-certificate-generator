"""ReportLab layout for the predefined certificate template.

This module only *draws* a certificate. It knows nothing about databases,
jobs, or HTTP, which keeps the layout easy to change.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

NAVY = HexColor("#1F3A5F")
GOLD = HexColor("#C9A227")
GREY = HexColor("#5A5A5A")
TEXT = HexColor("#222222")

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

# Y coordinates of each text baseline (points from the BOTTOM of the page).
TITLE_Y = PAGE_HEIGHT - 50 * mm
SUBTITLE_Y = PAGE_HEIGHT - 78 * mm
NAME_Y = PAGE_HEIGHT - 108 * mm
NAME_RULE_Y = PAGE_HEIGHT - 114 * mm
EVENT_LABEL_Y = PAGE_HEIGHT - 132 * mm
EVENT_Y = PAGE_HEIGHT - 150 * mm
DATE_Y = PAGE_HEIGHT - 175 * mm
CERTIFICATE_CODE_Y = 25 * mm

MAX_TEXT_WIDTH = 240 * mm
MIN_FONT_SIZE = 14


@dataclass(frozen=True)
class CertificateData:
    """Every value printed on a certificate."""

    title: str
    recipient_name: str
    event_name: str
    issue_date: date
    certificate_code: str


def render_certificate(data: CertificateData, output_path: Path) -> None:
    """Render one certificate PDF (A4 landscape) to ``output_path``."""
    pdf = canvas.Canvas(str(output_path), pagesize=landscape(A4))

    _draw_border(pdf)
    _draw_centered(pdf, data.title, "Times-Bold", 30, NAVY, TITLE_Y)
    _draw_centered(
        pdf, "This certificate is proudly presented to",
        "Times-Italic", 15, GREY, SUBTITLE_Y,
    )
    _draw_centered(
        pdf, data.recipient_name,
        "Times-Bold", _fit_font_size(data.recipient_name, "Times-Bold", 36),
        TEXT, NAME_Y,
    )
    _draw_name_rule(pdf)
    _draw_centered(
        pdf, "for active participation in",
        "Times-Italic", 13, GREY, EVENT_LABEL_Y,
    )
    _draw_centered(
        pdf, data.event_name,
        "Times-Bold", _fit_font_size(data.event_name, "Times-Bold", 22),
        NAVY, EVENT_Y,
    )
    _draw_centered(
        pdf, f"Issued on {data.issue_date.strftime('%d %B %Y')}",
        "Times-Roman", 14, GREY, DATE_Y,
    )
    _draw_centered(
        pdf, f"Certificate ID: {data.certificate_code}",
        "Times-Roman", 9, GREY, CERTIFICATE_CODE_Y,
    )

    pdf.showPage()
    pdf.save()


def _draw_border(pdf: canvas.Canvas) -> None:
    """Double certificate border: thick gold outside, thin navy inside."""
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(4)
    pdf.rect(8 * mm, 8 * mm, PAGE_WIDTH - 16 * mm, PAGE_HEIGHT - 16 * mm)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1)
    pdf.rect(12 * mm, 12 * mm, PAGE_WIDTH - 24 * mm, PAGE_HEIGHT - 24 * mm)


def _draw_name_rule(pdf: canvas.Canvas) -> None:
    """Short gold line under the recipient's name."""
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.line(
        PAGE_WIDTH / 2 - 60 * mm, NAME_RULE_Y,
        PAGE_WIDTH / 2 + 60 * mm, NAME_RULE_Y,
    )


def _draw_centered(
    pdf: canvas.Canvas, text: str, font: str, size: int, color: Color, y: float
) -> None:
    """Draw one line of horizontally centered text."""
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, text)


def _fit_font_size(text: str, font: str, preferred_size: int) -> int:
    """Shrink the font size until the text fits within MAX_TEXT_WIDTH."""
    size = preferred_size
    while size > MIN_FONT_SIZE and stringWidth(text, font, size) > MAX_TEXT_WIDTH:
        size -= 1
    return size