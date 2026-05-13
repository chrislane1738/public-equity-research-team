import re
from pathlib import Path

from backend.tools.pdf_writer import write_one_pager


def _count_pages(pdf_bytes: bytes) -> int:
    """Count `/Type /Page` markers in the raw PDF bytes."""
    return len(re.findall(rb"/Type /Page[^s]", pdf_bytes))


def test_write_one_pager_creates_pdf(tmp_path):
    out = tmp_path / "onepager.pdf"
    write_one_pager(
        path=out,
        ticker="NVDA",
        rating="Buy",
        price_target=158.0,
        current_price=110.0,
        thesis_bullets=[
            "Data Center capex secular tailwind",
            "Pricing power across CUDA moat",
            "FCF inflection ahead of estimates",
        ],
        triangulation_rows=[
            ("DCF GGM",      116, 0.20),
            ("DCF Exit",     200, 0.30),
            ("DCF Blend",    158, 0.20),
            ("Comps median", 165, 0.20),
            ("52-wk anchor", 130, 0.10),
        ],
        top_risks=[
            "AI capex digestion",
            "China revenue restrictions",
            "Custom-silicon competition",
        ],
    )
    assert out.exists()
    body = out.read_bytes()
    assert body.startswith(b"%PDF-")
    # Reasonable size — a single page with text and a table is ≥1 KB
    assert len(body) > 1500
    assert _count_pages(body) == 1, f"expected 1-page PDF, got {_count_pages(body)}"


def test_write_one_pager_handles_long_thesis(tmp_path):
    out = tmp_path / "onepager.pdf"
    long_bullet = "x" * 250
    write_one_pager(
        path=out, ticker="NVDA", rating="Buy",
        price_target=158, current_price=110,
        thesis_bullets=[long_bullet, long_bullet, long_bullet],
        triangulation_rows=[("DCF Blend", 158, 1.0)],
        top_risks=["risk one", "risk two", "risk three"],
    )
    assert out.exists() and out.stat().st_size > 1500
    assert _count_pages(out.read_bytes()) == 1, "long-thesis input should still fit on one page"
