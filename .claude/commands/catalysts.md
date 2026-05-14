---
description: Quick lookup of dated catalysts for a ticker
argument-hint: <TICKER>
---

Look up upcoming catalysts for `$1`:

1. Pull the FMP earnings calendar for the next 90 days.
2. Pull recent 8-K filings via `tools.edgar` for any 1-day-event-style filings.
3. WebSearch for `"<TICKER> investor day"`, `"<TICKER> product launch"`,
   regulatory deadlines.
4. Return a chronological bullet list to chat with date + event + impact note.

No on-disk artifact unless the user asks to save it.
