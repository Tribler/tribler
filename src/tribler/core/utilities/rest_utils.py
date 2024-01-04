import os
from typing import Any, Union

from yarl import URL

from tribler.core.utilities.path_util import Path

MAGNET_SCHEME = 'magnet'
FILE_SCHEME = 'file'
HTTP_SCHEME = 'http'
HTTPS_SCHEME = 'https'


def path_to_url(file_path: Union[str, Any], _path_cls=Path) -> str:
    """Convert path to url

    Example:
        '/path/to/file' -> 'file:///path/to/file'
    """
    return _path_cls(file_path).as_uri()


def url_to_path(file_url: str, _path_cls=Path) -> str:
    """Convert url to path

    Example:
        'file:///path/to/file' -> '/path/to/file'
    """

    def url_to_path_win():
        if url.host:
            # UNC file path, \\server\share\path...
            # ref: https://docs.microsoft.com/en-us/dotnet/standard/io/file-path-formats
            _, share, *segments = url.parts
            return str(_path_cls(rf'\\{url.host}\{share}', *segments))
        path = url.path.lstrip('/')
        return str(_path_cls(path))

    url = URL(file_url)
    if os.name == 'nt':
        return url_to_path_win()

    return str(_path_cls(url.path))


def scheme_from_url(url: str) -> str:
    """Get scheme from URL

    Examples:
        'file:///some/file' -> 'file'
        'magnet:link' -> 'magnet'
        'http://en.wikipedia.org' -> 'http'
    """
    return URL(url).scheme


def url_is_valid_file(file_url: str) -> bool:
    file_path = url_to_path(file_url)
    return Path(file_path).is_valid()
