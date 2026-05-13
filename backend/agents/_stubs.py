"""Stub research-pod agents for Plan A.

Each agent writes a placeholder section.md so the pipeline can run end-to-end
without the real agent logic. Plan B replaces every one of these with a real
agent in its own module.
"""
from pathlib import Path

from backend.agents.base import AgentResult


STUB_AGENTS = [
    "industry", "dcf", "comps", "macro", "risk", "technicals",
]


async def run_stub(name: str, ticker: str, ticker_dir: Path) -> AgentResult:
    """Write a placeholder section.md for one stub agent."""
    out_dir = ticker_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    body = (
        f"# {name.title()} — {ticker}\n\n"
        f"(Plan A stub. The real {name} agent ships in Plan B.)\n\n"
        f"- placeholder finding 1\n"
        f"- placeholder finding 2\n"
    )
    (out_dir / "section.md").write_text(body)
    return AgentResult(content=body, input_tokens=0, output_tokens=0, cost_usd=0.0)
