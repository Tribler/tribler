# EVA protocol: a protocol for transferring big binary data over ipv8.
#
# Limitations and other useful information described in the corresponding class.
# Example of use:
#
# class MyCommunity(EVAProtocolMixin, Community):
#     community_id = os.urandom(20)
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.eva_init()
#
#         self.eva_register_receive_callback(self.on_receive)
#         self.eva_register_send_complete_callback(self.on_send_complete)
#         self.eva_register_error_callback(self.on_error)
#
#     def my_function(self, peer):
#         self.eva_send_binary(peer, b'info1', b'data1')
#         self.eva_send_binary(peer, b'info2', b'data2')
#         self.eva_send_binary(peer, b'info3', b'data3')
#
#     def on_receive(self, peer, binary_info, binary_data, nonce):
#         logger.info(f'Data has been received: {binary_info}')
#
#     def on_send_complete(self, peer, binary_info, binary_data, nonce):
#         logger.info(f'Transfer has been completed: {binary_info}')
#
#     def on_error(self, peer, exception):
#         logger.error(f'Error has been occurred: {exception}')

import logging
import math
import time
from collections import defaultdict, deque
from enum import Enum, auto
from random import randint
from types import SimpleNamespace
from typing import Dict, Optional

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.types import Peer

logger = logging.getLogger('EVA')

MAX_U64 = 0xFFFFFFFF


# fmt: off

