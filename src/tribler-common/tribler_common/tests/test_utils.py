from pathlib import Path

from tribler_common.utilities import to_fts_query, uri_to_path


def test_uri_to_path():
    path = Path(__file__).parent / "bla%20foo.bar"
    uri = path.as_uri()
    assert uri_to_path(uri) == path


def test_to_fts_query():
    assert to_fts_query('') == ''
    assert to_fts_query('abc') == '"abc"*'
    assert to_fts_query('abc def') == '"abc" "def"*'
    assert to_fts_query('[abc, def]: xyz?!') == '"abc" "def" "xyz"*'
