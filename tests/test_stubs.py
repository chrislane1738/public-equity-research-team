from pathlib import Path

from backend.agents._stubs import run_stub, STUB_AGENTS


async def test_stub_writes_section_file(tmp_path):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()

    result = await run_stub("industry", "NVDA", ticker_dir)

    path = ticker_dir / "industry" / "section.md"
    assert path.exists()
    assert "Industry" in path.read_text()
    assert "NVDA" in path.read_text()
    assert result.cost_usd == 0.0


async def test_all_six_stubs_run_independently(tmp_path):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()

    for name in STUB_AGENTS:
        await run_stub(name, "NVDA", ticker_dir)
        assert (ticker_dir / name / "section.md").exists()
