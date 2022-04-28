from __future__ import annotations

import math
from typing import Iterable, Optional

from ipv8.types import Peer

import tribler.core.components.ipv8.eva.protocol as eva
from tribler.core.components.ipv8.eva.exceptions import SizeException, TransferException
from tribler.core.components.ipv8.eva.transfer.transfer import Transfer


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
