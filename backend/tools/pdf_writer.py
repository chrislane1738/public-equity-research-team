"""reportlab one-page PDF writer for the executive summary."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                 TableStyle)


def write_one_pager(
    path: Path,
    ticker: str,
    rating: str,
    price_target: float,
    current_price: float,
    thesis_bullets: list[str],
    triangulation_rows: list[tuple[str, float, float]],
    top_risks: list[str],
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("h_title", parent=styles["Heading1"],
                             fontSize=18, spaceAfter=6)
    h_section = ParagraphStyle("h_section", parent=styles["Heading2"],
                               fontSize=12, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=11)

    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []

    upside = (price_target - current_price) / current_price * 100 if current_price else 0
    story.append(Paragraph(
        f"{ticker} — {rating}  ·  PT ${price_target:.0f}  ·  "
        f"Current ${current_price:.0f}  ·  Upside {upside:+.1f}%", h_title))

    story.append(Paragraph("Investment Thesis", h_section))
    for b in thesis_bullets:
        story.append(Paragraph(f"• {b}", body))

    story.append(Paragraph("Valuation Triangulation", h_section))
    table_data = [["Method", "Implied price", "Weight"]]
    for label, price, weight in triangulation_rows:
        table_data.append([label, f"${price:.0f}", f"{weight*100:.0f}%"])
    tbl = Table(table_data, colWidths=[3.5 * inch, 2.0 * inch, 2.0 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(tbl)

    story.append(Paragraph("Top risks", h_section))
    for r in top_risks:
        story.append(Paragraph(f"• {r}", body))

    story.append(Spacer(1, 0.1 * inch))
    doc.build(story)
