import os
from typing import Any, Union

from yarl import URL

MAGNET_SCHEME = 'magnet'
HTTP_SCHEME = 'http'
FILE_SCHEME = 'file'


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
