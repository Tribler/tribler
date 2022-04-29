from __future__ import annotations

from typing import List, Optional

from tribler.core.components.ipv8.eva.exceptions import TransferException
from tribler.core.components.ipv8.eva.payload import Acknowledgement
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.transfer.base import Transfer
from tribler.core.components.ipv8.eva.transfer.window import TransferWindow


class IncomingTransfer(Transfer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_list: List[bytes] = []
        self.window: Optional[TransferWindow] = None
        self.last_window = False

        self.update()

    def on_data(self, index: int, data: bytes) -> Optional[Acknowledgement]:
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
                result = TransferResult(peer=self.peer, info=self.info, data=data, nonce=self.nonce)
                self.finish(result=result)

        return acknowledgement

    def make_acknowledgement(self) -> Acknowledgement:
        if self.window:
            self.data_list.extend(self.window.consecutive_blocks())

        self.window = TransferWindow(start=len(self.data_list), size=self.settings.window_size)
        self.logger.debug(f'Transfer window: {self.window}')
        return Acknowledgement(self.window.start, len(self.window.blocks), self.nonce)

    def finish(self, *, result: Optional[TransferResult] = None, exception: Optional[TransferException] = None):
        self.container.pop(self.peer, None)
        super().finish(result=result, exception=exception)
        self.data_list = None
