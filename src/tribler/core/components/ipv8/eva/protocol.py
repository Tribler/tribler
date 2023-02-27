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

import logging
from asyncio import Future
from functools import wraps
from itertools import chain
from random import SystemRandom
from typing import Awaitable, Callable, Dict, Optional, Type, TypeVar

from ipv8.community import Community
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.types import Peer

from tribler.core.components.ipv8.eva.aliases import TransferCompleteCallback, TransferErrorCallback, \
    TransferRequestCallback
from tribler.core.components.ipv8.eva.container import Container
from tribler.core.components.ipv8.eva.exceptions import RequestRejected, SizeException, TransferException, \
    TransferLimitException, \
    ValueException, to_class, to_code
from tribler.core.components.ipv8.eva.payload import Acknowledgement, Data, Error, ReadRequest, WriteRequest
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.scheduler import Scheduler
from tribler.core.components.ipv8.eva.settings import EVASettings
from tribler.core.components.ipv8.eva.transfer.base import Transfer
from tribler.core.components.ipv8.eva.transfer.incoming import IncomingTransfer
from tribler.core.components.ipv8.eva.transfer.outgoing import OutgoingTransfer
from tribler.core.components.ipv8.protocol_decorator import make_protocol_decorator
from tribler.core.utilities.async_group.async_group import AsyncGroup

__version__ = '2.2.0'

logger = logging.getLogger('EVA')

MAX_U32 = 0xFFFFFFFF

eva_packet_handler = make_protocol_decorator('eva')


def message_handler(packet_type):
    def eva_method_decorator(func):
        @eva_packet_handler(packet_type)
        @wraps(func)
        async def wrapped_func(self: EVAProtocol, peer: Peer, packet: VariablePayload):
            if self.shutting_down:
                return
            await func(self, peer, packet)

        return wrapped_func

    return eva_method_decorator


T = TypeVar('T', bound=Transfer)


async def blank(*_, **__):
    ...


