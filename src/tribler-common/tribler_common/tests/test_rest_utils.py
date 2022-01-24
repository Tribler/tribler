from unittest.mock import patch

import pytest

from tribler_common.rest_utils import path_to_uri, uri_to_path

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


# posix
@pytest.mark.parametrize('path,uri', NIX_PATHS)
@patch('os.name', 'posix')
def test_path_to_uri(path, uri):
    assert path_to_uri(path) == uri


@pytest.mark.parametrize('path,uri', NIX_PATHS)
@patch('os.name', 'posix')
def test_uri_to_path(path, uri):
    assert uri_to_path(uri) == path


# win
@pytest.mark.parametrize('path,uri', WIN_PATHS)
@patch('os.name', 'nt')
def test_path_to_uri_win(path, uri):
    assert path_to_uri(path) == uri


@pytest.mark.parametrize('path,uri', WIN_PATHS)
@patch('os.name', 'nt')
def test_uri_to_path_win(path, uri):
    assert uri_to_path(uri) == path
