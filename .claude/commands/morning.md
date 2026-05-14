---
description: Quick morning note on a ticker — fundamentals delta + brief synthesis
argument-hint: <TICKER>
---

Run a quick morning-note on `$1`:

1. Dispatch `fundamentals` skill (mode=morning — pull latest quote + 5-day
   price change + any 8-K from the last 24h).
2. Invoke `md-synthesis` skill in-context to write a 200-300 word morning note.
3. Save to `~/Documents/equity-research/$1/morning-note.md` and print to chat.
