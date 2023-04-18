from asyncio import CancelledError, Task
from threading import Lock
from typing import Type

from aiohttp import StreamReader
from aiohttp.abc import AbstractStreamWriter
from aiohttp.http_parser import RawRequestMessage
from aiohttp.web_app import Application
from aiohttp.web_protocol import RequestHandler
from aiohttp.web_request import Request


transport_is_none_counter = 0
counter_lock = Lock()


def increment_transport_is_none_counter():
    global transport_is_none_counter  # pylint: disable=global-statement
    with counter_lock:
        transport_is_none_counter += 1


def get_transport_is_none_counter() -> int:
    with counter_lock:
        return transport_is_none_counter


def patch_make_request(cls: Type[Application]) -> bool:
    # This function monkey-patches a bug in the aiohttp library, see #7344 and aio-libs/aiohttp#7258.
    # The essence of the bug is that the `aiohttp.web_protocol.RequestHandler.start()` coroutine erroneously continues
    # to run after a connection was closed from the client side, the transport was closed, and None was assigned
    # to `self.transport`. Then the `start` coroutine calls `self._make_request(...)`, which in turn creates
    # an `aiohttp.web_request.Request` instance, and it has `assert transport is not None` in its constructor.
    #
    # To fix the bug, the monkey-patched `_make_request` method first checks if the `self.transport is None`, and if so,
    # it raises the `CancelledError` exception to cancel the erroneously working `RequestHandler.start` coroutine.
    #
    # Additionally, the new `_make_request` method increases the counter of cases when the transport was None
    # to allow gathering some statistics on how often this situation happens

    original_make_request = cls._make_request  # pylint: disable=protected-access
    if getattr(original_make_request, 'patched', False):
        return False

    def new_make_request(
            self,
            message: RawRequestMessage,
            payload: StreamReader,
            protocol: RequestHandler,
            writer: AbstractStreamWriter,
            task: Task,
            _cls: Type[Request] = Request,
    ) -> Request:
        if protocol.transport is None:
            increment_transport_is_none_counter()
            raise CancelledError

        return original_make_request(
            self, message=message, payload=payload, protocol=protocol, writer=writer, task=task, _cls=_cls
        )

    new_make_request.patched = True
    cls._make_request = new_make_request  # pylint: disable=protected-access
    return True
