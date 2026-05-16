"""Assemble a single self-contained HTML report for a ticker.

Deterministic templating — no LLM call. Inputs: per-pod section.md files + PNG
charts on disk. Output: <TICKER>/report.html with inline CSS, base64-embedded
images, and relative-path links to companion .docx/.pptx/.xlsx artifacts.

Self-contained: open in any browser, including offline. Print-friendly via
@media print.
"""
import base64
import re
from html import escape as _escape
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
:root {
  --navy:#16243f; --navy-soft:#1f3050; --fg:#2b2b2b; --muted:#6b7280;
  --rule:#d8d8d8; --gold:#b8893a; --paper:#fff; --page:#f3f1ec;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: Georgia, "Times New Roman", serif; color: var(--fg);
       background: var(--page); line-height: 1.6; font-size: 16px; }

#rail { position: fixed; top: 0; left: 0; bottom: 0; width: 150px;
        background: var(--navy); color: #c7d0e0; overflow-y: auto;
        padding: 18px 0; font-size: 12px;
        font-family: -apple-system, "Segoe UI", system-ui, sans-serif; }
#rail .rail-h { font-size: 9px; letter-spacing: .16em; text-transform: uppercase;
                color: #8c99b3; padding: 0 16px 10px; }
.nav-sec { border-left: 3px solid transparent; }
.nav-sec.active { border-left-color: var(--gold); background: var(--navy-soft); }
.nav-row { display: flex; align-items: center; }
.nav-row a { flex: 1; color: #c7d0e0; text-decoration: none;
             padding: 7px 6px 7px 13px; line-height: 1.3; }
