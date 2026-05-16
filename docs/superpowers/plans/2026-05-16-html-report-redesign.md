# HTML Research Report Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the deep-dive `report.html` deliverable in an institutional sell-side aesthetic with an auto-extracted masthead and a fixed left quicklinks rail.

**Architecture:** All changes are confined to `tools/html_writer.py` — five new pure-function helpers (each unit-tested in isolation), a `toc`-extension change to `render_section`, and a rewrite of the `CSS` constant and the `write_report_html` template. A short documentation note is added to `.claude/skills/synthesize-html.md`. The assembler stays deterministic (no LLM call) and the output stays a single self-contained file.

**Tech Stack:** Python 3.14, the `markdown` library (`tables`, `fenced_code`, `toc` extensions), `pytest`. Output is HTML/CSS with one small inline `<script>`.

---

## Reference: the design spec

`docs/superpowers/specs/2026-05-16-html-report-redesign-design.md` — read it for the rationale. This plan implements it task-by-task.

## File Structure

- `tools/html_writer.py` — **modified.** Adds 5 helpers (`_extract_masthead`, `_strip_first_h1`, `_prefix_heading_ids`, `_wrap_figures`, `_build_rail`), a `RAIL_JS` constant, a rewritten `CSS` constant, a `toc` extension on `render_section`, and a rewritten `write_report_html`. One file, one responsibility (report assembly) — it stays cohesive at ~250 lines.
- `tests/test_html_writer.py` — **modified.** One existing assertion updated for the `toc` change; new tests for every helper and for masthead/rail behavior in the assembled output.
- `.claude/skills/synthesize-html.md` — **modified.** Adds a `## Report design` section recording the look as a preference.

## Note on one spec simplification

The spec's section 4 says numeric table cells are "right-aligned with tabular-nums". Markdown tables in the pod `section.md` files do not carry column-type metadata, so true per-column right-alignment is not reliably achievable. This plan applies `font-variant-numeric: tabular-nums` to all `<td>` (consistent digit widths — the main readability win) and leaves horizontal alignment at the default. Auto-detecting numeric columns is deliberately out of scope (YAGNI).

---

### Task 1: `_extract_masthead` helper

**Files:**
- Modify: `tools/html_writer.py`
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_html_writer.py` — update the import line and add the tests:

```python
from tools.html_writer import (
    encode_image_as_data_uri,
    render_section,
    write_report_html,
    _extract_masthead,
)


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k extract_masthead -v`
Expected: FAIL — `ImportError: cannot import name '_extract_masthead'`.

- [ ] **Step 3: Implement `_extract_masthead`**

In `tools/html_writer.py`, after the `CSS` constant (constants stay grouped at the top), add:

```python
_RE_NAME = re.compile(r"\*\*([^*]+?\(([A-Z][A-Z.]{0,5})\))\*\*")
_RE_RATING = re.compile(r"##\s*Rating:\s*\*\*([A-Za-z]+)\*\*")
_RE_PT = re.compile(r"##\s*Price Target:\s*\*\*([^*]+?)\*\*")
_RE_DATE = re.compile(r"Synthesis date:\s*(\d{4}-\d{2}-\d{2})")
_RE_SPOT = re.compile(r"Reference price:\s*\*{0,2}\$?([\d,.]+)")

_RATING_CLASS = {"BUY": "buy", "HOLD": "hold", "SELL": "sell"}


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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k extract_masthead -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): add _extract_masthead synthesis parser"
```

---

### Task 2: `_strip_first_h1` helper

**Files:**
- Modify: `tools/html_writer.py`
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

Add `_strip_first_h1` to the import line in `tests/test_html_writer.py`, then add:

```python
def test_strip_first_h1_removes_only_first():
    html = "<h1 id='a'>Title</h1><p>x</p><h1>Second</h1>"
    out = _strip_first_h1(html)
    assert "Title" not in out
    assert "<p>x</p>" in out
    assert "Second" in out


def test_strip_first_h1_noop_without_h1():
    html = "<h2>Sub</h2><p>body</p>"
    assert _strip_first_h1(html) == html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k strip_first_h1 -v`
Expected: FAIL — `ImportError: cannot import name '_strip_first_h1'`.

- [ ] **Step 3: Implement `_strip_first_h1`**

In `tools/html_writer.py`, add near the other helpers:

```python
_RE_FIRST_H1 = re.compile(r"<h1[^>]*>.*?</h1>", re.DOTALL)


