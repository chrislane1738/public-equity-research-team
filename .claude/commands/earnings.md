---
description: Run an earnings-update workflow on a ticker (delta vs. prior quarter)
argument-hint: <TICKER>
---

Run an earnings-update on `$1`:

1. Dispatch `fundamentals` skill as a subagent. Pass `mode=earnings-update` so
   it focuses on the latest reported quarter delta vs. prior.
2. In parallel (two Agent calls in one message): dispatch `dcf` (with the
   default 12x EV/EBITDA fallback if comps is absent) and `risk-upside`.
3. Dispatch `memo-builder` with `variant=earnings` so it wraps
   `equity-research:earnings-analysis`.
4. Invoke `synthesize-html` skill to produce `report.html`.

Output: `~/Documents/equity-research/$1/reports/memo.docx` + `report.html`.
