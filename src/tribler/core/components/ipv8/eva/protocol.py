"""
EVA protocol: a protocol for transferring big binary data over ipv8.

Limitations and other useful information described in the corresponding class.
An example of use:

>>> import os
>>> class MyCommunity(Community):
...     community_id = os.urandom(20)
...
...     def __init__(self, *args, **kwargs):
...         super().__init__(*args, **kwargs)
...         self.eva = EVAProtocol(self, self.on_receive, self.on_send_complete, self.on_error)
...
...     async def my_function(self, peer):
...         await self.eva.send_binary(peer, b'info1', b'data1')
...         await self.eva.send_binary(peer, b'info2', b'data2')
...         await self.eva.send_binary(peer, b'info3', b'data3')
...
...     async def on_receive(self, result):
...         self.logger.info(f'Data has been received: {result}')
...
...     async def on_send_complete(self, result):
...         self.logger.info(f'Transfer has been completed: {result}')
...
...     async def on_error(self, peer, exception):
...         self.logger.error(f'Error has been occurred: {exception}')
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from itertools import chain
from random import SystemRandom
from typing import Awaitable, Callable, Dict, Optional, Type

from ipv8.community import Community
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.types import Peer

from tribler.core.components.ipv8.eva.aliases import TransferCompleteCallback, TransferErrorCallback
from tribler.core.components.ipv8.eva.exceptions import SizeException, TransferException, TransferLimitException, \
    ValueException
from tribler.core.components.ipv8.eva.payload import Acknowledgement, Data, Error, WriteRequest
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.settings import EVASettings
from tribler.core.components.ipv8.eva.transfer.base import Transfer
from tribler.core.components.ipv8.eva.transfer.incoming import IncomingTransfer
from tribler.core.components.ipv8.eva.transfer.outgoing import OutgoingTransfer
from tribler.core.components.ipv8.protocol_decorator import make_protocol_decorator

__version__ = '2.1.3'

logger = logging.getLogger('EVA')

MAX_U32 = 0xFFFFFFFF

message_handler = make_protocol_decorator('eva')


class EVAProtocol:  # pylint: disable=too-many-instance-attributes
    """EVAProtocol makes it possible to transfer big binary data over ipv8.

        The protocol based on TFTP with windowsize (RFC 7440).
        Features:
            * timeout
            * retransmit
            * dynamic window size

        The maximum data size that can be transferred through the protocol can be
        calculated as "block_size * 4294967295" where 4294967295 is the max segment
        number (4B unsigned int).
    """

    MIN_WINDOWS_SIZE = 1

    def __init__(  # pylint: disable=too-many-arguments
            self,
            community: Community,
            on_receive: Optional[TransferCompleteCallback] = None,
            on_send_complete: Optional[TransferCompleteCallback] = None,
            on_error: Optional[TransferErrorCallback] = None,
            start_message_id: int = 186,
            settings: Optional[EVASettings] = None
    ):
        """Init should be called manually within his parent class.

        Args:
        """
        self.community = community

        self.scheduled = defaultdict(deque)
        self.settings = settings or EVASettings()

        self.on_send_complete = on_send_complete
        self.on_receive = on_receive
        self.on_error = on_error

        self.incoming: Dict[Peer, IncomingTransfer] = {}
        self.outgoing: Dict[Peer, OutgoingTransfer] = {}

        self.random = SystemRandom()

        self.start_message_id = self.last_message_id = start_message_id
        self.eva_messages: Dict[Type[VariablePayload], int] = {}

        # note:
        # The order in which _eva_register_message_handler is called defines
        # the message wire format. Do not change it.
        self._register_message_handler(WriteRequest, self.on_write_request_packet)
        self._register_message_handler(Acknowledgement, self.on_acknowledgement_packet)
        self._register_message_handler(Data, self.on_data_packet)
        self._register_message_handler(Error, self.on_error_packet)

        community.register_task('scheduled send', self.send_scheduled,
                                interval=self.settings.scheduled_send_interval_in_sec)

        logger.debug(f'Initialized. Settings: {self.settings}.')

    def _register_message_handler(self, message_class: Type[VariablePayload], handler: Callable):
        self.community.add_message_handler(self.last_message_id, handler)
        self.eva_messages[message_class] = self.last_message_id
        self.last_message_id += 1

    def send_binary(self, peer: Peer, info: bytes, data: bytes) -> Awaitable[TransferResult]:
        """Send a big binary data.

        Due to ipv8 specifics, we can use only one socket port per one peer.
        Therefore, at one point in time, the protocol can only transmit one particular
        piece of data for one particular peer.

        In case "eva_send_binary" is invoked multiply times for a single peer, the data
        transfer will be scheduled and performed when the current sending session is finished.

        An example:
        >>> class MyCommunity(Community):
        ...     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.eva = EVAProtocol(self)
        ...
        ...     async def my_function(self, peer):
        ...         await self.eva.send_binary(peer, b'binary_info0', b'binary_data0')
        ...         await self.eva.send_binary(peer, b'binary_info1', b'binary_data1')
        ...         await self.eva.send_binary(peer, b'binary_info2', b'binary_data2')

        Args:
            peer: the target peer
            info: a binary info, limited by <block_size> bytes
            data: binary data that will be sent to the target.
                It is limited by several GB, but the protocol is slow by design, so
                try to send less rather than more.
        """
        if not data:
            raise ValueException('The empty data binary passed')

        if peer == self.community.my_peer:
            raise ValueException('The receiver can not be equal to the sender')

        nonce = self.random.randint(0, MAX_U32)
        transfer = OutgoingTransfer(data, self.outgoing, peer, info, nonce, self.settings,
                                    on_complete=self.on_send_complete, on_error=self.on_error)

        need_to_schedule = peer in self.outgoing or self._is_simultaneously_served_transfers_limit_exceeded()
        if need_to_schedule:
            self.scheduled[peer].append(transfer)
        else:
            self.start_outgoing_transfer(transfer)
        return transfer.future

    def send_message(self, peer: Peer, message: VariablePayload):
        self.community.endpoint.send(peer.address, self.community.ezr_pack(self.eva_messages[type(message)], message))

    def start_outgoing_transfer(self, transfer: OutgoingTransfer):
        self.outgoing[transfer.peer] = transfer

        self.community.register_anonymous_task('eva_terminate_by_timeout', transfer.terminate_by_timeout_task)
        self.community.register_anonymous_task('eva_send_write_request', self._send_write_request_task, transfer)

    @message_handler(WriteRequest)
    async def on_write_request_packet(self, peer: Peer, payload: WriteRequest):
        logger.debug(f'On write request. Peer: {peer}. Info: {payload.info}. Size: {payload.data_size}')

        if peer in self.incoming:
            return

        transfer = IncomingTransfer(self.incoming, peer, payload.info, payload.nonce, self.settings,
                                    on_complete=self.on_receive, on_error=self.on_error, data_size=payload.data_size)

        if payload.data_size <= 0:
            self._finish_with_error(transfer, ValueException('Data size can not be less or equal to 0'))
            return

        if payload.data_size > self.settings.binary_size_limit:
            e = SizeException(f'Current data size limit({self.settings.binary_size_limit}) has been exceeded', transfer)
            self._finish_with_error(transfer, e)
            return

        if self._is_simultaneously_served_transfers_limit_exceeded():
            exception = TransferLimitException('Maximum simultaneous transfers limit exceeded')
            self._finish_with_error(transfer, exception)
            return

        self.incoming[peer] = transfer

        self.community.register_anonymous_task('eva_terminate_by_timeout', transfer.terminate_by_timeout_task)
        self.community.register_anonymous_task('eva_resend_acknowledge', self._resend_acknowledge_task, transfer)
        self.send_message(peer, transfer.make_acknowledgement())

    @message_handler(Acknowledgement)
    async def on_acknowledgement_packet(self, peer: Peer, payload: Acknowledgement):
        logger.debug(f'On acknowledgement({payload.number}). Window size: {payload.window_size}. Peer: {peer}.')

        transfer = self.outgoing.get(peer)
        if not transfer:
            logger.warning(f'No outgoing transfer found with peer {peer} associated with incoming acknowledgement.')
            return

        if transfer.nonce != payload.nonce:
            logger.warning(f'Cannot handle incoming acknowledgement from peer {peer} - nonce mismatch.')
            return

        data_list = list(transfer.on_acknowledgement(payload.number, payload.window_size))
        is_transfer_finished = not data_list
        if is_transfer_finished:
            self.send_scheduled()
            return

        for data in data_list:
            logger.debug(f'Transmit({data.number}). Peer: {peer}.')
            self.send_message(peer, data)

    @message_handler(Data)
    async def on_data_packet(self, peer, payload):
        # Separate protected method for easier overriding in tests
        logger.debug(f'On data({payload.number}). Peer: {peer}. Data hash: {hash(payload.data)}')
        transfer = self.incoming.get(peer)
        if not transfer:
            return

        window_index = payload.number - transfer.window.start
        # The packet can be handled if payload number within [window_start..window_start+window_size)
        can_be_handled = 0 <= window_index < len(transfer.window.blocks)
        if not can_be_handled or transfer.nonce != payload.nonce:
            return

        acknowledgement = transfer.on_data(index=window_index, data=payload.data)
        if acknowledgement:
            self.send_message(transfer.peer, acknowledgement)
        if transfer.finished:
            self.send_scheduled()

    @message_handler(Error)
    async def on_error_packet(self, peer: Peer, error: Error):
        message = error.message.decode('utf-8')
        logger.debug(f'On error. Peer: {peer}. Message: "{message}"')

        transfer = self.outgoing.get(peer)
        if not transfer or transfer.nonce != error.nonce:
            return

        transfer.finish(exception=TransferException(message, transfer))
        self.send_scheduled()

    def send_scheduled(self):
        logger.debug('Looking for scheduled transfers for send...')

        free_peers = [peer for peer in self.scheduled if peer not in self.outgoing]

        for peer in free_peers:
            if not self.scheduled[peer]:
                self.scheduled.pop(peer, None)
                continue

            if self._is_simultaneously_served_transfers_limit_exceeded():
                break

            transfer = self.scheduled[peer].popleft()

            logger.debug(f'Scheduled send: {transfer}')
            self.start_outgoing_transfer(transfer)

    def shutdown(self):
        """This method terminates all current transfers"""
        logger.info('Shutting down...')
        transfers = list(chain(self.incoming.values(), self.outgoing.values()))
        for transfer in transfers:
            transfer.finish(exception=TransferException('Terminated due to shutdown'))
        logger.info('Shutting down completed')

    def _finish_with_error(self, transfer: Transfer, exception: TransferException):
        self.send_message(transfer.peer, Error(transfer.nonce, str(exception).encode('utf-8')))
        transfer.finish(exception=exception)

    async def _resend_acknowledge_task(self, transfer: IncomingTransfer):
        remaining_time = self.settings.retransmit_interval_in_sec

        while self.settings.retransmit_enabled:
            await asyncio.sleep(remaining_time)

            attempts_are_over = transfer.attempt >= self.settings.retransmit_attempt_count
            if attempts_are_over or transfer.finished:
                return

            remaining_time = self.settings.retransmit_interval_in_sec - (time.time() - transfer.updated)
            if remaining_time <= 0:  # it is time to retransmit
                transfer.attempt += 1
                remaining_time = self.settings.retransmit_interval_in_sec

                current_attempt = f'{transfer.attempt + 1}/{self.settings.retransmit_attempt_count}'
                logger.debug(f'Re-ack. Attempt: {current_attempt} for peer: {transfer.peer}')
                self.send_message(transfer.peer, transfer.make_acknowledgement())

    async def _send_write_request_task(self, transfer: OutgoingTransfer):
        for attempt in range(self.settings.retransmit_attempt_count + 1):
            if attempt:
                current_attempt = f'{attempt}/{self.settings.retransmit_attempt_count}'
                logger.debug(f'Re-write request. Attempt: {current_attempt} for peer: {transfer.peer}')

            if self.send_write_request(transfer):
                await asyncio.sleep(self.settings.retransmit_interval_in_sec)

            if not self.settings.retransmit_enabled or transfer.finished or transfer.acknowledgement_received:
                break

    def send_write_request(self, transfer: OutgoingTransfer) -> bool:
        # Returns True is the message was sent
        if transfer.finished:
            return False

        transfer.update()
        write_request = WriteRequest(transfer.data_size, transfer.nonce, transfer.info)
        logger.debug(f'Write Request. Peer: {transfer.peer}. Transfer: {self}')
        self.send_message(transfer.peer, write_request)
        return True

    def _is_simultaneously_served_transfers_limit_exceeded(self) -> bool:
        transfers_count = len(self.incoming) + len(self.outgoing)
        return transfers_count >= self.settings.max_simultaneous_transfers
