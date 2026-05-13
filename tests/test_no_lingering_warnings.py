import warnings

from backend.tools.edgar_client import EdgarClient


def test_extract_sections_does_not_emit_lxml_deprecation():
    html = "<html><body><h2>Item 1.</h2>x<h2>Item 1A.</h2>y</body></html>"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        EdgarClient._extract_sections(html)
    msgs = [str(w.message) for w in caught]
    assert not any("strip_cdata" in m for m in msgs), \
        f"unexpected lxml deprecation warning: {msgs!r}"


def test_memo_builder_module_does_not_import_re():
    import backend.agents.memo_builder as mb
    src = open(mb.__file__).read()
    assert "import re" not in src.split("\n")[:5], "memo_builder should not import re"
