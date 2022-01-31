from unittest.mock import patch

import pytest

from tribler_common.rest_utils import path_to_uri, scheme_from_uri, uri_is_valid_file, uri_to_path

NIX_PATHS = [
    ('/path/to/file', 'file:///path/to/file'),
    ('/path/to/file with space', 'file:///path/to/file%20with%20space'),
    ('/path/to/%20%21file', 'file:///path/to/%2520%2521file'),  # See: https://github.com/Tribler/tribler/issues/6700
]

WIN_PATHS = [
    ('C:\\path\\to\\file', 'file:///C:%5Cpath%5Cto%5Cfile'),
    ('C:\\path\\to\\file with space', 'file:///C:%5Cpath%5Cto%5Cfile%20with%20space'),
    ('C:\\path\\to\\%20%21file', 'file:///C:%5Cpath%5Cto%5C%2520%2521file'),
]

SCHEMES = [
    ('file:///path/to/file', 'file'),
    ('magnet:link', 'magnet'),
    ('http://en.wikipedia.org', 'http'),
]

# posix
@pytest.mark.parametrize('path, uri', NIX_PATHS)
@patch('os.name', 'posix')
def test_path_to_uri(path, uri):
    assert path_to_uri(path) == uri


@pytest.mark.parametrize('path, uri', NIX_PATHS)
@patch('os.name', 'posix')
def test_uri_to_path(path, uri):
    assert uri_to_path(uri) == path


# win
@pytest.mark.parametrize('path, uri', WIN_PATHS)
@patch('os.name', 'nt')
def test_path_to_uri_win(path, uri):
    assert path_to_uri(path) == uri


@pytest.mark.parametrize('path, uri', WIN_PATHS)
@patch('os.name', 'nt')
def test_uri_to_path_win(path, uri):
    assert uri_to_path(uri) == path


@pytest.mark.parametrize('path, scheme', SCHEMES)
def test_scheme_from_uri(path, scheme):
    assert scheme_from_uri(path) == scheme


def test_uri_is_valid_file(tmpdir):
    file_path = tmpdir / '1.txt'
    file_path.write('test')
    file_uri = path_to_uri(file_path)
    assert uri_is_valid_file(file_uri)
    assert not uri_is_valid_file(file_uri + '/*')
