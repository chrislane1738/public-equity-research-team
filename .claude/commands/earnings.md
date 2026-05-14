---
description: Run an earnings-update workflow on a ticker (delta vs. prior quarter)
argument-hint: <TICKER>
---

Run an earnings-update on `$1`:

1. Dispatch `accountant` skill as a subagent in **earnings-update mode** — this
   is a lightweight variant: skip the full reconciliation and red-flag taxonomy,
   just download the latest 8-K (Ex-99.1 earnings release) and the earnings
   presentation (Ex-99.2 if filed, else IR site fallback). Write
   `accountant/section.md` with a brief summary of the earnings release. Wait
   for completion.
2. Dispatch `fundamentals` skill as a subagent. Pass `mode=earnings-update` so
   it focuses on the latest reported quarter delta vs. prior. Reads accountant's
   downloaded earnings deck for KPI grounding.
3. In parallel (two Agent calls in one message): dispatch `dcf` (with the
   default 12x EV/EBITDA fallback if comps is absent) and `risk-upside`.
4. Dispatch `memo-builder` with `variant=earnings` so it wraps
   `equity-research:earnings-analysis`.
5. Invoke `synthesize-html` skill to produce `report.html`.

Output: `~/Documents/equity-research/$1/reports/memo.docx` + `report.html`.
