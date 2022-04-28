from __future__ import annotations

import asyncio
import time
from asyncio import Future
from typing import Optional

from ipv8.types import Peer

import tribler.core.components.ipv8.eva.protocol as eva
from tribler.core.components.ipv8.eva.exceptions import TimeoutException, TransferException


class Transfer:
    """The class describes an incoming or an outgoing transfer"""

    NONE = -1

    def __init__(self, protocol: eva.EVAProtocol, peer: Peer, info: bytes, data_size: int, nonce: int,
                 on_complete: Optional[eva.TransferCompleteCallback] = None):
        """ This class has been used internally by the EVA protocol"""
        self.protocol = protocol
        self.peer = peer
        self.info = info
        self.data_size = data_size
        self.nonce = nonce
        self.on_complete = on_complete
        self.future = Future()
        self.updated = 0
        self.attempt = 0
        self.finished = False

    def update(self):
        self.updated = time.time()

    def finish(self, *, result: Optional[eva.TransferResult] = None, exception: Optional[TransferException] = None):
        if self.finished:
            return

        if exception:
            eva.logger.warning(f'Finish with exception: {exception.__class__.__name__}: {exception}, Peer: {self.peer}')
            self.future.set_exception(exception)

            # To prevent "Future exception was never retrieved" error when the future is not used
            self.future.exception()

            if self.protocol.on_error:
                asyncio.create_task(self.protocol.on_error(self.peer, exception))

        if result:
            eva.logger.debug(f'Finish with result: {result}')
            self.future.set_result(result)
            if self.on_complete:
                asyncio.create_task(self.on_complete(result))

        self.finished = True
        self.protocol = None

    async def terminate_by_timeout_task(self):
        timeout = self.protocol.timeout_interval_in_sec
        remaining_time = timeout

        while self.protocol.terminate_by_timeout_enabled:
            await asyncio.sleep(remaining_time)
            if self.finished:
                return

            remaining_time = timeout - (time.time() - self.updated)
            if remaining_time <= 0:  # it is time to terminate
                exception = TimeoutException('Terminated by timeout', self)
                self.finish(exception=exception)
                return
