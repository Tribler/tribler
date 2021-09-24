from pathlib import Path

from tribler_common.utilities import uri_to_path


def test_uri_to_path():
    path = Path(__file__).parent / "bla%20foo.bar"
    uri = path.as_uri()
    assert uri_to_path(uri) == path
