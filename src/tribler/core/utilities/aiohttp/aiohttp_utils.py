import asyncio
import logging
from ssl import SSLError
from typing import Dict, Optional, Union

from aiohttp import BaseConnector, ClientConnectorError, ClientResponseError, ClientSession, ClientTimeout, \
    ServerConnectionError
from aiohttp.hdrs import LOCATION
from aiohttp.typedefs import LooseHeaders

from tribler.core.utilities.aiohttp.exceptions import AiohttpException
from tribler.core.utilities.rest_utils import HTTPS_SCHEME, HTTP_SCHEME, scheme_from_url

logger = logging.getLogger(__name__)


async def query_uri(uri: str, connector: Optional[BaseConnector] = None, headers: Optional[LooseHeaders] = None,
                    timeout: ClientTimeout = None, return_json: bool = False, ) -> Union[Dict, bytes]:
    kwargs = {'headers': headers}
    if timeout:
        # ClientSession uses a sentinel object for the default timeout. Therefore, it should only be specified if an
        # actual value has been passed to this function.
        kwargs['timeout'] = timeout

    async with ClientSession(connector=connector, raise_for_status=True) as session:
        try:
            async with await session.get(uri, **kwargs) as response:
                if return_json:
                    return await response.json(content_type=None)
                return await response.read()
        except (ServerConnectionError, ClientResponseError, SSLError, ClientConnectorError, asyncio.TimeoutError) as e:
            message = f'Error while querying http uri. {e.__class__.__name__}: {e}'
            logger.warning(message, exc_info=e)
            raise AiohttpException(message) from e


async def unshorten(uri: str) -> str:
    """ Unshorten a URI if it is a short URI. Return the original URI if it is not a short URI.

    Args:
        uri (str): A string representing the shortened URL that needs to be unshortened.

    Returns:
        str: The unshortened URL. If the original URL does not redirect to another URL, the original URL is returned.
    """

    scheme = scheme_from_url(uri)
    if scheme not in (HTTP_SCHEME, HTTPS_SCHEME):
        return uri

    logger.info(f'Unshortening URI: {uri}')

    async with ClientSession() as session:
        try:
            async with await session.get(uri, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    uri = response.headers.get(LOCATION, uri)
        except Exception as e:
            logger.warning(f'Error while unshortening a URI: {e.__class__.__name__}: {e}', exc_info=e)

    logger.info(f'Unshorted URI: {uri}')
    return uri
