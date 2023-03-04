from __future__ import annotations

import asyncio
import logging
from math import isclose
from typing import Callable, Dict, Optional

from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.types import Peer

from tribler.core.components.ipv8.eva.aliases import TransferCompleteCallback, TransferErrorCallback
from tribler.core.components.ipv8.eva.exceptions import TimeoutException, TransferCancelledException, TransferException
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.settings import EVASettings
from tribler.core.utilities.async_group.async_group import AsyncGroup


class Transfer:
    """The class describes an incoming or an outgoing transfer"""

    NONE = -1

    def __init__(self, container: Dict[Peer, Transfer], peer: Peer, info: bytes, nonce: int, settings: EVASettings,
                 send_message: Callable[[Peer, VariablePayload], None], on_complete: TransferCompleteCallback,
                 on_error: TransferErrorCallback, protocol_task_group: AsyncGroup,
                 request: Optional[VariablePayload] = None, data_size: int = 0):
        """ This class has been used internally by the EVA protocol"""

        self.container = container
        self.peer = peer
        self.info = info
        self.data_size = data_size
        self.nonce = nonce
        self.send_message = send_message
        self.on_complete = on_complete
        self.on_error = on_error
        self.settings = settings
        self.protocol_task_group = protocol_task_group
        self.request = request
        self.request_received = False
        self.loop = asyncio.get_running_loop()
        self.future = self.loop.create_future()
        self.task_group = AsyncGroup()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.updated = None
        self.attempt = self.settings.retransmission.attempts
        self.finished = False
        self.started = False

        self.background_functions = [
            self.terminate_by_timeout,
            self.start_request,
        ]

        self.future.add_done_callback(self.on_future_cancelled)

    def start(self):
        if self.started:
            return
        self.logger.debug('Start')

        self.container[self.peer] = self
        for function in self.background_functions:
            self.task_group.add_task(function())

        self.started = True

    def update(self):
        self.updated = self.loop.time()
        self.logger.debug(f'Updated: {self.updated}')

    def _release(self):
        self.logger.debug('Release')
        self.finished = True

        self.protocol_task_group.add_task(self.task_group.cancel())

        if self.container:
            self.container.pop(self.peer, None)
            self.container = None

    def finish(self, *, result: Optional[TransferResult] = None, exception: Optional[TransferException] = None):
        if self.finished or self.future.done():
            return

        if exception:
            self.logger.warning(f'Finish with exception: {exception.__class__.__name__}: {exception}|Peer: {self.peer}')
            self.future.set_exception(exception)

            # To prevent "Future exception was never retrieved" error when the future is not used
            self.future.exception()
            self.protocol_task_group.add_task(self.on_error(self.peer, exception))

        if result:
            self.logger.debug(f'Finish with result: {result}')
            self.future.set_result(result)
            self.protocol_task_group.add_task(self.on_complete(result))

        self._release()

    def on_future_cancelled(self, _):
        if not self.future.cancelled():
            return

        self.logger.warning('Future was cancelled')
        exception = TransferCancelledException('The future was cancelled', self)
        self.protocol_task_group.add_task(self.on_error(self.peer, exception))
        self._release()

    async def terminate_by_timeout(self):
        remaining_time = self.settings.termination.timeout
        while self.settings.termination.enabled:
            await asyncio.sleep(remaining_time)
            if self.finished:
                return

            remaining_time = self._remaining(self.settings.termination.timeout)
            self.logger.debug(f'Remaining time before termination: {remaining_time:.6f}s')
            if self._the_time_has_come(remaining_time):  # it is time to terminate
                exception = TimeoutException('Terminated by timeout', self)
                self.finish(exception=exception)
                return

    async def start_request(self):
        attempts = self.attempt + 1
        for attempt in reversed(range(attempts)):
            if self.finished or self.request_received or not self.request:
                break

            current_attempt = self._format_attempt(remains=attempt, maximum=attempts)
            self.logger.debug(f'{self.request}. Attempt: {current_attempt} for peer: {self.peer}')

            self.update()
            self.send_message(self.peer, self.request)

            await asyncio.sleep(self.settings.retransmission.interval)

    def _remaining(self, timeout: float) -> float:
        if self.updated is None:
            return 0
        return timeout - (self.loop.time() - self.updated)

    @staticmethod
    def _the_time_has_come(remaining: float, tolerance: float = 0.001) -> bool:
        return remaining < 0 or isclose(remaining, 0, abs_tol=tolerance)

    @staticmethod
    def _format_attempt(remains: int, maximum: int) -> str:
        return f'{maximum - remains}/{maximum}'
