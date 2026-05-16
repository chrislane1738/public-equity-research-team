# HTML Research Report Redesign — Design

**Date:** 2026-05-16
**Status:** Approved — ready for implementation planning
**Topic:** Visual redesign of the deep-dive `report.html` deliverable

## Context

The deep-dive workflow produces `~/Documents/equity-research/<TICKER>/report.html` as
its canonical deliverable, assembled by `tools/html_writer.py` — a deterministic
templating module (no LLM call). The current report is functional but plain:
generic system-font styling, a one-line title, no in-document navigation. The
desk wants it to read like an institutional sell-side research note.

All styling and structure live in one file: `tools/html_writer.py` (the `CSS`
constant and the `write_report_html` template). The `synthesize-html` skill
(`.claude/skills/synthesize-html.md`) only invokes the writer; its workflow does
not change. The change is validated against the just-produced MU report.

## Goals

1. Restyle the report in an **institutional sell-side** aesthetic — serif
   headlines, navy accent, thin rules, tabular numerals.
2. Add an **auto-extracted masthead** — company name + ticker, rating
   (color-keyed), price target, as-of date, reference price — pulled from
   `_synthesis.md`.
3. Add a **fixed left quicklinks rail** — the eight report sections, each with a
   chevron that expands a dropdown of that section's subsections; the active
   section highlights on scroll.
4. Keep the report a **single self-contained file** that opens offline and
   prints cleanly.

## Non-Goals

- Chart restyling (`tools/charts.py`) — tracked as a separate follow-up task.
- Any change to research content, pod outputs, or `section.md` structure.
- A mobile/hamburger menu — this is a desktop and print document; below a
  breakpoint the rail simply hides.

## Design

### 1. Masthead (auto-extracted)

A new helper `_extract_masthead(synthesis_md: str) -> dict` parses
`_synthesis.md` with regexes against its regular format:

| Field | Source line in `_synthesis.md` | Regex target |
|---|---|---|
| Company + ticker | `**Micron Technology, Inc. (MU)** | ...` | first bold span containing `(TICKER)` |
| Rating | `## Rating: **SELL**` | `## Rating:\s*\*\*(\w+)\*\*` |
| Price target | `## Price Target: **$400**` | `## Price Target:\s*\*\*(.+?)\*\*` |
| Synthesis date | `Synthesis date: 2026-05-16` | `Synthesis date:\s*([\d-]+)` |
| Reference price | `Reference price: **$724.66**` | `Reference price:\s*\*?\*?\$?([\d.,]+)` |

The navy masthead renders: company name + ticker (serif, bold), a metadata line
(`Equity Research · Deep-Dive · <date> · Reference price $<spot>`), and a
right-aligned call box with the **rating** and **price target**.

The rating is color-keyed: `SELL` → red, `HOLD` → amber, `BUY` → green
(case-insensitive). Only the rating word carries color; the rest of the
masthead stays restrained navy/white.

**Fallback:** if rating or price target cannot be extracted, the masthead
degrades to a plain title (`<TICKER> — Equity Research Report`) with no call
box. The report still assembles. This keeps the writer robust to any future
synthesis that breaks format.

### 2. Left quicklinks rail

A fixed 150px navy rail (`<nav id="rail">`), independent of page scroll, that
does not push or overlap the body text. It contains the eight report sections
in canonical order (Executive Summary, Fundamentals, Industry & Moat, DCF
Valuation, Trading Comps, Macro & Catalysts, Risks & Upside, Technicals).

Each entry is a `.nav-sec` containing: a section link (`#<pod>`), a chevron
toggle, and a hidden `.subnav` of subsection links. Clicking the chevron
expands/collapses the dropdown. Subsections are the `<h2>` headings within that
section's rendered markdown.

The active section highlights (gold left-border + lighter background) as the
reader scrolls, via an `IntersectionObserver`.

A section with no subsections renders without a chevron.

### 3. Anchor IDs and heading levels

To support the rail, every heading needs a stable, document-unique `id`:

- Rendering switches on the markdown `toc` extension:
  `markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])`.
  The `toc` extension assigns slug `id`s to all headings.
- The `toc` extension only dedupes slugs **within a single render call**, and
  each `section.md` is rendered separately — so two sections could both emit
  `id="data-gaps"`. After rendering each section, the writer **prefixes every
  heading `id` with the pod name** (`id="industry__data-gaps"`) and builds the
  nav links to match. This guarantees global uniqueness.
