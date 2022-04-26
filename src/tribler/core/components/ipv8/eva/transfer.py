from __future__ import annotations

import asyncio
import math
import time
from asyncio import Future
from typing import Iterable, List, Optional

from ipv8.types import Peer

import tribler.core.components.ipv8.eva.protocol as eva
from tribler.core.components.ipv8.eva.exceptions import SizeException, TimeoutException, TransferException


class Transfer:  # pylint: disable=too-many-instance-attributes
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


class IncomingTransfer(Transfer):
    def __init__(self, protocol: eva.EVAProtocol, peer: Peer, info: bytes, data_size: int, nonce: int,
                 on_complete: Optional[eva.TransferCompleteCallback] = None):
        super().__init__(protocol, peer, info, data_size, nonce, on_complete)
        self.data_list: List[bytes] = []
        self.window: Optional[TransferWindow] = None
        self.last_window = False

        self.update()

    def on_data(self, index: int, data: bytes) -> Optional[eva.Acknowledgement]:
        is_final_data_packet = len(data) == 0
        if is_final_data_packet:
            self.last_window = True
            self.window.blocks = self.window.blocks[:index + 1]

        self.window.add(index, data)
        self.attempt = 0

        self.update()

        acknowledgement = None
        if self.window.is_finished():
            acknowledgement = self.make_acknowledgement()
            if self.last_window:
                data = b''.join(self.data_list)
                result = eva.TransferResult(peer=self.peer, info=self.info, data=data, nonce=self.nonce)
                self.finish(result=result)

        return acknowledgement

    def make_acknowledgement(self) -> eva.Acknowledgement:
        if self.window:
            self.data_list.extend(self.window.consecutive_blocks())

        self.window = TransferWindow(start=len(self.data_list), size=self.protocol.window_size)
        eva.logger.debug(f'Transfer window: {self.window}')
        return eva.Acknowledgement(self.window.start, len(self.window.blocks), self.nonce)

    def finish(self, *, result: Optional[eva.TransferResult] = None, exception: Optional[TransferException] = None):
        self.protocol.incoming.pop(self.peer, None)
        super().finish(result=result, exception=exception)
        self.data_list = None


class OutgoingTransfer(Transfer):
    def __init__(self, protocol: eva.EVAProtocol, peer: Peer, info: bytes, data: bytes, nonce: int,
                 on_complete: Optional[eva.TransferCompleteCallback] = None):
        limit = protocol.binary_size_limit
        data_size = len(data)
        if data_size > limit:
            raise SizeException(f'Current data size limit {limit} has been exceeded: {data_size}')

        super().__init__(protocol, peer, info, data_size, nonce, on_complete)
        self.data = data
        self.block_count = math.ceil(data_size / self.protocol.block_size)
        self.acknowledgement_received = False

    def on_acknowledgement(self, ack_number: int, window_size: int) -> Iterable[eva.Data]:
        self.update()
        self.acknowledgement_received = True
        is_final_acknowledgement = ack_number > self.block_count
        if is_final_acknowledgement:
            result = eva.TransferResult(peer=self.peer, info=self.info, data=self.data, nonce=self.nonce)
            self.finish(result=result)
            return

        for block_number in range(ack_number, ack_number + window_size):
            block = self._get_block(block_number)
            yield eva.Data(block_number, self.nonce, block)
            if len(block) == 0:
                return

    def finish(self, *, result: Optional[eva.TransferResult] = None, exception: Optional[TransferException] = None):
        self.protocol.outgoing.pop(self.peer, None)
        super().finish(result=result, exception=exception)
        self.data = None

    def _get_block(self, number: int) -> bytes:
        start_position = number * self.protocol.block_size
        stop_position = start_position + self.protocol.block_size
        return self.data[start_position:stop_position]


class TransferWindow:
    def __init__(self, start: int, size: int):
        self.blocks: List[Optional[bytes]] = [None] * size

        self.start = start
        self.processed: int = 0

    def add(self, index: int, block: bytes):
        if self.blocks[index] is not None:
            return
        self.blocks[index] = block
        self.processed += 1

    def is_finished(self) -> bool:
        return self.processed == len(self.blocks)

    def consecutive_blocks(self):
        for block in self.blocks:
            if block is None:
                break
            yield block

    def __str__(self):
        return f'{{start: {self.start}, processed: {self.processed}, size: {len(self.blocks)}}}'
