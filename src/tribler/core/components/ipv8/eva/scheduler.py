from __future__ import annotations

import logging
from asyncio import Future
from typing import Dict, Iterable, List, TYPE_CHECKING

from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.transfer.base import Transfer
from tribler.core.utilities.async_group.async_group import AsyncGroup

if TYPE_CHECKING:
    from tribler.core.components.ipv8.eva.protocol import EVAProtocol


class Scheduler:
    """This class is used for scheduling and sending a scheduled transfers in the EVA protocol"""

    def __init__(self, eva: EVAProtocol):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.eva = eva
        self.scheduled: Dict[Transfer] = {}  # this dict is used as an ordered set

        self.task_group = AsyncGroup()

    def can_be_send_immediately(self, transfer: Transfer) -> bool:
        """Test the transfer and decide can it be sent immediately or not"""
        peer_is_free = transfer.peer not in transfer.container
        return peer_is_free and not self._is_simultaneously_served_transfers_limit_exceeded()

    def schedule(self, transfer: Transfer) -> Future[TransferResult]:
        """Schedule transfer for the sending. In the case it can be sent immediately, it send immediately,
        without scheduling
        """
        if self.eva.shutting_down:
            raise RuntimeError('The protocol is in the shutting down state')

        if not self.can_be_send_immediately(transfer):
            self.scheduled[transfer] = True
        else:
            transfer.start()

        return transfer.future

    def send_scheduled(self) -> List[Transfer]:
        """Select transfers that can be sent immediately and send them"""
        started = []
        if self.eva.shutting_down:
            return started

        self.logger.debug('Looking for scheduled transfers for send...')
        for transfer in self._transfers_that_can_be_send():
            if self._is_simultaneously_served_transfers_limit_exceeded():
                break
            self.scheduled.pop(transfer)
            self.logger.debug(f'Scheduled send: {transfer}')
            started.append(transfer)

            transfer.start()

        return started

    async def shutdown(self):
        await self.task_group.cancel()

    def _transfers_that_can_be_send(self) -> Iterable[Transfer]:
        return (transfer for transfer in list(self.scheduled.keys()) if self.can_be_send_immediately(transfer))

    def _is_simultaneously_served_transfers_limit_exceeded(self) -> bool:
        transfers_count = len(self.eva.incoming) + len(self.eva.outgoing)
        return transfers_count >= self.eva.settings.max_simultaneous_transfers