class EVAProtocol:  # pylint: disable=too-many-instance-attributes
    """EVAProtocol makes it possible to transfer big binary data over ipv8.

        The protocol based on TFTP with window size (RFC 7440).
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
            on_request: Optional[TransferRequestCallback] = None,
            start_message_id: int = 186,
            settings: Optional[EVASettings] = None
    ):
        """Init should be called manually within his parent class.

        Args:
        """
        self.community = community

        self.settings = settings or EVASettings()

        self.on_send_complete = on_send_complete or blank
        self.on_receive = on_receive or blank
        self.on_error = on_error or blank
        self.on_request = on_request

        self.incoming: Container[Peer, IncomingTransfer] = Container(self)
        self.outgoing: Container[Peer, OutgoingTransfer] = Container(self)

        self.random = SystemRandom()
        self.scheduler = Scheduler(eva=self)
        self.task_group = AsyncGroup()
        self.shutting_down = False

        self.start_message_id = self.last_message_id = start_message_id
        self.eva_messages: Dict[Type[VariablePayload], int] = {}

        # note:
        # The order in which _eva_register_message_handler is called defines
        # the message wire format. Do not change it.
        self._register_message_handler(WriteRequest, self.on_write_request_packet)
        self._register_message_handler(Acknowledgement, self.on_acknowledgement_packet)
        self._register_message_handler(Data, self.on_data_packet)
        self._register_message_handler(Error, self.on_error_packet)
        self._register_message_handler(ReadRequest, self.on_read_request)

        logger.debug(f'Initialized. Settings: {self.settings}.')

    def _register_message_handler(self, message_class: Type[VariablePayload], handler: Callable):
        self.community.add_message_handler(self.last_message_id, handler)
        self.eva_messages[message_class] = self.last_message_id
        self.last_message_id += 1

    def send_binary(self, peer: Peer, info: bytes, data: bytes) -> Future[TransferResult]:
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
        if self.shutting_down:
            raise TransferException('The protocol is shutting down')

        if not data:
            raise ValueException('The empty data binary passed')

        if peer == self.community.my_peer:
            raise ValueException('The receiver can not be equal to the sender')

        nonce = self.random.randint(0, MAX_U32)
        data_size = len(data)
        if data_size > self.settings.binary_size_limit:
            raise SizeException(f'Data size limit {self.settings.binary_size_limit} has been exceeded: {data_size}')

        transfer = OutgoingTransfer(
            container=self.outgoing,
            peer=peer,
            info=info,
            data=data,
            data_size=data_size,
            nonce=nonce,
            settings=self.settings,
            protocol_task_group=self.task_group,
            send_message=self.send_message,
            on_complete=self.on_send_complete,
            on_error=self.on_error,
            request=WriteRequest(data_size, nonce, info)
        )

        return self.scheduler.schedule(transfer)

    def get_binary(self, peer: Peer, info: bytes) -> Awaitable[TransferResult]:
        """Receive a big binary data.

         Due to ipv8 specifics, we can use only one socket port per one peer.
         Therefore, at one point in time, the protocol can only transmit one particular
         piece of data for one particular peer.

         In case "get_binary" is invoked multiply times for a single peer, the data
         transfer will be scheduled and performed when the current sending session is finished.

         An example:
         >>> class MyCommunity(Community):
         ...     def __init__(self, *args, **kwargs):
         ...         super().__init__(*args, **kwargs)
         ...         self.eva = EVAProtocol(self)
         ...
         ...     async def my_function(self, peer):
         ...         result = await self.eva.get_binary(peer, b'id: 1')
         ...         print(result.data)

         Args:
             peer: the target peer
             info: a binary info, limited by <block_size> bytes
         """
        logger.debug(f'Get binary. Peer: {peer}. Info: {info}.')

        if self.shutting_down:
            raise TransferException('The protocol is shutting down')

        if peer == self.community.my_peer:
            raise ValueException('The receiver can not be equal to the sender')

        nonce = self.random.randint(0, MAX_U32)
        transfer = IncomingTransfer(
            container=self.incoming,
            peer=peer,
            info=info,
            nonce=nonce,
            settings=self.settings,
            protocol_task_group=self.task_group,
            send_message=self.send_message,
            on_complete=self.on_receive,
            on_error=self.on_error,
            data_size=0,
            request=ReadRequest(info=info, nonce=nonce)
        )

        return self.scheduler.schedule(transfer)

    def send_message(self, peer: Peer, message: VariablePayload):
        self.community.endpoint.send(peer.address, self.community.ezr_pack(self.eva_messages[type(message)], message))

    def check_transfer_correctness(self, transfer: Transfer) -> bool:
        exception = None
        if transfer.data_size <= 0:
            exception = ValueException('Data size can not be less or equal to 0', transfer)
        elif transfer.data_size > self.settings.binary_size_limit:
            exception = SizeException(f'Data size limit({self.settings.binary_size_limit}) has been exceeded', transfer)
        elif self._is_simultaneously_served_transfers_limit_exceeded():
            exception = TransferLimitException('Maximum simultaneous transfers limit exceeded')

        if exception:
            self._finish_with_error(transfer, exception)
            return False

        return True

    @message_handler(WriteRequest)
    async def on_write_request_packet(self, peer: Peer, payload: WriteRequest):
        logger.debug(f'On write request. Peer: {peer}. Info: {payload.info}. Size: {payload.data_size}')

        if peer in self.incoming:
            return

        transfer = IncomingTransfer(
            container=self.incoming,
            peer=peer,
            info=payload.info,
            nonce=payload.nonce,
            data_size=payload.data_size,
            settings=self.settings,
            protocol_task_group=self.task_group,
            send_message=self.send_message,
            on_complete=self.on_receive,
            on_error=self.on_error,
        )

        if self.check_transfer_correctness(transfer):
            transfer.start()

    @message_handler(ReadRequest)
    async def on_read_request(self, peer: Peer, payload: ReadRequest):
        logger.debug(f'On read request. Peer: {peer}. Info: {payload.info}.')
        if peer in self.outgoing:
            return

        data = b''
        exception = None
        if self.on_request:
            try:
                data = await self.on_request(peer, payload.info)
            except Exception as e:  # pylint: disable=broad-except
                exception = e
        else:
            exception = NotImplementedError('on_request callback is not defined')

        transfer = OutgoingTransfer(
            container=self.outgoing,
            peer=peer,
            info=payload.info,
            data=data,
            data_size=len(data),
            nonce=payload.nonce,
            settings=self.settings,
            protocol_task_group=self.task_group,
            send_message=self.send_message,
            on_complete=self.on_send_complete,
            on_error=self.on_error
        )

        if exception:
            message = f'{exception.__class__.__name__}: {exception}'
            logger.warning(f'Exception during data retrieval. {message}')
            self._finish_with_error(transfer, RequestRejected(message, transfer))
            return

        if self.check_transfer_correctness(transfer):
            transfer.start()

    @message_handler(Acknowledgement)
    async def on_acknowledgement_packet(self, peer: Peer, payload: Acknowledgement):
        logger.debug(f'On acknowledgement({payload.number}). Window size: {payload.window_size}. Peer: {peer}.')

        transfer = self._get_transfer(peer=peer, container=self.outgoing, nonce=payload.nonce)
        if not transfer:
            return

        data_list = list(transfer.on_acknowledgement(payload.number, payload.window_size))
        is_transfer_finished = not data_list
        if is_transfer_finished:
            transfer.finish(result=transfer.create_result())
            return

        for data in data_list:
            logger.debug(f'Transmit({data.number}). Peer: {peer}.')
            self.send_message(peer, data)

    @message_handler(Data)
    async def on_data_packet(self, peer, payload):
        logger.debug(f'On data({payload.number}). Peer: {peer}. Data hash: {hash(payload.data)}')
        transfer = self._get_transfer(peer=peer, container=self.incoming, nonce=payload.nonce)
        if not transfer:
            return

        window_index = payload.number - transfer.window.start
        # The packet can be handled if payload number within [window_start..window_start+window_size)
        can_be_handled = 0 <= window_index < len(transfer.window.blocks)
        if not can_be_handled:
            return

        acknowledgement = transfer.on_data(index=window_index, data=payload.data)
        if acknowledgement:
            self.send_message(transfer.peer, acknowledgement)

    @message_handler(Error)
    async def on_error_packet(self, peer: Peer, error: Error):
        message = error.message.decode('utf-8')
        logger.debug(f'On error. Peer: {peer}. Message: "{message}"')

        container = self.outgoing if error.incoming else self.incoming
        transfer = self._get_transfer(peer=peer, container=container, nonce=error.nonce)
        if transfer:
            exception_cls = to_class(error.code)
            transfer.finish(exception=exception_cls(message, transfer, remote=True))

    @staticmethod
    def _get_transfer(peer: Peer, container: Dict[Peer, T], nonce: int) -> Optional[T]:
        transfer = container.get(peer)
        if not transfer:
            logger.warning(f'No transfer found with peer {peer} associated with incoming acknowledgement.')
            return None

        if transfer.nonce != nonce:
            logger.warning(f'Cannot handle acknowledgement from peer {peer} - nonce mismatch.')
            return None

        return transfer

    async def shutdown(self):
        """This method terminates all current transfers"""
        logger.info('Shutting down...')
        self.shutting_down = True

        await self.scheduler.shutdown()

        transfers = list(chain(self.incoming.values(), self.outgoing.values()))
        exception = TransferException('Terminated due to shutdown')

        for transfer in transfers:
            transfer.finish(exception=exception)

        await self.task_group.wait()

        logger.info('Shutting down completed')

    def _finish_with_error(self, transfer: Transfer, exception: TransferException):
        message = str(exception).encode('utf-8')
        message_limit = self.settings.block_size - (1 + 4 + 4)  # bool+int+int
        message = message[:message_limit]
        error = Error(
            incoming=isinstance(transfer, IncomingTransfer),
            nonce=transfer.nonce,
            code=to_code(exception.__class__),
            message=message
        )
        self.send_message(transfer.peer, error)
        transfer.finish(exception=exception)

    def _is_simultaneously_served_transfers_limit_exceeded(self) -> bool:
        transfers_count = len(self.incoming) + len(self.outgoing)
        return transfers_count >= self.settings.max_simultaneous_transfers
