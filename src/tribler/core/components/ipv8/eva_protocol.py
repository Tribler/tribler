"""
EVA protocol: a protocol for transferring big binary data over ipv8.

Limitations and other useful information described in the corresponding class.
An example of use:

>>> import os
>>> from ipv8.community import Community
>>> class MyCommunity(EVAProtocolMixin, Community):
...     community_id = os.urandom(20)
...
>>>     def __init__(self, *args, **kwargs):
...         super().__init__(*args, **kwargs)
...         self.eva_init()
...
...         self.eva.register_receive_callback(self.on_receive)
...         self.eva.register_send_complete_callback(self.on_send_complete)
...         self.eva.register_error_callback(self.on_error)
...
>>>     async def my_function(self, peer):
...         await self.eva.send_binary(peer, b'info1', b'data1')
...         await self.eva.send_binary(peer, b'info2', b'data2')
...         await self.eva.send_binary(peer, b'info3', b'data3')
...
>>>     async def on_receive(self, result):
...         self.logger.info(f'Data has been received: {result}')
...
>>>     async def on_send_complete(self, result):
...         self.logger.info(f'Transfer has been completed: {result}')
...
>>>     async def on_error(self, peer, exception):
...         self.logger.error(f'Error has been occurred: {exception}')
"""
__version__ = '2.0.0'

import asyncio
import logging
import math
import time
from asyncio import Future
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum, auto
from random import SystemRandom
from typing import Awaitable, Callable, Dict, Optional, Type

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.types import Peer

logger = logging.getLogger('EVA')

MAX_U64 = 0xFFFFFFFF