.nav-sec.active > .nav-row a { color: #fff; font-weight: 600; }
.chev { width: 26px; text-align: center; cursor: pointer; color: #7c89a3;
        user-select: none; font-size: 10px; padding: 7px 0;
        transition: transform .15s; }
.chev:hover { color: #fff; }
.chev.open { transform: rotate(90deg); }
.subnav { display: none; padding: 2px 0 6px; background: #101b30; }
.subnav.open { display: block; }
.subnav a { display: block; color: #9aa6bf; text-decoration: none;
            font-size: 11px; padding: 4px 12px 4px 26px; }
.subnav a:hover { color: #fff; }

#page { margin-left: 150px; }
.wrap { max-width: 820px; margin: 0 auto; padding: 0 32px 80px;
        background: var(--paper); min-height: 100vh; }

.masthead { background: var(--navy); color: #fff; margin: 0 -32px;
            padding: 26px 36px; }
.masthead .top { display: flex; align-items: flex-start;
                 justify-content: space-between; gap: 24px; }
.masthead .name { font-size: 27px; font-weight: 700; }
.masthead .meta { font-size: 12px; color: #aab6cd; margin-top: 5px;
                  font-family: -apple-system, system-ui, sans-serif; }
.callbox { text-align: right; flex-shrink: 0; }
.callbox .rating { font-size: 15px; font-weight: 700; letter-spacing: .14em;
                   color: #fff;
                   font-family: -apple-system, system-ui, sans-serif; }
.callbox .rating.sell { color: #f0867a; }
.callbox .rating.hold { color: #e3b762; }
.callbox .rating.buy { color: #7fce9f; }
.callbox .pt { font-size: 13px; color: #d6deec; margin-top: 3px;
               font-family: -apple-system, system-ui, sans-serif; }
.callbox .pt b { color: #fff; font-size: 16px; }

.companion { background: #faf8f3; border-left: 3px solid var(--navy);
             margin: 22px 0 0; padding: 12px 18px; font-size: 13px;
             font-family: -apple-system, system-ui, sans-serif; }
.companion strong { font-size: 11px; letter-spacing: .08em;
                    text-transform: uppercase; color: var(--muted); }
.companion a { color: var(--navy); }

h1.sec { font-size: 23px; color: var(--navy); border-bottom: 2px solid var(--navy);
         padding-bottom: 6px; margin: 52px 0 6px; }
h1 { font-size: 23px; color: var(--navy); }
h2 { font-size: 17px; color: var(--navy); margin: 30px 0 8px;
     border-bottom: 1px solid var(--rule); padding-bottom: 3px; }
h3 { font-size: 15px; color: var(--navy); margin: 22px 0 6px; }
p { margin: 12px 0; }
a { color: var(--navy); }
code { background: #f3f1ec; padding: .1em .3em; border-radius: 3px; font-size: .92em; }
.section { scroll-margin-top: 16px; }
.placeholder { color: var(--muted); font-style: italic; }
.muted { color: var(--muted); font-size: .92em; }

table { width: 100%; border-collapse: collapse; margin: 18px 0; font-size: 14px; }
th { text-align: left; border-bottom: 2px solid var(--navy); padding: 7px 10px;
     font-variant: small-caps; letter-spacing: .04em; font-size: 13px; }
td { border-bottom: 1px solid var(--rule); padding: 7px 10px;
     vertical-align: top; font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: 2px solid var(--navy); }

figure { margin: 22px 0; }
figure img { display: block; max-width: 100%; height: auto;
             border: 1px solid var(--rule); padding: 8px; background: #fcfbf8; }
figcaption { font-size: 12px; color: var(--muted); font-style: italic;
             margin-top: 6px; text-align: center; }
img { max-width: 100%; height: auto; }

@media print {
  #rail { display: none; }
  #page { margin-left: 0; }
  body { background: #fff; }
  .companion { display: none; }
  h1.sec { page-break-after: avoid; }
}
@media (max-width: 1080px) {
  #rail { display: none; }
  #page { margin-left: 0; }
}
"""


RAIL_JS = """
document.querySelectorAll('.chev').forEach(function(c){
  c.addEventListener('click', function(){
    c.classList.toggle('open');
    c.closest('.nav-sec').querySelector('.subnav').classList.toggle('open');
  });
});
var sectionObserver = new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(e.isIntersecting){
      document.querySelectorAll('.nav-sec').forEach(function(n){
        n.classList.remove('active');
      });
      var m = document.querySelector('.nav-sec[data-sec="'+e.target.id+'"]');
      if(m) m.classList.add('active');
    }
  });
}, { rootMargin: '-10% 0px -80% 0px' });
document.querySelectorAll('section.section').forEach(function(s){ sectionObserver.observe(s); });
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
        rows.append(f'<a href="#{sec_id}">{_escape(sec_label)}</a>')
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


def _escape_raw_html_in_markdown(md_text: str) -> str:
    """Escape raw HTML tags embedded in a markdown source string.

    Markdown passes raw HTML through verbatim by default. LLM-generated
    content may contain injected tags (e.g. <script>, <img onerror=…>).
    This pre-process step converts those tag characters to HTML entities so
    they render as visible text rather than executable markup.  Normal
    markdown constructs (**, ##, tables, fenced code) contain no < / > and
    are unaffected.
    """
    return re.sub(
        r"<(/?[a-zA-Z][^>]*)>",
        lambda m: f"&lt;{m.group(1)}&gt;",
        md_text,
    )


def render_section(section_path: Path) -> str:
    """Render a section.md to HTML. Returns a placeholder if the file is missing."""
    if not section_path.exists():
        return '<p class="placeholder">Section not produced — see logs.</p>'
    md_text = _escape_raw_html_in_markdown(section_path.read_text())
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

    # --- masthead from the synthesis ---
    synth_path = ticker_dir / "synthesis" / "_synthesis.md"
    synth_md = synth_path.read_text() if synth_path.exists() else ""
    mast = _extract_masthead(synth_md)

    # --- render each section, post-process, collect the nav tree ---
    nav: list = []
    section_blocks: list = []
    for pod, heading, filename in SECTION_ORDER:
        section_path = ticker_dir / pod / filename
        html = render_section(section_path)
        html = _strip_first_h1(html)
        html = _inline_images(html, ticker_dir / pod)
        html = _wrap_figures(html)
        html, subs = _prefix_heading_ids(html, pod)
        nav.append((pod, heading, subs))
        section_blocks.append(
            f'<section class="section" id="{pod}">'
            f'<h1 class="sec">{_escape(heading)}</h1>{html}</section>'
        )

    # --- assemble ---
    parts: list = []
    parts.append("<!DOCTYPE html>\n<html lang='en'>\n<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"<title>{_escape(ticker)} — Equity Research Report</title>")
    parts.append(f"<style>{CSS}</style>")
    parts.append("</head>\n<body>")

    parts.append(_build_rail(nav))
    parts.append("<div id='page'><div class='wrap'>")

    # masthead (auto-extracted, or plain-title fallback)
    if mast:
        meta_bits = ["Equity Research", "Deep-Dive"]
        if mast["date"]:
            meta_bits.append(mast["date"])
        if mast["spot"]:
            meta_bits.append(f'Reference price ${mast["spot"]}')
        parts.append('<header class="masthead"><div class="top"><div>')
        parts.append(f'<div class="name">{_escape(mast["company"] or ticker)}</div>')
        parts.append(f'<div class="meta">{" · ".join(meta_bits)}</div>')
        parts.append('</div><div class="callbox">')
        parts.append(
            f'<div class="rating {mast["rating_class"]}">{_escape(mast["rating"])}</div>'
        )
        parts.append(
            f'<div class="pt">Price Target <b>{_escape(mast["price_target"])}</b></div>'
        )
        parts.append('</div></div></header>')
    else:
        parts.append(
            '<header class="masthead"><div class="top"><div>'
            f'<div class="name">{_escape(ticker)} — Equity Research Report</div>'
            '</div></div></header>'
        )

    # companion links (only those present)
    companion_present = [
        (rel, label) for rel, label in COMPANION_LINKS if (ticker_dir / rel).exists()
    ]
    if companion_present:
        parts.append('<div class="companion"><strong>Companion artifacts</strong> ')
        parts.append(
            " · ".join(
                f'<a href="{rel}">{label}</a>' for rel, label in companion_present
            )
        )
        parts.append("</div>")

    parts.extend(section_blocks)

    parts.append("</div></div>")  # .wrap, #page
    parts.append(f"<script>{RAIL_JS}</script>")
    parts.append("</body>\n</html>\n")

    out = ticker_dir / "report.html"
    out.write_text("\n".join(parts))
    return out
