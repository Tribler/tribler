import os
from pathlib import Path
from typing import Any, Union

from yarl import URL

MAGNET_SCHEME = 'magnet'
FILE_SCHEME = 'file'
HTTP_SCHEME = 'http'
HTTPS_SCHEME = 'https'


def path_to_uri(file_path: Union[str, Any]) -> str:
    """Convert path to url

    Example:
        '/path/to/file' -> 'file:///path/to/file'
    """
    if not isinstance(file_path, str):
        file_path = str(file_path)
    return str(URL().build(scheme=FILE_SCHEME, path=file_path))


def uri_to_path(file_uri: str) -> str:
    """Convert uri to path

    Example:
        'file:///path/to/file' -> '/path/to/file'
    """
    path = URL(file_uri).path
    if os.name == 'nt':
        # Removes first slash for win OS
        # see https://github.com/aio-libs/yarl/issues/674
        return path.lstrip('/')
    return path


def scheme_from_uri(uri: str) -> str:
    """Get scheme from URI

    Examples:
        'file:///some/file' -> 'file'
        'magnet:link' -> 'magnet'
        'http://en.wikipedia.org' -> 'http'
    """
    return URL(uri).scheme


def uri_is_valid_file(file_uri: str) -> bool:
    file_path = uri_to_path(file_uri)
    try:
        return Path(file_path).is_file()
    except OSError:
        return False