@vp_compile
class WriteRequest(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['data_size', 'nonce', 'info_binary']


@vp_compile
class Acknowledgement(VariablePayload):
    format_list = ['I', 'I', 'I']
    names = ['number', 'window_size', 'nonce']


@vp_compile
class Data(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['block_number', 'nonce', 'data_binary']


@vp_compile
class Error(VariablePayload):
    format_list = ['raw']
    names = ['message']


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

    def eva_init(  # pylint: disable=too-many-arguments
            self,
            block_size=1000,
            window_size_in_blocks=16,
            start_message_id=186,
            retransmit_interval_in_sec=3,
            retransmit_attempt_count=3,
            timeout_interval_in_sec=10,
            binary_size_limit=1024 * 1024 * 1024,
            terminate_by_timeout_enabled=True
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
        """
        self.last_message_id = start_message_id
        self.eva_messages = dict()

        self.eva_protocol = EVAProtocol(
            community=self,
            block_size=block_size,
            window_size_in_blocks=window_size_in_blocks,
            retransmit_interval_in_sec=retransmit_interval_in_sec,
            retransmit_attempt_count=retransmit_attempt_count,
            scheduled_send_interval_in_sec=5,
            timeout_interval_in_sec=timeout_interval_in_sec,
            binary_size_limit=binary_size_limit,
            terminate_by_timeout_enabled=terminate_by_timeout_enabled,
        )

        # note:
        # The order in which _eva_register_message_handler is called defines
        # the message wire format. Do not change it.
        self._eva_register_message_handler(WriteRequest, self.on_eva_write_request)
        self._eva_register_message_handler(Acknowledgement, self.on_eva_acknowledgement)
        self._eva_register_message_handler(Data, self.on_eva_data)
        self._eva_register_message_handler(Error, self.on_eva_error)

    def eva_send_binary(self, peer, info_binary, data_binary, nonce=None):
        """Send a big binary data.

        Due to ipv8 specifics, we can use only one socket port per one peer.
        Therefore, at one point in time, the protocol can only transmit one particular
        piece of data for one particular peer.

        In case "eva_send_binary" is invoked multiply times for a single peer, the data
        transfer will be scheduled and performed when the current sending session is finished.

        An example:

        self.eva_send_binary(peer, b'binary_data0', b'binary_info0')
        self.eva_send_binary(peer, b'binary_data1', b'binary_info1')
        self.eva_send_binary(peer, b'binary_data2', b'binary_info2')

        Args:
            peer: the target peer
            info_binary: a binary info, limited by <block_size> bytes
            data_binary: binary data that will be sent to the target.
                It is limited by several GB, but the protocol is slow by design, so
                try to send less rather than more.
            nonce: a unique number for identifying the session. If not specified, generated randomly
        """
        self.eva_protocol.send_binary(peer, info_binary, data_binary, nonce)

    def eva_register_receive_callback(self, callback):
        """Register callback that will be invoked when a data receiving is complete.

        An example:

        def on_receive(peer, info, data, nonce):
            pass

        self.eva_register_receive_callback(on_receive)
        """
        self.eva_protocol.receive_callbacks.add(callback)

    def eva_register_send_complete_callback(self, callback):
        """Register callback that will be invoked when a data sending is complete.

        An example:

        def on_send_complete(peer, info, data, nonce):
            pass

        self.eva_register_send_complete_callback(on_receive)
        """
        self.eva_protocol.send_complete_callbacks.add(callback)

    def eva_register_error_callback(self, callback):
        """Register callback that will be invoked in case of an error.

        An example:

        def on_error(self, peer, exception):
            pass

        self.eva_register_error_callback(on_error)
        """
        self.eva_protocol.error_callbacks.add(callback)

    def eva_send_message(self, peer, message):
        self.endpoint.send(peer.address, self.ezr_pack(self.eva_messages[type(message)], message))

    @lazy_wrapper(WriteRequest)
    async def on_eva_write_request(self, peer, payload):
        await self.eva_protocol.on_write_request(peer, payload)

    @lazy_wrapper(Acknowledgement)
    async def on_eva_acknowledgement(self, peer, payload):
        await self.eva_protocol.on_acknowledgement(peer, payload)

    @lazy_wrapper(Data)
    async def on_eva_data(self, peer, payload):
        await self.eva_protocol.on_data(peer, payload)

    @lazy_wrapper(Error)
    async def on_eva_error(self, peer, payload):
        await self.eva_protocol.on_error(peer, payload)

    def _eva_register_message_handler(self, message_class, handler):
        self.add_message_handler(self.last_message_id, handler)
        self.eva_messages[message_class] = self.last_message_id
        self.last_message_id += 1


class TransferType(Enum):
    INCOMING = auto()
    OUTGOING = auto()


class Transfer:  # pylint: disable=too-many-instance-attributes
    """The class describes an incoming or an outgoing transfer"""

    NONE = -1

    def __init__(self, transfer_type, info_binary, data_binary, nonce):
        self.type = transfer_type
        self.info_binary = info_binary
        self.data_binary = data_binary
        self.block_number = Transfer.NONE
        self.block_count = 0
        self.attempt = 0
        self.nonce = nonce
        self.window_size = 0
        self.acknowledgement_number = 0
        self.updated = time.time()
        self.released = False

    def release(self):
        self.info_binary = None
        self.data_binary = None
        self.released = True

    def __str__(self):
        return (
            f'Type: {self.type}. Info: {self.info_binary}. Block: {self.block_number}({self.block_count}). '
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
            terminate_by_timeout_enabled=True
    ):
        self.community = community

        self.scheduled = defaultdict(deque)
        self.block_size = block_size
        self.window_size = window_size_in_blocks
        self.retransmit_interval_in_sec = retransmit_interval_in_sec
        self.retransmit_attempt_count = retransmit_attempt_count
        self.timeout_interval_in_sec = timeout_interval_in_sec
        self.scheduled_send_interval_in_sec = scheduled_send_interval_in_sec
        self.binary_size_limit = binary_size_limit

        self.send_complete_callbacks = set()
        self.receive_callbacks = set()
        self.error_callbacks = set()

        self.incoming: Dict[Peer, Transfer] = dict()
        self.outgoing: Dict[Peer, Transfer] = dict()

        self.retransmit_enabled = True
        self.terminate_by_timeout_enabled = terminate_by_timeout_enabled

        # register tasks
        community.register_task('scheduled send', self.send_scheduled, interval=scheduled_send_interval_in_sec)

        logger.debug(
            f'Initialized. Block size: {block_size}. Window size: {window_size_in_blocks}. '
            f'Start message id: {start_message_id}. Retransmit interval: {retransmit_interval_in_sec}sec. '
            f'Max retransmit attempts: {retransmit_attempt_count}. Timeout: {timeout_interval_in_sec}sec. '
            f'Scheduled send interval: {scheduled_send_interval_in_sec}sec. '
            f'Binary size limit: {binary_size_limit}.'
        )

    def send_binary(self, peer, info_binary, data_binary, nonce=None):
        if not data_binary:
            return

        if peer == self.community.my_peer:
            return

        if nonce is None:
            nonce = randint(0, MAX_U64)

        if peer in self.outgoing:
            scheduled_transfer = SimpleNamespace(info_binary=info_binary, data_binary=data_binary, nonce=nonce)
            self.scheduled[peer].append(scheduled_transfer)
            return

        self.start_outgoing_transfer(peer, info_binary, data_binary, nonce)

    def start_outgoing_transfer(self, peer, info_binary, data_binary, nonce):
        transfer = Transfer(TransferType.OUTGOING, info_binary, b'', nonce)

        data_size = len(data_binary)
        if data_size > self.binary_size_limit:
            message = f'Current data size limit({self.binary_size_limit}) has been exceeded'
            self._notify_error(peer, SizeException(message, transfer))
            return

        transfer.block_count = math.ceil(data_size / self.block_size)
        transfer.data_binary = data_binary

        self.outgoing[peer] = transfer

        self._schedule_terminate(self.outgoing, peer, transfer)

        logger.debug(f'Write Request. Peer hash: {hash(peer)}. Transfer: {transfer}')
        self.community.eva_send_message(peer, WriteRequest(data_size, nonce, info_binary))

    async def on_write_request(self, peer: Peer, payload: WriteRequest):
        logger.debug(f'On write request. Peer hash: {hash(peer)}. Info: {payload.info_binary}. '
                     f'Size: {payload.data_size}')

        if payload.data_size <= 0:
            self._incoming_error(peer, None, ValueException('Data size can not be less or equal to 0'))
            return

        transfer = Transfer(TransferType.INCOMING, payload.info_binary, b'', payload.nonce)
        transfer.window_size = self.window_size
        transfer.attempt = 0

        if payload.data_size > self.binary_size_limit:
            e = SizeException(f'Current data size limit({self.binary_size_limit}) has been exceeded', transfer)
            self._incoming_error(peer, transfer, e)
            return

        self.incoming[peer] = transfer

        self._schedule_terminate(self.incoming, peer, transfer)
        self._schedule_resend_acknowledge(peer, transfer)

        self.send_acknowledgement(peer, transfer)

    async def on_acknowledgement(self, peer: Peer, payload: Acknowledgement):
        logger.debug(f'On acknowledgement({payload.number}). Window size: {payload.window_size}. '
                     f'Peer hash: {hash(peer)}.')

        transfer = self.outgoing.get(peer, None)
        if not transfer:
            return

        can_be_handled = transfer.block_number <= payload.number
        if not can_be_handled or transfer.nonce != payload.nonce:
            return

        transfer.block_number = payload.number
        if transfer.block_number > transfer.block_count:
            self.finish_outgoing_transfer(peer, transfer)
            return

        transfer.window_size = max(self.MIN_WINDOWS_SIZE, min(payload.window_size, self.binary_size_limit))
        transfer.updated = time.time()

        for block_number in range(transfer.block_number, transfer.block_number + transfer.window_size):
            start_position = block_number * self.block_size
            stop_position = start_position + self.block_size
            data = transfer.data_binary[start_position:stop_position]
            logger.debug(f'Transmit({block_number}). Peer hash: {hash(peer)}.')
            self.community.eva_send_message(peer, Data(block_number, transfer.nonce, data))
            if len(data) == 0:
                break

    async def on_data(self, peer, payload):
        logger.debug(
            f'On data({payload.block_number}). Peer hash: {hash(peer)}. Data hash: {hash(payload.data_binary)}')
        transfer = self.incoming.get(peer, None)
        if not transfer:
            return

        can_be_handled = transfer.block_number == payload.block_number - 1
        if not can_be_handled or transfer.nonce != payload.nonce:
            return

        transfer.block_number = payload.block_number

        is_final_data_packet = len(payload.data_binary) == 0
        if is_final_data_packet:
            self.send_acknowledgement(peer, transfer)
            self.finish_incoming_transfer(peer, transfer)
            return

        data_size = len(transfer.data_binary) + len(payload.data_binary)
        if data_size > self.binary_size_limit:
            e = SizeException(f'Current data size limit({self.binary_size_limit}) has been exceeded', transfer)
            self._incoming_error(peer, transfer, e)
            return

        transfer.data_binary += payload.data_binary
        transfer.attempt = 0
        transfer.updated = time.time()

        time_to_acknowledge = transfer.acknowledgement_number + transfer.window_size <= transfer.block_number + 1
        if time_to_acknowledge:
            self.send_acknowledgement(peer, transfer)

    def send_acknowledgement(self, peer, transfer):
        transfer.acknowledgement_number = transfer.block_number + 1

        logger.debug(f'Acknowledgement ({transfer.acknowledgement_number}). Window size: {transfer.window_size}. '
                     f'Peer hash: {hash(peer)}')

        acknowledgement = Acknowledgement(transfer.acknowledgement_number, transfer.window_size, transfer.nonce)
        self.community.eva_send_message(peer, acknowledgement)

    async def on_error(self, peer, payload):
        message = payload.message.decode('utf-8')
        logger.debug(f'On error. Peer hash: {hash(peer)}. Message: "{message}"')
        transfer = self.outgoing.get(peer, None)
        if not transfer:
            return

        EVAProtocol.terminate(self.outgoing, peer, transfer)

        self._notify_error(peer, TransferException(message, transfer))
        self.send_scheduled()

    def finish_incoming_transfer(self, peer, transfer):
        data = transfer.data_binary
        info = transfer.info_binary
        nonce = transfer.nonce

        EVAProtocol.terminate(self.incoming, peer, transfer)

        for callback in self.receive_callbacks:
            callback(peer, info, data, nonce)

    def finish_outgoing_transfer(self, peer, transfer):
        data = transfer.data_binary
        info = transfer.info_binary
        nonce = transfer.nonce

        EVAProtocol.terminate(self.outgoing, peer, transfer)

        for callback in self.send_complete_callbacks:
            callback(peer, info, data, nonce)

        self.send_scheduled()

    def send_scheduled(self):
        logger.debug('Looking for scheduled transfers for send...')

        free_peers = [peer for peer in self.scheduled if peer not in self.outgoing]

        for peer in free_peers:
            if not self.scheduled[peer]:
                self.scheduled.pop(peer, None)
                continue

            transfer = self.scheduled[peer].popleft()

            logger.debug(f'Scheduled send: {transfer.info_binary}')
            self.start_outgoing_transfer(peer, transfer.info_binary, transfer.data_binary, transfer.nonce)

    @staticmethod
    def terminate(container, peer, transfer):
        logger.debug(f'Finish. Peer hash: {hash(peer)}. Transfer: {transfer}')

        transfer.release()
        container.pop(peer, None)

    def _incoming_error(self, peer: Peer, transfer: Optional[Transfer], e: TransferException):
        if transfer:
            self.terminate(self.incoming, peer, transfer)
        self.community.eva_send_message(peer, Error(e.message.encode('utf-8')))
        self._notify_error(peer, e)

    def _notify_error(self, peer, exception):
        logger.warning(f'Exception.Peer hash {hash(peer)}: "{exception}"')

        for callback in self.error_callbacks:
            callback(peer, exception)

    def _schedule_terminate(self, container, peer, transfer):
        if not self.terminate_by_timeout_enabled:
            return

        self.community.register_anonymous_task('eva_terminate_by_timeout', self._terminate_by_timout_task, container,
                                               peer, transfer, delay=self.timeout_interval_in_sec, )

    def _terminate_by_timout_task(self, container, peer, transfer):
        if transfer.released or not self.terminate_by_timeout_enabled:
            return

        timeout = self.timeout_interval_in_sec
        remaining_time = timeout - (time.time() - transfer.updated)

        if remaining_time > 0:
            self.community.register_anonymous_task('eva_terminate_by_timeout', self._terminate_by_timout_task,
                                                   container, peer, transfer, delay=remaining_time, )
            return

        EVAProtocol.terminate(container, peer, transfer)
        self._notify_error(peer, TimeoutException(f'Terminated by timeout. Timeout is: {timeout} sec', transfer))

    def _schedule_resend_acknowledge(self, peer, transfer):
        if not self.retransmit_enabled:
            return

        self.community.register_anonymous_task('eva_resend_acknowledge', self._resend_acknowledge_task,
                                               peer, transfer, delay=self.retransmit_interval_in_sec, )

    def _resend_acknowledge_task(self, peer, transfer):
        if transfer.released or not self.retransmit_enabled:
            return

        attempts_are_over = transfer.attempt >= self.retransmit_attempt_count
        if attempts_are_over:
            return

        resend_needed = time.time() - transfer.updated >= self.retransmit_interval_in_sec
        if resend_needed:
            transfer.acknowledgement_number = transfer.block_number + 1
            transfer.attempt += 1

            logger.debug(f'Re-acknowledgement({transfer.acknowledgement_number}). '
                         f'Attempt: {transfer.attempt + 1}/{self.retransmit_attempt_count} for peer: {hash(peer)}')

            self.send_acknowledgement(peer, transfer)

        self.community.register_anonymous_task('eva_resend_acknowledge', self._resend_acknowledge_task, peer,
                                               transfer, delay=self.retransmit_interval_in_sec, )
