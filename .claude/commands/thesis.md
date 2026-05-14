---
description: Targeted thesis check — dispatch 2-3 relevant skills and write a focused memo
argument-hint: <TICKER> "<question>"
---

Run a thesis-check on `$1` for the question: `$2`.

1. Decide which 2-3 skills are most relevant given the question. For example,
   "is the moat narrowing" → `industry-moat` + `risk-upside`. "Is the multiple
   stretched" → `comps` + `dcf`.
2. Dispatch the chosen skills as parallel subagents.
3. Invoke `md-synthesis` to write a focused memo (300-500 words) that directly
   answers the question, citing the section.md files.
4. Save to `~/Documents/equity-research/$1/thesis-checks/<slug>.md` (slugify
   the question for the filename).