- The writer injects the section title as `<h1 class="sec">` (was `<h2>`).
- Each pod `section.md` repeats its own title as a markdown `<h1>` immediately
  below the injected heading (e.g. "Fundamentals" then "Fundamentals — MU
  (Micron Technology, Inc.)"). The writer **strips the first `<h1>`** from each
  rendered section so every section shows one clean heading. Subsection `<h2>`s
  are kept and feed the rail.

### 4. Institutional-A visual system

Replaces the `CSS` constant:

- **Type:** Georgia/serif for headlines and body; system sans for the
  masthead metadata, rail, and chart captions.
- **Color:** navy `#16243f` accent, charcoal `#2b2b2b` body, gold `#b8893a`
  active-nav marker, paper-white content on a warm `#f3f1ec` page.
- **Sections:** `h1.sec` with a 2px navy underline; `h2` with a 1px grey rule.
- **Tables:** horizontal rules only (no vertical lines); small-caps headers
  with a 2px navy underline; numeric cells right-aligned with
  `font-variant-numeric: tabular-nums`; a 2px navy rule under the last row.
- **Charts:** each inlined `<img>` is wrapped in a `<figure>` with a thin
  framed border; the markdown image alt-text becomes an italic `<figcaption>`.
- **Companion box:** retained (existing `COMPANION_LINKS` logic unchanged),
  restyled to the navy/paper palette.

### 5. Print & responsive behavior

- `@media print`: hide `#rail`, reset `#page` margin to 0, hide the companion
  box (already hidden today), white background, avoid page-breaks after
  section headings.
- `@media (max-width: 1080px)`: hide `#rail`, reset `#page` margin — the body
  recenters. No hamburger menu.

### 6. Inline JavaScript

One small inline `<script>` (keeps the file self-contained and offline-capable):

- Chevron click → toggle the section's `.subnav` and the chevron's rotation.
- `IntersectionObserver` over `section.section` → set `.active` on the matching
  `.nav-sec`.

## Implementation Surface

All changes in `tools/html_writer.py`:

- **New:** `_extract_masthead(synthesis_md: str) -> dict` — regex extraction +
  fallback.
- **New:** `_prefix_heading_ids(html: str, pod: str) -> tuple[str, list]` —
  prefixes heading `id`s with the pod name; returns rewritten HTML and a list
  of `(id, text)` subsection entries for the nav.
- **New:** `_strip_first_h1(html: str) -> str` — removes the redundant pod-title
  `<h1>`.
- **New:** `_build_rail(nav_tree: list) -> str` — emits the `<nav id="rail">`
  markup.
- **Changed:** `render_section` — add the `toc` extension.
- **Changed:** `write_report_html` — compute masthead, render + post-process
  each section, build the rail, emit the new shell (`#rail`, `#page`/`.wrap`,
  `<header class="masthead">`, sections, `<script>`).
- **Changed:** `CSS` constant — the institutional-A stylesheet.

## Testing

`tests/test_html_writer.py`:

- **Existing tests must keep passing.** `test_write_report_html_assembles_self_contained_file`
  asserts `<style>`, `@media print`, the two companion `href`s, and body
  content — all still hold. Its synthesis fixture (`Rating: Buy. PT $200.`) is
  not in the real `## Rating:` format, so masthead extraction falls back to the
  plain title — the intended fallback behavior; the test still passes.
- **New:** `_extract_masthead` happy path — a real-format synthesis string
  yields rating `SELL`, PT `$400`, date, reference price, company/ticker.
- **New:** `_extract_masthead` fallback — a malformed synthesis yields an empty
  result and the report renders with a plain title and no call box.
- **New:** rail generation — a section with `<h2>` subsections produces a
  `.subnav` with matching links; a section without produces no chevron.
- **New:** cross-section anchor uniqueness — two sections that both contain a
  `## Data Gaps` heading produce two distinct, pod-prefixed `id`s.
- **New:** rating color-keying — `SELL`/`HOLD`/`BUY` map to the three classes.

## Persisting the Preference

The user asked that the chosen look be saved to the synthesizer skill. Add a
short **`## Report design`** section to `.claude/skills/synthesize-html.md`
documenting: the institutional-A aesthetic, the auto-extracted masthead, and
the left quicklinks rail — so the design intent is recorded alongside the
skill. The skill's workflow steps do not change.

## Risks & Edge Cases

- **Synthesis format drift** — handled by the masthead fallback; the report
  always assembles.
- **Duplicate heading slugs across sections** — handled by pod-prefixing all
  heading `id`s.
- **A section file missing** — `render_section` already returns a placeholder;
  the rail entry for that section simply has no subsections (no chevron).
- **Charts not inlined** — out of scope here; the MU report's `section.md`
  files were already edited to reference charts inline, and `_inline_images`
  is unchanged.