def _strip_first_h1(html: str) -> str:
    """Remove the first <h1>…</h1> — each pod section.md repeats its own title
    as an <h1>, which is redundant with the section heading the writer injects.
    """
    return _RE_FIRST_H1.sub("", html, count=1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k strip_first_h1 -v`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): add _strip_first_h1 helper"
```

---

### Task 3: `_prefix_heading_ids` helper

**Files:**
- Modify: `tools/html_writer.py`
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

Add `_prefix_heading_ids` to the import line, then add:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k prefix_heading_ids -v`
Expected: FAIL — `ImportError: cannot import name '_prefix_heading_ids'`.

- [ ] **Step 3: Implement `_prefix_heading_ids`**

In `tools/html_writer.py`, add:

```python
_RE_HEADING_ID = re.compile(
    r'<h([1-6])([^>]*)\sid="([^"]+)"([^>]*)>(.*?)</h\1>', re.DOTALL
)
_RE_TAGS = re.compile(r"<[^>]+>")


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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k prefix_heading_ids -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): add _prefix_heading_ids for unique anchors"
```

---

### Task 4: `_wrap_figures` helper

**Files:**
- Modify: `tools/html_writer.py`
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

Add `_wrap_figures` to the import line, then add:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k wrap_figures -v`
Expected: FAIL — `ImportError: cannot import name '_wrap_figures'`.

- [ ] **Step 3: Implement `_wrap_figures`**

In `tools/html_writer.py`, add:

```python
_RE_IMG_PARA = re.compile(r"<p>\s*(<img\s+[^>]*?>)\s*</p>", re.DOTALL)
_RE_IMG_ALT = re.compile(r'alt="([^"]*)"')


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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k wrap_figures -v`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): add _wrap_figures for framed chart captions"
```

---

### Task 5: `_build_rail` helper

**Files:**
- Modify: `tools/html_writer.py`
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

Add `_build_rail` to the import line, then add:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k build_rail -v`
Expected: FAIL — `ImportError: cannot import name '_build_rail'`.

- [ ] **Step 3: Implement `_build_rail`**

In `tools/html_writer.py`, add:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k build_rail -v`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): add _build_rail quicklinks generator"
```

---

### Task 6: Add `toc` extension to `render_section`

**Files:**
- Modify: `tools/html_writer.py` (`render_section`)
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Update the existing test and add a new one**

In `tests/test_html_writer.py`, the existing `test_render_section_converts_markdown_to_html` asserts `"<h1>" in html`. With the `toc` extension headings render as `<h1 id="...">`, so that exact substring no longer appears. Change the assertion and add a heading-id test:

```python
def test_render_section_converts_markdown_to_html(tmp_path):
    section_md = tmp_path / "section.md"
    section_md.write_text("# Heading\n\n- bullet one\n- bullet two\n")
    html = render_section(section_md)
    assert "<h1" in html
    assert "<li>bullet one</li>" in html


def test_render_section_adds_heading_ids(tmp_path):
    section_md = tmp_path / "section.md"
    section_md.write_text("## Balance Sheet\n\nbody\n")
    html = render_section(section_md)
    assert 'id="balance-sheet"' in html
```

- [ ] **Step 2: Run the tests to verify the new one fails**

Run: `python3 -m pytest tests/test_html_writer.py -k render_section -v`
Expected: `test_render_section_adds_heading_ids` FAILS (no `id=` attribute yet); the other render_section tests PASS.

- [ ] **Step 3: Add the `toc` extension**

In `tools/html_writer.py`, change the `markdown.markdown` call in `render_section`:

```python
def render_section(section_path: Path) -> str:
    """Render a section.md to HTML. Returns a placeholder if the file is missing."""
    if not section_path.exists():
        return '<p class="placeholder">Section not produced — see logs.</p>'
    md_text = section_path.read_text()
    return markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_html_writer.py -k render_section -v`
Expected: PASS — all render_section tests.

