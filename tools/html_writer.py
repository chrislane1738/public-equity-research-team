"""Assemble a single self-contained HTML report for a ticker.

Deterministic templating — no LLM call. Inputs: per-pod section.md files + PNG
charts on disk. Output: <TICKER>/report.html with inline CSS, base64-embedded
images, and relative-path links to companion .docx/.pptx/.xlsx artifacts.

Self-contained: open in any browser, including offline. Print-friendly via
@media print.
"""
import base64
import re
from pathlib import Path

import markdown


SECTION_ORDER = [
    ("synthesis", "Executive Summary", "_synthesis.md"),
    ("fundamentals", "Fundamentals", "section.md"),
    ("industry", "Industry & Moat", "section.md"),
    ("dcf", "DCF Valuation", "section.md"),
    ("comps", "Trading Comps", "section.md"),
    ("macro", "Macro & Catalysts", "section.md"),
    ("risk", "Risks & Upside", "section.md"),
    ("technicals", "Technicals", "section.md"),
]


COMPANION_LINKS = [
    ("reports/memo.docx", "Memo (.docx)"),
    ("reports/pitch.pptx", "Pitch Deck (.pptx)"),
    ("reports/onepager.pdf", "One-Pager (.pdf)"),
    ("dcf/dcf.xlsx", "DCF Model (.xlsx)"),
    ("comps/comps.xlsx", "Comps Model (.xlsx)"),
]


CSS = """
:root { --fg: #1a1a1a; --muted: #666; --accent: #1e40af; --bg: #fff; --rule: #e5e7eb; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       max-width: 860px; margin: 2em auto; padding: 0 1.5em; color: var(--fg); background: var(--bg);
       line-height: 1.55; font-size: 16px; }
h1, h2, h3 { color: var(--fg); margin-top: 1.5em; }
h1 { border-bottom: 2px solid var(--accent); padding-bottom: 0.3em; }
h2 { border-bottom: 1px solid var(--rule); padding-bottom: 0.2em; margin-top: 2em; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: #f3f4f6; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.92em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid var(--rule); padding: 0.5em 0.8em; text-align: left; }
th { background: #f9fafb; }
img { max-width: 100%; height: auto; margin: 1em 0; }
.companion { background: #f9fafb; padding: 1em 1.2em; border-left: 3px solid var(--accent);
             margin: 2em 0; border-radius: 4px; }
.companion ul { margin: 0.3em 0 0 0; padding-left: 1.4em; }
.section { margin-bottom: 2em; }
.muted { color: var(--muted); font-size: 0.92em; }
.placeholder { color: var(--muted); font-style: italic; }

@media print {
    body { max-width: none; margin: 0; padding: 1em; font-size: 11pt; }
    h2 { page-break-after: avoid; }
    .companion { display: none; }
}
"""


_RE_NAME = re.compile(r"\*\*([^*]+?\(([A-Z][A-Z.]{0,5})\))\*\*")
_RE_RATING = re.compile(r"##\s*Rating:\s*\*\*([A-Za-z]+)\*\*")
_RE_PT = re.compile(r"##\s*Price Target:\s*\*\*([^*]+?)\*\*")
_RE_DATE = re.compile(r"Synthesis date:\s*(\d{4}-\d{2}-\d{2})")
_RE_SPOT = re.compile(r"Reference price:\s*\*{0,2}\$?([\d,.]+)")
_RE_FIRST_H1 = re.compile(r"<h1[^>]*>.*?</h1>", re.DOTALL)
_RE_HEADING_ID = re.compile(
    r'<h([1-6])([^>]*)\sid="([^"]+)"([^>]*)>(.*?)</h\1>', re.DOTALL
)
_RE_TAGS = re.compile(r"<[^>]+>")
_RE_IMG_PARA = re.compile(r"<p>\s*(<img\s+[^>]*?>)\s*</p>", re.DOTALL)
_RE_IMG_ALT = re.compile(r'alt="([^"]*)"')

_RATING_CLASS = {"BUY": "buy", "HOLD": "hold", "SELL": "sell"}


def _strip_first_h1(html: str) -> str:
    """Remove the first <h1>…</h1> — each pod section.md repeats its own title
    as an <h1>, which is redundant with the section heading the writer injects.
    """
    return _RE_FIRST_H1.sub("", html, count=1)


def _prefix_heading_ids(html: str, pod: str) -> tuple[str, list[tuple[str, str]]]:
    """Prefix every heading id with the pod name so ids are unique across the
    whole document (the markdown `toc` extension only dedupes within one render
    call, and each section.md is rendered separately).

    Returns the rewritten HTML and a list of (id, text) for the <h2> headings,
    which feed the quicklinks rail's subsection dropdown.
    """
    subsections: list[tuple[str, str]] = []

    def repl(m: re.Match) -> str:
        level, pre, hid, post, text = m.groups()
        new_id = f"{pod}__{hid}"
        if level == "2":
            label = _RE_TAGS.sub("", text).strip()
            subsections.append((new_id, label))
        return f'<h{level}{pre} id="{new_id}"{post}>{text}</h{level}>'

    return _RE_HEADING_ID.sub(repl, html), subsections


