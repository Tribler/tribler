from pathlib import PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest

from tribler.core.utilities.rest_utils import FILE_SCHEME, HTTP_SCHEME, MAGNET_SCHEME, path_to_url, scheme_from_url, \
    url_is_valid_file, \
    url_to_path

# https://en.wikipedia.org/wiki/File_URI_scheme
POSIX_PATH_URL = [
    ('/path/to/file', 'file:///path/to/file'),
    ('/path/to/file with space', 'file:///path/to/file%20with%20space'),
    ('/path/to/%20%21file', 'file:///path/to/%2520%2521file'),  # See: https://github.com/Tribler/tribler/issues/6700
    ('//path/to/file', 'file:////path/to/file'),
]

POSIX_URL_CORNER_CASES = [
    ('file:/path', '/path'),
    ('file://localhost/path', '/path'),
]

# https://docs.microsoft.com/en-us/dotnet/standard/io/file-path-formats
WIN_PATH_URL = [
    (r'C:\path\to\file', 'file:///C:/path/to/file'),
    (r'C:\path\to\file with space', 'file:///C:/path/to/file%20with%20space'),
    (r'C:\%20%21file', 'file:///C:/%2520%2521file'),  # See: https://github.com/Tribler/tribler/issues/6700
]

WIN_URL_CORNER_CASES = [
    ('file://server/share/path', r'\\server\share\path'),
]

SCHEMES = [
    ('file:///path/to/file', FILE_SCHEME),
    ('magnet:link', MAGNET_SCHEME),
    ('http://en.wikipedia.org', HTTP_SCHEME),
]


# posix
@pytest.mark.parametrize('path, url', POSIX_PATH_URL)
@patch('os.name', 'posix')
def test_round_trip_posix(path, url):
    assert path_to_url(path, _path_cls=PurePosixPath) == url
    assert url_to_path(url, _path_cls=PurePosixPath) == path


@pytest.mark.parametrize('url, path', POSIX_URL_CORNER_CASES)
@patch('os.name', 'posix')
def test_posix_corner_cases(url, path):
    assert url_to_path(url, _path_cls=PurePosixPath) == path


# win
@pytest.mark.parametrize('path, url', WIN_PATH_URL)
@patch('os.name', 'nt')
def test_round_trip_win(path, url):
    assert path_to_url(path, _path_cls=PureWindowsPath) == url
    assert url_to_path(url, _path_cls=PureWindowsPath) == path


@pytest.mark.parametrize('url, path', WIN_URL_CORNER_CASES)
@patch('os.name', 'nt')
def test_win_corner_cases(url, path):
    assert url_to_path(url, _path_cls=PureWindowsPath) == path


@pytest.mark.parametrize('path, scheme', SCHEMES)
def test_scheme_from_uri(path, scheme):
    assert scheme_from_url(path) == scheme


def test_uri_is_valid_file(tmpdir):
    file_path = tmpdir / '1.txt'
    file_path.write('test')
    file_uri = path_to_url(file_path)
    assert url_is_valid_file(file_uri)
    assert not url_is_valid_file(file_uri + '/*')