- [ ] **Step 5: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): emit heading ids via markdown toc extension"
```

---

### Task 7: Rewrite `CSS`, add `RAIL_JS`, rewrite `write_report_html`

**Files:**
- Modify: `tools/html_writer.py` (`CSS` constant, new `RAIL_JS` constant, `write_report_html`)
- Test: `tests/test_html_writer.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_html_writer.py`, add (the existing `test_write_report_html_assembles_self_contained_file` stays unchanged and must keep passing):

```python
def _build_min_tree(tmp_path, ticker, synthesis_text):
    """Create a minimal ticker tree with all 8 sections."""
    ticker_dir = tmp_path / ticker
    for pod in ("fundamentals", "industry", "dcf", "comps", "macro",
                "risk", "technicals", "synthesis"):
        (ticker_dir / pod).mkdir(parents=True)
    for pod in ("fundamentals", "industry", "dcf", "comps", "macro",
                "risk", "technicals"):
        (ticker_dir / pod / "section.md").write_text(
            f"# {pod} title\n\n## A Subsection\n\nContent for {pod}.\n"
        )
    (ticker_dir / "synthesis" / "_synthesis.md").write_text(synthesis_text)
    return ticker_dir


def test_write_report_html_renders_masthead_from_synthesis(tmp_path):
    ticker_dir = _build_min_tree(tmp_path, "MU", REAL_SYNTH)
    html = write_report_html(ticker_dir, "MU").read_text()
    assert 'class="masthead"' in html
    assert 'class="rating sell"' in html
    assert ">SELL<" in html
    assert "$400" in html
    assert '<nav id="rail">' in html
    assert 'data-sec="fundamentals"' in html


def test_write_report_html_rail_has_prefixed_subsection_links(tmp_path):
    ticker_dir = _build_min_tree(tmp_path, "MU", REAL_SYNTH)
    html = write_report_html(ticker_dir, "MU").read_text()
    # the "A Subsection" h2 in each pod gets a pod-prefixed anchor in the rail
    assert 'href="#fundamentals__a-subsection"' in html
    assert 'href="#industry__a-subsection"' in html