def _wrap_figures(html: str) -> str:
    """Wrap each standalone <img> (a markdown image rendered on its own line as
    a solo <p>) in a <figure>, using the image's alt-text as an italic caption.
    """

    def repl(m: re.Match) -> str:
        img = m.group(1)
        alt_m = _RE_IMG_ALT.search(img)
        caption = alt_m.group(1).strip() if alt_m else ""
        cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f"<figure>{img}{cap_html}</figure>"

    return _RE_IMG_PARA.sub(repl, html)


def _build_rail(nav: list[tuple[str, str, list[tuple[str, str]]]]) -> str:
    """Build the fixed left quicklinks rail.

    nav: list of (section_id, section_label, subsections), where subsections is
    a list of (subsection_id, subsection_label).
    """
    rows = ['<nav id="rail">', '<div class="rail-h">Contents</div>']
    for sec_id, sec_label, subs in nav:
        rows.append(f'<div class="nav-sec" data-sec="{sec_id}">')
        rows.append('<div class="nav-row">')
        rows.append(f'<a href="#{sec_id}">{sec_label}</a>')
        if subs:
            rows.append('<span class="chev">&#9654;</span>')
        rows.append('</div>')
        if subs:
            rows.append('<div class="subnav">')
            for sub_id, sub_label in subs:
                rows.append(f'<a href="#{sub_id}">{sub_label}</a>')
            rows.append('</div>')
        rows.append('</div>')
    rows.append('</nav>')
    return "\n".join(rows)


def _extract_masthead(synthesis_md: str) -> dict:
    """Parse masthead fields from _synthesis.md.

    Returns {} (caller falls back to a plain title) if either the rating or
    the price target cannot be found — the writer must never fail on a
    synthesis that drifts from the expected format.
    """
    rating_m = _RE_RATING.search(synthesis_md)
    pt_m = _RE_PT.search(synthesis_md)
    if not rating_m or not pt_m:
        return {}
    rating = rating_m.group(1).strip().upper()
    name_m = _RE_NAME.search(synthesis_md)
    if name_m:
        ticker = name_m.group(2)
        base = name_m.group(1).rsplit("(", 1)[0].strip().rstrip(",").strip()
        company = f"{base} — {ticker}"
    else:
        company, ticker = "", ""
    date_m = _RE_DATE.search(synthesis_md)
    spot_m = _RE_SPOT.search(synthesis_md)
    return {
        "company": company,
        "ticker": ticker,
        "rating": rating,
        "rating_class": _RATING_CLASS.get(rating, ""),
        "price_target": pt_m.group(1).strip(),
        "date": date_m.group(1) if date_m else "",
        "spot": spot_m.group(1) if spot_m else "",
    }


def encode_image_as_data_uri(path: Path) -> str:
    """Read a PNG (or any image) and return its data: URI. Empty string if missing."""
    if not path.exists() or not path.is_file():
        return ""
    suffix = path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(
        suffix, "application/octet-stream"
    )
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def render_section(section_path: Path) -> str:
    """Render a section.md to HTML. Returns a placeholder if the file is missing."""
    if not section_path.exists():
        return '<p class="placeholder">Section not produced — see logs.</p>'
    md_text = section_path.read_text()
    return markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])


def _inline_images(html: str, section_dir: Path) -> str:
    """Replace <img src="rel.png"> with data: URIs sourced from section_dir."""
    def replace(match: re.Match) -> str:
        src = match.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)
        uri = encode_image_as_data_uri(section_dir / src)
        if not uri:
            return match.group(0)
        return match.group(0).replace(f'src="{src}"', f'src="{uri}"')

    return re.sub(r'<img\s+[^>]*src="([^"]+)"[^>]*>', replace, html)


def write_report_html(ticker_dir: Path, ticker: str) -> Path:
    """Assemble <ticker_dir>/report.html and return its path."""
    ticker_dir = Path(ticker_dir)
    parts: list = []
    parts.append(f"<!DOCTYPE html>\n<html lang='en'>\n<head>")
    parts.append(f"<meta charset='utf-8'>")
    parts.append(f"<title>{ticker} — Equity Research Report</title>")
    parts.append(f"<style>{CSS}</style>")
    parts.append("</head>\n<body>")
    parts.append(f"<h1>{ticker} — Equity Research Report</h1>")

    # Companion links (only those present)
    companion_present = [(rel, label) for rel, label in COMPANION_LINKS if (ticker_dir / rel).exists()]
    if companion_present:
        parts.append('<div class="companion"><strong>Companion artifacts</strong><ul>')
        for rel, label in companion_present:
            parts.append(f'<li><a href="{rel}">{label}</a></li>')
        parts.append("</ul></div>")

    for pod, heading, filename in SECTION_ORDER:
        section_path = ticker_dir / pod / filename
        section_html = render_section(section_path)
        section_html = _inline_images(section_html, ticker_dir / pod)
        parts.append(f'<section class="section" id="{pod}">')
        parts.append(f"<h2>{heading}</h2>")
        parts.append(section_html)
        parts.append("</section>")

    parts.append("</body>\n</html>\n")
    out = ticker_dir / "report.html"
    out.write_text("\n".join(parts))
    return out
