from __future__ import annotations

import asyncio
from typing import List, Optional

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
        self.background_functions.append(self.send_acknowledge)

    def on_data(self, index: int, data: bytes) -> Optional[Acknowledgement]:
        self.request_received = True
        is_final_data_packet = len(data) == 0
        if is_final_data_packet:
            self.last_window = True
            self.window.blocks = self.window.blocks[:index + 1]

        self.window.add(index, data)
        self.attempt = self.settings.retransmission.attempts
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

    def _release(self):
        super()._release()
        self.data_list = None

    async def send_acknowledge(self):
        while True:
            attempts_are_over = self.attempt <= 0
            if attempts_are_over or self.finished:
                return

            remaining_time = self._remaining(self.settings.retransmission.interval)
            if self._the_time_has_come(remaining_time):  # it is time to retransmit
                remaining_time = self.settings.retransmission.interval
                self.attempt -= 1

                current_attempt = self._format_attempt(remains=self.attempt,
                                                       maximum=self.settings.retransmission.attempts)
                acknowledgement = self.make_acknowledgement()
                self.logger.debug(f'Ack({acknowledgement.number}). Attempt: {current_attempt} for peer: {self.peer}')
                self.send_message(self.peer, acknowledgement)

            self.logger.debug(f'Remaining time before send acknowledge: {remaining_time:.6f}s')
            await asyncio.sleep(remaining_time)
