from __future__ import annotations

import asyncio
from asyncio import StreamReader, get_running_loop
from io import BytesIO
from json import loads
from typing import TYPE_CHECKING, Any

from aiohttp import HttpVersion
from aiohttp.abc import AbstractStreamWriter
from aiohttp.http_parser import RawRequestMessage
from aiohttp.web_request import Request
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from yarl import URL

if TYPE_CHECKING:
    from tribler.core.restapi.rest_endpoint import RESTResponse


class BodyCapture(BytesIO, AbstractStreamWriter):
    """
    Helper-class to capture RESTResponse bodies.
    """

    async def write(self, value: bytes) -> None:
        """
        Write to our Bytes stream.
        """
        BytesIO.write(self, value)


class MockRequest(Request):
    """
    Base class for mocked REST requests.
    """

    class Transport:
        """
        A fake transport that does nothing.
        """

        def __init__(self) -> None:
            """
            Create a new fake Transport.
            """
            super().__init__()
            self.closing = False

        def get_extra_info(self, _: str) -> None:
            """
            Get extra info, which is always None.
            """
            return

        def is_closing(self) -> bool:
            """
            Get the closing state.
            """
            return self.closing

    def __init__(self, query: dict, method: str = "GET", path: str = "",
                 payload_writer: AbstractStreamWriter | None = None) -> None:
        """
        Create a new MockRequest, just like if it were returned from aiohttp.
        """
        message = RawRequestMessage(method, path, HttpVersion(1, 0), CIMultiDictProxy(CIMultiDict({})),
                                    ((b'', b''),), True, None, False, False, URL(path))
        self._transport = MockRequest.Transport()
        super().__init__(message=message, payload=StreamReader(), protocol=self,
                         payload_writer=payload_writer, task=None, loop=get_running_loop())
        self._query = query

    @property
    def query(self) -> MultiDictProxy[str]:
        """
        Overwrite the query with the query passed in our constructor.
        """
        return MultiDictProxy(MultiDict(self._query))

    @property
    def transport(self) -> asyncio.Transport | None:
        """
        Overwrite the transport with our fake transport.
        """
        return self._transport


async def response_to_bytes(response: RESTResponse) -> bytes:
    """
    Get the bytes of a RESTResponse's body.
    """
    capture = BodyCapture()
    if isinstance(response.body, bytes):
        return response.body
    await response.body.write(capture)
    return capture.getvalue()


async def response_to_json(response: RESTResponse) -> Any:  # noqa: ANN401
    """
    Get the JSON dict of a RESTResponse's body.
    """
    return loads(await response_to_bytes(response))
