---
description: Run a stock screen — FMP screener for numeric, WebSearch for thematic
argument-hint: "<criteria>"
---

Run a screen against the criteria: `$ARGUMENTS`.

Invoke the `screen` skill in-context. The skill decides whether the criteria
are numeric (mcap/P-E/growth bands → FMP screener) or thematic ("AI
infrastructure" → WebSearch then enrichment). Returns 10-15 candidates with a
one-line thesis each.

Output: chat-only by default. If the user follows up with "make a sector
report", route to `/sector` with the top tickers.
