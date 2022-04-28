from __future__ import annotations

from typing import List, Optional

from ipv8.types import Peer
import tribler.core.components.ipv8.eva.protocol as eva

from tribler.core.components.ipv8.eva.exceptions import TransferException
from tribler.core.components.ipv8.eva.transfer.transfer import Transfer
from tribler.core.components.ipv8.eva.transfer.transfer_window import TransferWindow


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