@vp_compile
class WriteRequest(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['data_size', 'nonce', 'info']


@vp_compile
class Acknowledgement(VariablePayload):
    format_list = ['I', 'I', 'I']
    names = ['number', 'window_size', 'nonce']


@vp_compile
class Data(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['block_number', 'nonce', 'data']


@vp_compile
class Error(VariablePayload):
    format_list = ['I', 'raw']
    names = ['nonce', 'message']


class EVAProtocolMixin:
    """This mixin makes it possible to transfer big binary data over ipv8.

        The protocol based on TFTP with windowsize (RFC 7440).
        Features:
            * timeout
            * retransmit
            * dynamic window size

        The maximum data size that can be transferred through the protocol can be
        calculated as "block_size * 4294967295" where 4294967295 is the max segment
        number (4B unsigned int).
    """

    def eva_init(self, start_message_id: int = 186, **kwargs):
        """Init should be called manually within his parent class.
        For the arguments description see `EVAProtocol` class.
        """
        self.eva = EVAProtocol(community=self, **kwargs)
        self.last_message_id = start_message_id
        self.eva_messages: Dict[Type[VariablePayload], int] = {}

        # note:
        # The order in which _eva_register_message_handler is called defines
        # the message wire format. Do not change it.
        self._eva_register_message_handler(WriteRequest, self.on_eva_write_request)
        self._eva_register_message_handler(Acknowledgement, self.on_eva_acknowledgement)
        self._eva_register_message_handler(Data, self.on_eva_data)
        self._eva_register_message_handler(Error, self.on_eva_error)

    def eva_send_message(self, peer: Peer, message: VariablePayload):
        self.endpoint.send(peer.address, self.ezr_pack(self.eva_messages[type(message)], message))

    @lazy_wrapper(WriteRequest)
    async def on_eva_write_request(self, peer: Peer, payload: WriteRequest):
        await self.eva.on_write_request(peer, payload)

    @lazy_wrapper(Acknowledgement)
    async def on_eva_acknowledgement(self, peer: Peer, payload: Acknowledgement):
        await self.eva.on_acknowledgement(peer, payload)

    @lazy_wrapper(Data)
    async def on_eva_data(self, peer: Peer, payload: Data):
        await self.eva.on_data(peer, payload)

    @lazy_wrapper(Error)
    async def on_eva_error(self, peer: Peer, payload: Error):
        await self.eva.on_error(peer, payload)

    def _eva_register_message_handler(self, message_class: Type[VariablePayload], handler: Callable):
        self.add_message_handler(self.last_message_id, handler)
        self.eva_messages[message_class] = self.last_message_id
        self.last_message_id += 1


class TransferType(Enum):
    INCOMING = auto()
    OUTGOING = auto()


@dataclass
class TransferResult:
    peer: Peer
    info: bytes
    data: bytes
    nonce: int


class Transfer:  # pylint: disable=too-many-instance-attributes
    """The class describes an incoming or an outgoing transfer"""

    NONE = -1

    def __init__(self, transfer_type: TransferType, info: bytes, data: bytes, data_size: int, block_count: int,
                 nonce: int, peer: Peer, protocol, future: Optional[Future] = None, window_size: int = 0,
                 updated: float = 0):
        """ This class has been used internally by the EVA protocol"""
        self.type = transfer_type
        self.info = info
        self.data = data
        self.data_size = data_size
        self.block_count = block_count
        self.block_number = Transfer.NONE
        self.future = future
        self.peer = peer
        self.nonce = nonce
        self.window_size = window_size
        self.updated = updated
        self.protocol = protocol

        self.attempt = 0
        self.acknowledgement_number = 0
        self.terminated = False

    def finish(self):
        result = TransferResult(peer=self.peer, info=self.info, data=self.data, nonce=self.nonce)
        self.terminate(result=result)

    def terminate(self, result: Optional[TransferResult] = None, exception: Optional[Exception] = None):
        if self.terminated:
            return

        logger.debug(f'Terminate. Peer: {self.peer}. Transfer: {self}')

        container = self.protocol.incoming if self.type == TransferType.INCOMING else self.protocol.outgoing
        container.pop(self.peer, None)

        if result:
            self._terminate_with_result(result)
        if exception:
            self._terminate_with_exception(exception)

        self.info = None
        self.data = None
        self.peer = None
        self.protocol = None
        self.future = None

        self.terminated = True

    def _terminate_with_result(self, result: TransferResult):
        if self.future:
            self.future.set_result(result)

        callbacks = self.protocol.receive_callbacks if self.type == TransferType.INCOMING \
            else self.protocol.send_complete_callbacks

        for callback in callbacks:
            asyncio.create_task(callback(result))

    def _terminate_with_exception(self, exception: Exception):
        logger.warning(f'Peer hash: {self.peer}: "{exception.__class__.__name__}: {exception}".')

        if self.future:
            self.future.set_exception(exception)

        for callback in self.protocol.error_callbacks:
            asyncio.create_task(callback(self.peer, exception))

    def __str__(self):
        return (
            f'Type: {self.type}. Info: {self.info}. Block: {self.block_number}({self.block_count}). '
            f'Window size: {self.window_size}. Updated: {self.updated}'
        )


class TransferException(Exception):
    def __init__(self, message: str, transfer: Optional[Transfer] = None):
        super().__init__(message)
        self.transfer = transfer
        self.message = message


class SizeException(TransferException):
    pass


class TimeoutException(TransferException):
    pass


class ValueException(TransferException):
    pass


class TransferLimitException(TransferException):
    """Maximum simultaneous transfers limit exceeded"""


class EVAProtocol:  # pylint: disable=too-many-instance-attributes
    MIN_WINDOWS_SIZE = 1

    def __init__(  # pylint: disable=too-many-arguments
            self,
            community,
            block_size=1000,
            window_size_in_blocks=16,
            start_message_id=186,
            retransmit_interval_in_sec=3,
            retransmit_attempt_count=3,
            scheduled_send_interval_in_sec=5,
            timeout_interval_in_sec=10,
            binary_size_limit=1024 * 1024 * 1024,
            terminate_by_timeout_enabled=True,
            max_simultaneous_transfers=10
    ):
        """Init should be called manually within his parent class.

        Args:
            block_size: a single block size in bytes. Please keep in mind that
                ipv8 adds approx. 177 bytes to each packet.
            window_size_in_blocks: size of consecutive blocks to send
            start_message_id: a started id that will be used to assigning
                protocol's messages ids
            retransmit_interval_in_sec: an interval until the next attempt
                to retransmit will be made
            retransmit_attempt_count: a limit for retransmit attempts
            timeout_interval_in_sec: an interval after which the transfer will
                be considered as "dead" and will be terminated
            binary_size_limit: limit for binary data size. If this limit will be
                exceeded, the exception will be returned through a registered
                error handler
            terminate_by_timeout_enabled: the flag indicating is termination-by-timeout
                mechanism enabled or not
            max_simultaneous_transfers: an upper limit of simultaneously served peers.
                The reason for introducing this parameter is to have a tool for
                limiting socket load which could lead to packet loss.
        """
        self.community = community

        self.scheduled = defaultdict(deque)
        self.block_size = block_size
        self.window_size = window_size_in_blocks
        self.retransmit_interval_in_sec = retransmit_interval_in_sec
        self.retransmit_attempt_count = retransmit_attempt_count
        self.timeout_interval_in_sec = timeout_interval_in_sec
        self.scheduled_send_interval_in_sec = scheduled_send_interval_in_sec
        self.binary_size_limit = binary_size_limit
        self.max_simultaneous_transfers = max_simultaneous_transfers

        self.send_complete_callbacks = set()
        self.receive_callbacks = set()
        self.error_callbacks = set()

        self.incoming: Dict[Peer, Transfer] = {}
        self.outgoing: Dict[Peer, Transfer] = {}

        self.retransmit_enabled = True
        self.terminate_by_timeout_enabled = terminate_by_timeout_enabled
        self.random = SystemRandom()

        community.register_task('scheduled send', self.send_scheduled, interval=scheduled_send_interval_in_sec)

        logger.debug(
            f'Initialized. Block size: {block_size}. Window size: {window_size_in_blocks}. '
            f'Start message id: {start_message_id}. Retransmit interval: {retransmit_interval_in_sec}sec. '
            f'Max retransmit attempts: {retransmit_attempt_count}. Timeout: {timeout_interval_in_sec}sec. '
            f'Scheduled send interval: {scheduled_send_interval_in_sec}sec. '
            f'Binary size limit: {binary_size_limit}.'
        )

    def send_binary(self, peer: Peer, info: bytes, data: bytes, nonce: Optional[int] = None) -> Future:
        """Send a big binary data.

        Due to ipv8 specifics, we can use only one socket port per one peer.
        Therefore, at one point in time, the protocol can only transmit one particular
        piece of data for one particular peer.

        In case "eva_send_binary" is invoked multiply times for a single peer, the data
        transfer will be scheduled and performed when the current sending session is finished.

        An example:
        >>> from ipv8.community import Community
        >>> class MyCommunity(EVAProtocolMixin, Community)
        >>>     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.eva_init()
        ...
        >>>     async def my_function(self, peer):
        ...         await self.eva.send_binary(peer, b'binary_data0', b'binary_info0')
        ...         await self.eva.send_binary(peer, b'binary_data1', b'binary_info1')
        ...         await self.eva.send_binary(peer, b'binary_data2', b'binary_info2')

        Args:
            peer: the target peer
            info: a binary info, limited by <block_size> bytes
            data: binary data that will be sent to the target.
                It is limited by several GB, but the protocol is slow by design, so
                try to send less rather than more.
            nonce: a unique number for identifying the session. If not specified, generated randomly
        """
        if not data:
            raise ValueException('The empty data binary passed')

        if peer == self.community.my_peer:
            raise ValueException('The receiver can not be equal to the sender')

        data_size = len(data)
        if data_size > self.binary_size_limit:
            raise SizeException(f'Current data size limit({self.binary_size_limit}) has been exceeded')

        transfer = Transfer(
            transfer_type=TransferType.OUTGOING,
            info=info,
            data=data,
            data_size=data_size,
            block_count=math.ceil(data_size / self.block_size),
            nonce=nonce if nonce is not None else self.random.randint(0, MAX_U64),
            future=Future(),
            peer=peer,
            protocol=self
        )

        need_to_schedule = peer in self.outgoing or self._is_simultaneously_served_transfers_limit_exceeded()
        if need_to_schedule:
            self.scheduled[peer].append(transfer)
            return transfer.future

        self.start_outgoing_transfer(transfer)
        return transfer.future

    def register_receive_callback(self, callback: Callable[[TransferResult], Awaitable[None]]):
        """Register callback that will be invoked when a data receiving is complete.

        An example:
        >>> import os
        >>> from ipv8.community import Community
        >>> class MyCommunity(EVAProtocolMixin, Community):
        >>>     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.eva_init()
        ...         self.eva.register_receive_callback(self.on_receive)
        ...
        >>>     async def on_receive(self, result):
        ...         self.logger.info(f'Data has been received: {result}')

        """
        self.receive_callbacks.add(callback)

    def register_send_complete_callback(self, callback: Callable[[TransferResult], Awaitable[None]]):
        """Register callback that will be invoked when a data sending is complete.

        An example:
        >>> import os
        >>> from ipv8.community import Community
        >>> class MyCommunity(EVAProtocolMixin, Community):
        >>>     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.eva_init()
        ...         self.eva.register_send_complete_callback(self.on_send_complete)
        ...
        >>>     async def on_send_complete(self, result):
        ...         self.logger.info(f'Transfer has been completed: {result}')

        """
        self.send_complete_callbacks.add(callback)

    def register_error_callback(self, callback: Callable[[Peer, TransferException], Awaitable[None]]):
        """Register callback that will be invoked in case of an error.

        An example:

        >>> import os
        >>> from ipv8.community import Community
        >>> class MyCommunity(EVAProtocolMixin, Community):
        >>>     def __init__(self, *args, **kwargs):
        ...         super().__init__(*args, **kwargs)
        ...         self.eva_init()
        ...         self.eva.register_error_callback(self.on_error)
        ...
        >>>     async def on_error(self, peer, exception):
        ...         self.logger.error(f'Error has been occurred: {exception}')

        """
        self.error_callbacks.add(callback)

    def start_outgoing_transfer(self, transfer: Transfer):
        self.outgoing[transfer.peer] = transfer

        self.community.register_anonymous_task('eva_terminate_by_timeout', self._terminate_by_timeout_task, transfer)
        self.community.register_anonymous_task('eva_send_write_request', self._send_write_request_task, transfer)

    def send_write_request(self, transfer: Transfer):
        if transfer.terminated:
            return
        transfer.updated = time.time()
        write_request = WriteRequest(transfer.data_size, transfer.nonce, transfer.info)
        logger.debug(f'Write Request. Peer: {transfer.peer}. Transfer: {transfer}')
        self.community.eva_send_message(transfer.peer, write_request)

    async def on_write_request(self, peer: Peer, payload: WriteRequest):
        logger.debug(f'On write request. Peer: {peer}. Info: {payload.info}. Size: {payload.data_size}')

        if peer in self.incoming:
            return

        transfer = Transfer(
            transfer_type=TransferType.INCOMING,
            info=payload.info,
            data=b'',
            data_size=payload.data_size,
            block_count=0,
            nonce=payload.nonce,
            future=None,
            peer=peer,
            window_size=self.window_size,
            updated=time.time(),
            protocol=self
        )

        if payload.data_size <= 0:
            self._terminate_by_error(transfer, ValueException('Data size can not be less or equal to 0'))
            return

        if self._is_simultaneously_served_transfers_limit_exceeded():
            exception = TransferLimitException('Maximum simultaneous transfers limit exceeded')
            self._terminate_by_error(transfer, exception)
            return

        if payload.data_size > self.binary_size_limit:
            e = SizeException(f'Current data size limit({self.binary_size_limit}) has been exceeded', transfer)
            self._terminate_by_error(transfer, e)
            return

        self.incoming[peer] = transfer

        self.community.register_anonymous_task('eva_terminate_by_timeout', self._terminate_by_timeout_task, transfer)
        self.community.register_anonymous_task('eva_resend_acknowledge', self._resend_acknowledge_task, transfer)
        self.send_acknowledgement(transfer)

    async def on_acknowledgement(self, peer: Peer, payload: Acknowledgement):
        logger.debug(f'On acknowledgement({payload.number}). Window size: {payload.window_size}. Peer: {peer}.')

        transfer = self.outgoing.get(peer)
        if not transfer:
            logger.warning("No outgoing transfer found with peer %s associated with incoming ackowledgement.", peer)
            return

        if transfer.block_number > payload.number:
            logger.warning("Cannot handle incoming acknowledgement from peer %s - ack num mismatch (%d - %d)",
                           peer, transfer.block_number, payload.number)
            return

        if transfer.nonce != payload.nonce:
            logger.warning("Cannot handle incoming acknowledgement from peer %s - nonce mismatch", peer)
            return

        transfer.block_number = payload.number
        if transfer.block_number > transfer.block_count:
            transfer.finish()
            self.send_scheduled()
            return

        transfer.window_size = max(self.MIN_WINDOWS_SIZE, min(payload.window_size, self.binary_size_limit))
        transfer.updated = time.time()

        for block_number in range(transfer.block_number, transfer.block_number + transfer.window_size):
            start_position = block_number * self.block_size
            stop_position = start_position + self.block_size
            data = transfer.data[start_position:stop_position]
            logger.debug(f'Transmit({block_number}). Peer: {peer}.')
            self.community.eva_send_message(peer, Data(block_number, transfer.nonce, data))
            if len(data) == 0:
                break

    async def on_data(self, peer, payload):
        logger.debug(f'On data({payload.block_number}). Peer: {peer}. Data hash: {hash(payload.data)}')
        transfer = self.incoming.get(peer)
        if not transfer:
            return

        can_be_handled = transfer.block_number == payload.block_number - 1
        if not can_be_handled or transfer.nonce != payload.nonce:
            return

        transfer.block_number = payload.block_number

        is_final_data_packet = len(payload.data) == 0
        if is_final_data_packet:
            self.send_acknowledgement(transfer)
            transfer.finish()
            self.send_scheduled()
            return

        data_size = len(transfer.data) + len(payload.data)
        if data_size > self.binary_size_limit:
            e = SizeException(f'Current data size limit({self.binary_size_limit}) has been exceeded', transfer)
            self._terminate_by_error(transfer, e)
            return

        transfer.data += payload.data

        transfer.attempt = 0
        transfer.updated = time.time()

        time_to_acknowledge = transfer.acknowledgement_number + transfer.window_size <= transfer.block_number + 1
        if time_to_acknowledge:
            self.send_acknowledgement(transfer)

    def send_acknowledgement(self, transfer: Transfer):
        ack = transfer.block_number + 1

        transfer.acknowledgement_number = ack
        logger.debug(f'Ack ({ack}). Window size: {transfer.window_size}. Peer: {transfer.peer}')

        acknowledgement = Acknowledgement(ack, transfer.window_size, transfer.nonce)
        self.community.eva_send_message(transfer.peer, acknowledgement)

    async def on_error(self, peer: Peer, error: Error):
        message = error.message.decode('utf-8')
        logger.debug(f'On error. Peer: {peer}. Message: "{message}"')

        transfer = self.outgoing.get(peer)
        if not transfer or transfer.nonce != error.nonce:
            return

        transfer.terminate(exception=TransferException(message, transfer))
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
        transfers = list(self.incoming.values()) + list(self.outgoing.values())
        for transfer in transfers:
            transfer.terminate(exception=TransferException('Terminated due to shutdown'))
        logger.info('Shutting down completed')

    def _terminate_by_error(self, transfer: Transfer, exception: TransferException):
        self.community.eva_send_message(transfer.peer, Error(transfer.nonce, exception.message.encode('utf-8')))
        transfer.terminate(exception=exception)

    async def _terminate_by_timeout_task(self, transfer: Transfer):
        remaining_time = self.timeout_interval_in_sec

        while self.terminate_by_timeout_enabled:
            await asyncio.sleep(remaining_time)
            if transfer.terminated:
                return

            remaining_time = self.timeout_interval_in_sec - (time.time() - transfer.updated)
            if remaining_time <= 0:  # it is time to terminate
                exception = TimeoutException('Terminated by timeout', transfer)
                transfer.terminate(exception=exception)
                return

    async def _resend_acknowledge_task(self, transfer: Transfer):
        remaining_time = self.retransmit_interval_in_sec

        while self.retransmit_enabled:
            await asyncio.sleep(remaining_time)

            attempts_are_over = transfer.attempt >= self.retransmit_attempt_count
            if attempts_are_over or transfer.terminated:
                return

            remaining_time = self.retransmit_interval_in_sec - (time.time() - transfer.updated)
            if remaining_time <= 0:  # it is time to retransmit
                transfer.attempt += 1
                remaining_time = self.retransmit_interval_in_sec

                current_attempt = f'{transfer.attempt + 1}/{self.retransmit_attempt_count}'
                logger.debug(f'Re-ack ({transfer.acknowledgement_number}). '
                             f'Attempt: {current_attempt} for peer: {transfer.peer}')

                self.send_acknowledgement(transfer)

    async def _send_write_request_task(self, transfer: Transfer):
        self.send_write_request(transfer)

        if not self.retransmit_enabled:
            return

        for attempt in range(self.retransmit_attempt_count):
            await asyncio.sleep(self.retransmit_interval_in_sec)

            if transfer.terminated or transfer.block_number != Transfer.NONE:
                return
            current_attempt = f'{attempt + 1}/{self.retransmit_attempt_count}'
            logger.debug(f'Re-write request. Attempt: {current_attempt} for peer: {transfer.peer}')
            self.send_write_request(transfer)

    def _is_simultaneously_served_transfers_limit_exceeded(self) -> bool:
        transfers_count = len(self.incoming) + len(self.outgoing)
        return transfers_count >= self.max_simultaneous_transfers
