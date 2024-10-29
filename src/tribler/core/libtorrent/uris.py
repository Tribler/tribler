import logging
import os
from pathlib import Path

from aiohttp import ClientSession
from aiohttp.hdrs import LOCATION
from yarl import URL

logger = logging.getLogger(__name__)


def url_to_path(file_url: str) -> str:
    """
    Convert a URL to a path.

    For example:

    .. code-block::

        'file:///path/to/file' -> '/path/to/file'

    :param file_url: the URL for a file.
    :returns: the filesystem path for the file.
    """
    url = URL(file_url)

    if os.name == "nt" and url.host:
        # UNC file path, \\server\share\path...
        # ref: https://docs.microsoft.com/en-us/dotnet/standard/io/file-path-formats
        _, share, *segments = url.parts
        path = (rf"\\{url.host}\{share}", *segments)
    elif os.name == "nt":
        path = (url.path.lstrip("/"), )
    else:
        path = (url.path, )

    return str(Path(*path))


async def unshorten(uri: str) -> str:
    """
    Unshorten a URI if it is a short URI. Return the original URI if it is not a short URI.

    :param uri: A string representing the shortened URL that needs to be unshortened.
    :return: The unshortened URL. If the original URL does not redirect to another URL, the original URL is returned.
    """
    scheme = URL(uri).scheme
    if scheme not in ("http", "https"):
        return uri

    logger.info("Unshortening URI: %s", uri)

    async with ClientSession() as session:
        try:
            async with await session.get(uri, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    uri = response.headers.get(LOCATION, uri)
        except Exception as e:
            logger.warning("Error while unshortening a URI: %s: %s", e.__class__.__name__, str(e), exc_info=e)

    logger.info("Unshorted URI: %s", uri)
    return uri
