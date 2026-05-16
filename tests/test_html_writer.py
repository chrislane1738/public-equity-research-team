"""HTML report assembler — deterministic Python templating, no LLM call."""
import base64
from pathlib import Path

import pytest

from tools.html_writer import (
    _build_rail,
    encode_image_as_data_uri,
    render_section,
    write_report_html,
    _extract_masthead,
    _strip_first_h1,
    _prefix_heading_ids,
    _wrap_figures,
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


def test_prefix_heading_ids_prefixes_and_collects_h2():
    html = '<h2 id="balance-sheet">Balance Sheet</h2><p>x</p><h2 id="kpis">KPIs</h2>'
    out, subs = _prefix_heading_ids(html, "fundamentals")
    assert 'id="fundamentals__balance-sheet"' in out
    assert 'id="fundamentals__kpis"' in out
    assert subs == [
        ("fundamentals__balance-sheet", "Balance Sheet"),
        ("fundamentals__kpis", "KPIs"),
    ]


def test_prefix_heading_ids_unique_across_pods():
    html = '<h2 id="data-gaps">Data Gaps</h2>'
    out_a, _ = _prefix_heading_ids(html, "industry")
    out_b, _ = _prefix_heading_ids(html, "macro")
    assert 'id="industry__data-gaps"' in out_a
    assert 'id="macro__data-gaps"' in out_b


def test_prefix_heading_ids_strips_tags_from_label():
    html = '<h2 id="x">Plain <em>and</em> fancy</h2>'
    _, subs = _prefix_heading_ids(html, "dcf")
    assert subs == [("dcf__x", "Plain and fancy")]


def test_prefix_heading_ids_ignores_headings_without_id():
    html = "<h2>No id here</h2>"
    out, subs = _prefix_heading_ids(html, "risk")
    assert out == html
    assert subs == []


def test_wrap_figures_wraps_standalone_img():
    html = '<p><img alt="Football field" src="data:image/png;base64,AAA"></p>'
    out = _wrap_figures(html)
    assert "<figure>" in out
    assert "<figcaption>Football field</figcaption>" in out
    assert 'src="data:image/png;base64,AAA"' in out
    assert "<p>" not in out


def test_wrap_figures_leaves_text_paragraphs_alone():
    html = "<p>A paragraph with no image.</p>"
    assert _wrap_figures(html) == html


def test_wrap_figures_handles_img_without_alt():
    html = '<p><img src="data:image/png;base64,AAA"></p>'
    out = _wrap_figures(html)
    assert "<figure>" in out
    assert "<figcaption>" not in out


def test_build_rail_emits_section_link_and_chevron():
    nav = [("fundamentals", "Fundamentals", [("fundamentals__bs", "Balance Sheet")])]
    rail = _build_rail(nav)
    assert rail.startswith('<nav id="rail">')
    assert 'data-sec="fundamentals"' in rail
    assert 'href="#fundamentals"' in rail
    assert 'href="#fundamentals__bs"' in rail
    assert 'class="chev"' in rail


def test_build_rail_no_chevron_without_subsections():
    rail = _build_rail([("technicals", "Technicals", [])])
    assert 'data-sec="technicals"' in rail
    assert 'class="chev"' not in rail
    assert 'class="subnav"' not in rail
