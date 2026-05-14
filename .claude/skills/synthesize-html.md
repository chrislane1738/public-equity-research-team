---
name: synthesize-html
description: Use as the final step of every research workflow — invokes tools.html_writer.write_report_html to assemble <TICKER>/report.html as a single self-contained file (inline CSS, base64 charts, relative-path companion links, print-friendly). Loaded into Claude's own context (not a subagent).
---

# Synthesize HTML — single self-contained report

This skill loads in-context. Do not dispatch as a subagent.

## Workflow

1. Confirm the target directory exists at `~/Documents/equity-research/<TICKER>/`
   and contains at least `synthesis/_synthesis.md`.
2. Invoke the deterministic assembler via Bash:
   ```bash
   python -c "from tools.html_writer import write_report_html; \
              from pathlib import Path; \
              write_report_html(Path.home() / 'Documents/equity-research/<TICKER>', '<TICKER>')"
   ```
3. Confirm `<TICKER>/report.html` exists and report its size.
4. Return the absolute path to the report.

## Notes

- Deterministic — no LLM call. Judgment is just whether to invoke at all (e.g., halt if synthesis is missing).
- Companion .docx / .pptx / .xlsx are linked via relative paths. Missing companions silently skipped.
- All PNG charts in section.md files are inlined as base64. Missing chart files left as broken images (not fatal).

## Tools Used

- Bash (to invoke `tools.html_writer`)
- Read (to verify the target tree exists and has the expected structure)
