"""HTML report assembler — deterministic Python templating, no LLM call."""
import base64
from pathlib import Path

import pytest

from tools.html_writer import (
    encode_image_as_data_uri,
    render_section,
    write_report_html,
    _extract_masthead,
    _strip_first_h1,
)


def test_encode_image_as_data_uri(tmp_path):
    png = tmp_path / "chart.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")
    uri = encode_image_as_data_uri(png)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == b"\x89PNG\r\n\x1a\nfake-png-bytes"


def test_encode_image_returns_empty_for_missing_file(tmp_path):
    assert encode_image_as_data_uri(tmp_path / "nope.png") == ""


def test_render_section_converts_markdown_to_html(tmp_path):
    section_md = tmp_path / "section.md"
    section_md.write_text("# Heading\n\n- bullet one\n- bullet two\n")
    html = render_section(section_md)
    assert "<h1>" in html
    assert "<li>bullet one</li>" in html


def test_render_section_returns_placeholder_for_missing_file(tmp_path):
    html = render_section(tmp_path / "missing.md")
    assert "not produced" in html.lower()


def test_write_report_html_assembles_self_contained_file(tmp_path):
    # Build a minimal ticker tree
    ticker_dir = tmp_path / "NVDA"
    for pod in ("fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals", "synthesis"):
        (ticker_dir / pod).mkdir(parents=True)
        (ticker_dir / pod / "section.md").write_text(f"# {pod}\n\nContent for {pod}.\n")
    (ticker_dir / "synthesis" / "_synthesis.md").write_text("# Synthesis\n\nRating: Buy. PT $200.\n")
    (ticker_dir / "reports").mkdir()
    (ticker_dir / "reports" / "memo.docx").write_bytes(b"")
    (ticker_dir / "reports" / "pitch.pptx").write_bytes(b"")

    out = write_report_html(ticker_dir, ticker="NVDA")

    assert out == ticker_dir / "report.html"
    html = out.read_text()
    assert "<html" in html
    assert "<style>" in html  # inline CSS
    assert "@media print" in html
    assert 'href="reports/memo.docx"' in html
    assert 'href="reports/pitch.pptx"' in html
    assert "Rating: Buy" in html  # synthesis included
    assert "Content for fundamentals" in html


def test_write_report_html_embeds_png_charts_as_base64(tmp_path):
    ticker_dir = tmp_path / "NVDA"
    (ticker_dir / "dcf").mkdir(parents=True)
    (ticker_dir / "dcf" / "section.md").write_text("# DCF\n\n![Football](football-field.png)\n")
    (ticker_dir / "dcf" / "football-field.png").write_bytes(b"\x89PNGfake")
    for pod in ("fundamentals", "industry", "comps", "macro", "risk", "technicals", "synthesis"):
        (ticker_dir / pod).mkdir(parents=True)
        (ticker_dir / pod / "section.md").write_text(f"# {pod}\n")
    (ticker_dir / "synthesis" / "_synthesis.md").write_text("# Synthesis\n")

    out = write_report_html(ticker_dir, ticker="NVDA")
    html = out.read_text()
    assert "data:image/png;base64," in html
    # original relative path should NOT remain (we replaced it with the data URI)
    assert 'src="football-field.png"' not in html


def test_write_report_html_skips_missing_companion_links(tmp_path):
    ticker_dir = tmp_path / "NVDA"
    for pod in ("fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals", "synthesis"):
        (ticker_dir / pod).mkdir(parents=True)
        (ticker_dir / pod / "section.md").write_text(f"# {pod}\n")
    (ticker_dir / "synthesis" / "_synthesis.md").write_text("# Synthesis\n")
    # No reports/ subdir, no xlsx

    out = write_report_html(ticker_dir, ticker="NVDA")
    html = out.read_text()
    assert 'href="reports/memo.docx"' not in html
    assert 'href="reports/pitch.pptx"' not in html


REAL_SYNTH = """# MU — Managing Director Synthesis

**Micron Technology, Inc. (MU)** | Technology / Semiconductors (Memory)
Synthesis date: 2026-05-16 | Reference price: **$724.66** | Market cap ~ $817B

## Rating: **SELL**

## Price Target: **$400** (~ -45% from $724.66)
"""


def test_extract_masthead_happy_path():
    m = _extract_masthead(REAL_SYNTH)
    assert m["rating"] == "SELL"
    assert m["rating_class"] == "sell"
    assert m["price_target"] == "$400"
    assert m["date"] == "2026-05-16"
    assert m["spot"] == "724.66"
    assert m["ticker"] == "MU"
    assert m["company"] == "Micron Technology, Inc. — MU"


def test_extract_masthead_fallback_when_rating_missing():
    assert _extract_masthead("# Synthesis\n\nNo rating here.\n") == {}


def test_extract_masthead_fallback_when_pt_missing():
    assert _extract_masthead("## Rating: **BUY**\n\nNo target.\n") == {}


def test_extract_masthead_buy_and_hold_classes():
    buy = _extract_masthead("## Rating: **BUY**\n\n## Price Target: **$200**\n")
    assert buy["rating_class"] == "buy"
    hold = _extract_masthead("## Rating: **Hold**\n\n## Price Target: **$150**\n")
    assert hold["rating_class"] == "hold"


def test_strip_first_h1_removes_only_first():
    html = "<h1 id='a'>Title</h1><p>x</p><h1>Second</h1>"
    out = _strip_first_h1(html)
    assert "Title" not in out
    assert "<p>x</p>" in out
    assert "Second" in out


def test_strip_first_h1_noop_without_h1():
    html = "<h2>Sub</h2><p>body</p>"
    assert _strip_first_h1(html) == html
