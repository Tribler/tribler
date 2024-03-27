import asyncio
from ssl import SSLError
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientConnectorError, ClientResponseError, ClientSession, ServerConnectionError
from aiohttp.hdrs import LOCATION, URI

from tribler.core.utilities.aiohttp.aiohttp_utils import query_uri, unshorten
from tribler.core.utilities.aiohttp.exceptions import AiohttpException

UNSHORTEN_TEST_DATA = [
    SimpleNamespace(
        # Test that the `unshorten` function returns the unshorten URL if there is a redirect detected by
        # the right status code and right header.
        url='http://shorten',
        response=SimpleNamespace(status=301, headers={LOCATION: 'http://unshorten'}),
        expected='http://unshorten'
    ),
    SimpleNamespace(
        # Test that the `unshorten` function returns the same URL if there is wrong scheme
        url='file://shorten',
        response=SimpleNamespace(status=0, headers={}),
        expected='file://shorten'
    ),
    SimpleNamespace(
        # Test that the `unshorten` function returns the same URL if there is no redirect detected by the wrong status
        # code.
        url='http://shorten',
        response=SimpleNamespace(status=401, headers={LOCATION: 'http://unshorten'}),
        expected='http://shorten'
    ),
    SimpleNamespace(
        # Test that the `unshorten` function returns the same URL if there is no redirect detected by the wrong header.
        url='http://shorten',
        response=SimpleNamespace(status=301, headers={URI: 'http://unshorten'}),
        expected='http://shorten'
    )
]


@pytest.mark.parametrize("test_data", UNSHORTEN_TEST_DATA)
async def test_unshorten(test_data):
    # The function mocks the ClientSession.get method to return a mocked response with the given status and headers.
    # It is used with the test data above to test the unshorten function.
    response = MagicMock(status=test_data.response.status, headers=test_data.response.headers)
    mocked_get = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))
    with patch.object(ClientSession, 'get', mocked_get):
        assert await unshorten(test_data.url) == test_data.expected


# These are the exceptions that are handled query_uri
HANDLED_EXCEPTIONS = [
    ServerConnectionError(),
    ClientResponseError(Mock(), Mock()),
    SSLError(),
    ClientConnectorError(Mock(), Mock()),
    asyncio.TimeoutError()
]


@pytest.mark.parametrize("e", HANDLED_EXCEPTIONS)
async def test_query_uri_handled_exceptions(e):
    # test that the function `query_uri` handles exceptions from the `HANDLED_EXCEPTIONS` list
    with patch.object(ClientSession, 'get', AsyncMock(side_effect=e)):
        with pytest.raises(AiohttpException):
            await query_uri('any.uri')


async def test_query_uri_unhandled_exceptions():
    # test that the function `query_uri` does not handle exceptions outside the `HANDLED_EXCEPTIONS` list.
    with patch.object(ClientSession, 'get', AsyncMock(side_effect=ZeroDivisionError)):
        with pytest.raises(ZeroDivisionError):
            await query_uri('any.uri')