def test_write_report_html_falls_back_to_plain_title(tmp_path):
    ticker_dir = _build_min_tree(tmp_path, "XYZ", "# Synthesis\n\nNo rating.\n")
    html = write_report_html(ticker_dir, "XYZ").read_text()
    assert "XYZ — Equity Research Report" in html
    assert 'class="callbox"' not in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_html_writer.py -k "masthead or rail or plain_title" -v`
Expected: FAIL — masthead/rail markup not yet produced.

- [ ] **Step 3: Replace the `CSS` constant**

In `tools/html_writer.py`, replace the entire existing `CSS = """..."""` block with:

```python
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
```

- [ ] **Step 4: Add the `RAIL_JS` constant**

In `tools/html_writer.py`, immediately after the `CSS` constant, add:

```python
RAIL_JS = """
document.querySelectorAll('.chev').forEach(function(c){
  c.addEventListener('click', function(){
    c.classList.toggle('open');
    c.closest('.nav-sec').querySelector('.subnav').classList.toggle('open');
  });
});
var io = new IntersectionObserver(function(entries){
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
document.querySelectorAll('section.section').forEach(function(s){ io.observe(s); });
"""
```

- [ ] **Step 5: Rewrite `write_report_html`**

In `tools/html_writer.py`, replace the entire `write_report_html` function with:

```python
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
            f'<h1 class="sec">{heading}</h1>{html}</section>'
        )

    # --- assemble ---
    parts: list = []
    parts.append("<!DOCTYPE html>\n<html lang='en'>\n<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"<title>{ticker} — Equity Research Report</title>")
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
        parts.append(f'<div class="name">{mast["company"] or ticker}</div>')
        parts.append(f'<div class="meta">{" · ".join(meta_bits)}</div>')
        parts.append('</div><div class="callbox">')
        parts.append(
            f'<div class="rating {mast["rating_class"]}">{mast["rating"]}</div>'
        )
        parts.append(
            f'<div class="pt">Price Target <b>{mast["price_target"]}</b></div>'
        )
        parts.append('</div></div></header>')
    else:
        parts.append(
            '<header class="masthead"><div class="top"><div>'
            f'<div class="name">{ticker} — Equity Research Report</div>'
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
```

- [ ] **Step 6: Run the full test file**

Run: `python3 -m pytest tests/test_html_writer.py -v`
Expected: PASS — all tests, including the unchanged `test_write_report_html_assembles_self_contained_file` (its no-`## Rating:` synthesis fixture exercises the plain-title fallback).

- [ ] **Step 7: Commit**

```bash
git add tools/html_writer.py tests/test_html_writer.py
git commit -m "feat(html_writer): institutional restyle, masthead, quicklinks rail"
```

---

### Task 8: Document the design in the `synthesize-html` skill

**Files:**
- Modify: `.claude/skills/synthesize-html.md`

- [ ] **Step 1: Add a `## Report design` section**

In `.claude/skills/synthesize-html.md`, after the `## Notes` section and before `## Tools Used`, insert:

```markdown
## Report design

`tools.html_writer` renders the report in a fixed **institutional sell-side**
style — the deterministic assembler owns the look; there is no per-run styling
choice. Key elements:

- **Masthead** — a navy band auto-populated from `_synthesis.md`: company name +
  ticker, an `Equity Research · Deep-Dive · <date> · Reference price` metadata
  line, and the rating (color-keyed red/amber/green for Sell/Hold/Buy) with the
  price target. Falls back to a plain title if the synthesis lacks a parseable
  rating or price target.
- **Left quicklinks rail** — a fixed navy rail listing the eight sections; each
  has a chevron that expands its subsection headings. Hidden on print and below
  a 1080px viewport.
- **Body** — Georgia/serif headlines, navy accents, framed charts with captions.

Changing the look means editing `tools/html_writer.py` (`CSS`, `RAIL_JS`, and
`write_report_html`), not this skill's workflow.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/synthesize-html.md
git commit -m "docs(synthesize-html): record institutional report design"
```

---

### Task 9: Regenerate the MU report and verify

**Files:**
- No code changes — regeneration and verification only.

- [ ] **Step 1: Regenerate `report.html` for MU**

Run:
```bash
python3 -c "from tools.html_writer import write_report_html; from pathlib import Path; write_report_html(Path.home() / 'Documents/equity-research/MU', 'MU')"
```
Expected: no error; the command prints nothing and exits 0.

- [ ] **Step 2: Verify the structural markers**

Run:
```bash
cd ~/Documents/equity-research/MU && \
  grep -c '<nav id="rail">' report.html && \
  grep -c 'class="rating sell"' report.html && \
  grep -c 'class="masthead"' report.html && \
  grep -oc 'data:image/png;base64' report.html && \
  grep -c 'Price Target' report.html
```
Expected: `1`, `1`, `1`, `6` (six inlined charts), and `≥1`.

- [ ] **Step 3: Verify the full test suite still passes**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — all tests (no regressions in the wider suite).

- [ ] **Step 4: Visual check**

Open `~/Documents/equity-research/MU/report.html` in a browser. Confirm:
the navy masthead shows `SELL` in red and `Price Target $400`; the left rail
chevrons expand subsections; the active section highlights on scroll; the six
charts render framed with captions; browser print-preview drops the rail and
reflows the body full-width.

- [ ] **Step 5: No commit**

This task regenerates a deliverable under `~/Documents/equity-research/` (outside
the repo) — there is nothing to commit.

---

## Self-Review

**Spec coverage:**
- Masthead auto-extraction → Task 1 + Task 7. ✓
- Left quicklinks rail with collapsible subsections → Task 3, 5, 6, 7. ✓
- Institutional-A visual system → Task 7 (`CSS`). ✓
- Framed charts with captions → Task 4 + Task 7. ✓
- Heading-id uniqueness across sections → Task 3. ✓
- Redundant pod-title `<h1>` cleanup → Task 2 + Task 7. ✓
- Print + responsive behavior → Task 7 (`CSS` media queries). ✓
- Inline JS for chevron + scrollspy → Task 7 (`RAIL_JS`). ✓
- Tests (masthead happy/fallback, rail generation, cross-section uniqueness,
  rating color-keying) → Tasks 1, 3, 6, 7. ✓
- Persist preference to the skill → Task 8. ✓
- One spec simplification (numeric-column right-alignment) is documented above
  and in Task 7's `CSS`. ✓

**Placeholder scan:** none — every step contains complete code or an exact command.

**Type consistency:** `_extract_masthead` returns a dict consumed in Task 7 by
the exact keys it sets (`company`, `ticker`, `rating`, `rating_class`,
`price_target`, `date`, `spot`). `_prefix_heading_ids` returns
`(html, list[(id, label)])`, consumed as `subs` and passed into `_build_rail`'s
`nav` tuples `(section_id, section_label, subs)` — consistent across Tasks 3, 5, 7.
