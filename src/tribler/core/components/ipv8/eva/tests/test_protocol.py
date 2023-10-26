import asyncio
import logging
import os
import random
from asyncio import AbstractEventLoop
from collections import defaultdict
from copy import deepcopy
from itertools import permutations
from types import SimpleNamespace
from typing import Type
from unittest.mock import Mock, patch

import pytest
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.types import Peer
from tribler.core.components.ipv8.adapters_tests import TriblerTestBase

from tribler.core.components.ipv8.eva.exceptions import RequestRejected, SizeException, TimeoutException, \
    TransferCancelledException, TransferException, \
    TransferLimitException, ValueException
from tribler.core.components.ipv8.eva.payload import Acknowledgement, Data, Error, WriteRequest
from tribler.core.components.ipv8.eva.protocol import EVAProtocol
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.eva.settings import EVASettings, Retransmission, Termination
from tribler.core.components.ipv8.tribler_community import TriblerCommunity

# pylint: disable=redefined-outer-name, protected-access, attribute-defined-outside-init

default_settings = EVASettings(
    termination=Termination(
        enabled=False,
        timeout=0.2
    ),
    retransmission=Retransmission(
        interval=0.1
    )
)


async def drain_loop(loop: AbstractEventLoop):
    """Cool asyncio magic brewed by Vadim"""
    while True:
        if not loop._ready or not loop._scheduled:  # pylint: disable=protected-access
            break
        await asyncio.sleep(0)


class MockCommunity(TriblerCommunity):  # pylint: disable=too-many-ancestors
    community_id = os.urandom(20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_data = defaultdict(lambda: [])
        self.sent_data = defaultdict(lambda: [])

        self.data_has_been_sent = asyncio.Event()
        self.error_has_been_raised = asyncio.Event()

        self.most_recent_received_data = None
        self.most_recent_received_exception = None
        self.most_recent_sent_data = None

        self.eva = EVAProtocol(
            community=self,
            settings=deepcopy(default_settings),
            start_message_id=100,
            on_receive=self.on_receive,
            on_send_complete=self.on_send_complete,
            on_error=self.on_error
        )

    async def on_receive(self, result: TransferResult):
        self.most_recent_received_data = result.info, result.data
        self.received_data[result.peer].append(self.most_recent_received_data)

    async def on_send_complete(self, result: TransferResult):
        self.most_recent_sent_data = result.info, result.data
        self.sent_data[result.peer].append(self.most_recent_sent_data)
        self.data_has_been_sent.set()

    async def on_error(self, _, exception):
        self.most_recent_received_exception = exception
        self.error_has_been_raised.set()


class TestEVA(TriblerTestBase):
    def setUp(self):
        super().setUp()
        self.initialize(MockCommunity, 3)

        self.test_store = SimpleNamespace()

    async def tearDown(self):
        await asyncio.wait([asyncio.create_task(node.overlay.eva.shutdown()) for node in self.nodes])
        await super().tearDown()

    @property
    def alice(self) -> MockCommunity:
        return self.overlay(0)

    @property
    def bob(self) -> MockCommunity:
        return self.overlay(1)

    @property
    def carol(self) -> MockCommunity:
        return self.overlay(2)

    async def send_sequence_from_alice_to_bob(self, *sequence: Type[VariablePayload]):
        for message in sequence:
            self.alice.eva.send_message(self.bob.my_peer, message)
            await drain_loop(asyncio.get_event_loop())

    async def test_one_block_binary(self):
        # In this test we send a single transfer from Alice to Bob.
        # The transfer size is less than and `block_size` and therefore it
        # could be send as a single packet.
        data = (b'test1', b'1234')

        await self.alice.eva.send_binary(self.bob.my_peer, *data)

        assert self.bob.most_recent_received_data == data

        await self.alice.data_has_been_sent.wait()
        assert self.alice.most_recent_sent_data == data

    async def test_cancel_send_binary(self):
        future = self.alice.eva.send_binary(self.bob.my_peer, b'test1', b'1234')
        transfer = self.alice.eva.outgoing[self.bob.my_peer]

        future.cancel()
        await self.alice.error_has_been_raised.wait()

        assert isinstance(self.alice.most_recent_received_exception, TransferCancelledException)
        assert transfer.finished
        assert not self.alice.eva.outgoing

    async def test_get_binary(self):
        # In this test we request binary from Bob to Alice
        async def on_request(peer: Peer, info: bytes):
            response = {
                b'0': b'zero',
                b'1': b'one',
                b'2': b'two',
            }
            return response[info]

        self.bob.eva.on_request = on_request

        result = await self.alice.eva.get_binary(self.bob.my_peer, b'1')
        assert result.data == b'one'

    async def test_get_binary_self_send(self):
        # In this test we request binary from Alice to Alice.
        # It should lead to `ValueException`
        with pytest.raises(ValueException):
            await self.alice.eva.get_binary(self.alice.my_peer, b'1')

    async def test_get_binary_rejected(self):
        # In this test we request binary from Bob to Alice.
        # But Bob's `on_request` is not defined.
        # It should lead to `RequestRejected` error.
        with pytest.raises(RequestRejected) as exception:
            await self.alice.eva.get_binary(self.bob.my_peer, b'give me an error')
        assert exception.value.remote

        assert type(self.bob.most_recent_received_exception) == RequestRejected  # pylint: disable=unidiomatic-typecheck
        assert not self.bob.most_recent_received_exception.remote

    async def test_block_count_fits_a_single_window(self):
        # In this test we send three transfers from Alice to Bob to ensure that
        # protocol works well in the case of all blocks roughly fits just a single window.
        #
        # In this test three datasets are used:
        # 1:    data:   |XXXXXXXXX_|
        #       window: |__________|
        #
        # 2:    data:   |XXXXXXXXXX|
        #       window: |__________|
        #
        # 3:    data:   |XXXXXXXXXX|X
        #       window: |__________|
        window_size = 10
        for blocks_count in [window_size - 1, window_size, window_size + 1]:
            data = (b'info', os.urandom(self.alice.eva.settings.block_size * blocks_count))
            self.bob.eva.settings.window_size = window_size
            await self.alice.eva.send_binary(self.bob.my_peer, *data)
            assert self.bob.most_recent_received_data == data

    async def test_self_send(self):
        # In this test we send a single transfer from Alice to Alice.
        # `ValueException` should be raised.
        with pytest.raises(ValueException):
            await self.alice.eva.send_binary(self.alice.my_peer, b'test1', b'1234')

    async def test_two_blocks_binary(self):
        # In this test we send a single transfer from Alice to Bob.
        # The transfer size is equal to and `block_size * 2` and therefore it
        # could be send as a two packets.
        data = b'test2', b'4321'
        self.alice.eva.settings.block_size = 2
        await self.alice.eva.send_binary(self.bob.my_peer, *data)
        assert self.bob.most_recent_received_data == data

        await self.alice.data_has_been_sent.wait()
        assert self.alice.most_recent_sent_data == data

    async def test_zero_transfer(self):
        # In this test we send a single transfer from Alice to Bob.
        # The transfer size is equal to zero and the transfer attempt should
        # lead to `ValueException`.
        with pytest.raises(ValueException):
            await self.alice.eva.send_binary(self.bob.my_peer, b'', b'')

    async def test_one_megabyte_transfer(self):
        # In this test we send `1Mb` transfer from Alice to Bob.
        data_size = 1024 * 1024
        data = os.urandom(1), os.urandom(data_size)

        await self.alice.eva.send_binary(self.bob.my_peer, *data)

        assert self.bob.most_recent_received_data == data

        await self.alice.data_has_been_sent.wait()
        assert self.alice.most_recent_sent_data == data

    async def test_termination_by_timeout(self):
        # In this test we send a single transfer from Alice to Bob.
        # To invoke a termination by timeout we should do the following:
        # On Bob's instance we should replace `send_message` function by Mock().
        #
        # After a failed sending attempt from Alice to Bob we should see that Alice's
        # instance had terminated its transfer by timeout.
        self.alice.eva.settings.termination.enabled = True
        self.alice.eva.send_message = Mock()

        with pytest.raises(TimeoutException):
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'data')

        assert len(self.alice.eva.outgoing) == 0
        assert len(self.bob.eva.incoming) == 0

    async def test_retransmit_enabled(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will not answer the Bob in this test.
        # Therefore, Bob should accomplish `retransmit_attempt_count` attempts of
        # re-sending Acknowledgement to Alice and ends up with TimeoutException
        # exception.

        self.bob.eva.settings.termination.enabled = True
        self.bob.eva.settings.retransmission.interval = 0

        await self.bob.eva.on_write_request_packet(self.alice.my_peer, WriteRequest(4, 1, b'info'))

        transfer = self.bob.eva.incoming[self.alice.my_peer]

        await self.bob.error_has_been_raised.wait()

        assert isinstance(self.bob.most_recent_received_exception, TimeoutException)
        assert transfer.attempt == 0

    async def test_size_limit(self):
        # In this test we send a single transfer from Alice to Bob.
        # TransferException and SizeException should be raised in the case of
        # exceeded binary size limit.

        # First, try to exceed size limit on a receiver (bob) side.
        self.bob.eva.settings.binary_size_limit = 4
        with pytest.raises(SizeException) as exception:
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'12345')
        assert exception.value.remote

        # Second, try to exceed size limit on a sender (alice) side.
        self.alice.eva.settings.binary_size_limit = 4
        with pytest.raises(SizeException) as exception:
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'12345')
        assert not exception.value.remote

    async def test_duplex_transfer(self):
        # In this test we send a single transfer from Alice to Bob and `1 transfer
        # from Bob to Alice at the same time.

        block_count = 100
        block_size = 10

        self.alice.eva.settings.block_size = block_size
        self.bob.eva.settings.block_size = block_size

        alice_data = os.urandom(1), os.urandom(block_size * block_count)
        bob_data = os.urandom(1), os.urandom(block_size * block_count)

        alice_feature = self.alice.eva.send_binary(self.bob.my_peer, *alice_data)
        bob_feature = self.bob.eva.send_binary(self.alice.my_peer, *bob_data)

        await drain_loop(asyncio.get_event_loop())

        assert alice_feature.done()
        assert bob_feature.done()
        assert self.alice.most_recent_received_data == bob_data
        assert self.bob.most_recent_received_data == alice_data

        assert not self.alice.eva.incoming
        assert not self.alice.eva.outgoing
        assert not self.bob.eva.incoming
        assert not self.bob.eva.outgoing

    async def test_scheduled_send(self):
        # In this test we will send `10` transfers from Alice to Bob
        # at the same time.
        # `9` transfers should be scheduled by Alice and then sent one by one to Bob.

        data_set_count = 10
        data_size = 1024

        alice_data_list = [(os.urandom(1), os.urandom(data_size)) for _ in range(data_set_count)]
        futures = []
        for data in alice_data_list:
            futures.append(self.alice.eva.send_binary(self.bob.my_peer, *data))
        assert len(self.alice.eva.scheduler.scheduled) == data_set_count - 1

        await drain_loop(asyncio.get_event_loop())  # wait for transfer's complete

        for future in futures:
            assert future.done()

        assert self.bob.received_data[self.alice.my_peer] == alice_data_list
        assert not self.alice.eva.scheduler.scheduled

    async def test_multiply_duplex(self):
        # In this test we will send `5` transfers in the following directions
        # at the same time:

        # Alice->Bob
        # Alice->Carol

        # Bob->Alice
        # Bob->Carol

        # Carol->Alice
        # Carol->Bob

        data_set_count = 5

        # create 10 different data sets for each direction (0->1, 0->2, 1->0, 1->2, 2->0, 2->1)
        participants = [
            (self.alice.my_peer, self.alice),
            (self.bob.my_peer, self.bob),
            (self.carol.my_peer, self.carol),
        ]

        for _, community in participants:
            community.eva.block_size = 10

        data = [
            (p, list((os.urandom(1), os.urandom(50)) for _ in range(data_set_count)))
            for p in permutations(participants, 2)
        ]

        futures = []
        for ((_, community), (peer, _)), data_set in data:
            for d in data_set:
                futures.append(community.eva.send_binary(peer, *d))

        await drain_loop(asyncio.get_event_loop())

        for _, community in participants:
            assert len(community.received_data) == 2

        data_sets_checked = 0
        for ((peer, _), (_, community)), data_set in data:
            assert community.received_data[peer] == data_set
            data_sets_checked += 1

        assert data_sets_checked == len(data)

    async def test_survive_when_multiply_packets_lost(self):
        # In this test we send `3` transfers from Alice to Bob.
        # On bob's side we replace `on_data` function by `fake_on_data` in
        # which some packets will be ignored (dropped).
        # The EVA protocol should handle this situation by retransmitting
        # dropped packets.
        lost_packets_count_estimation = 5
        data_set_count = 3

        block_count = 15
        block_size = 3

        packet_loss_probability = lost_packets_count_estimation / (block_count * data_set_count)

        self.bob.eva.settings.retransmission.attempts = lost_packets_count_estimation
        self.alice.eva.settings.retransmission.interval = 1
        self.bob.eva.settings.retransmission.interval = 0.1

        for participant in [self.alice, self.bob]:
            participant.eva.settings.block_size = 3
            participant.eva.settings.window_size = 10

        data = [(os.urandom(1), os.urandom(block_size * block_count)) for _ in range(data_set_count)]

        # a storage for the fake function
        self.test_store.actual_packets_lost = 0
        self.test_store.lost_packets_count_estimation = lost_packets_count_estimation
        self.test_store.packet_loss_probability = packet_loss_probability

        # modify "send_message" function to proxying all calls and to add a probability
        # to a packet loss
        alice_send_message = self.alice.eva.send_message

        def wrapped_send_message(peer: Peer, message: VariablePayload):
            if isinstance(message, Data):
                chance_to_fake = random.random() < self.test_store.packet_loss_probability
                max_count_reached = self.test_store.actual_packets_lost >= self.test_store.lost_packets_count_estimation
                if chance_to_fake and not max_count_reached:
                    self.test_store.actual_packets_lost += 1
                    logging.info(f'Lost packet ({message.number})')
                    return
            alice_send_message(peer, message)

        self.alice.eva.send_message = wrapped_send_message

        for d in data:
            await self.alice.eva.send_binary(self.bob.my_peer, *d)

        logging.info(f'Estimated packet lost block_count/probability: '
                     f'{lost_packets_count_estimation}/{packet_loss_probability}')
        logging.info(f'Actual packet lost: {self.test_store.actual_packets_lost}')
        assert self.bob.received_data[self.alice.my_peer] == data
        assert self.test_store.actual_packets_lost > 0

    async def test_write_request_packets_lost(self):
        # In this test we send a single transfer from Alice to Bob.
        # On Alice's side we replace `send_write_request` function by
        # `fake_send_write_request` in which first `2` packets will be dropped.
        # The EVA protocol should handle this situation by retransmitting
        # dropped packets.

        self.alice.eva.settings.retransmission.interval = 0
        self.packets_to_drop = 3

        # replace `EVAProtocol.send_message` method with `lossy_send_message`
        # that ignores (drops) first `lost_packet_count` messages
        alice_send_message = self.alice.eva.send_message

        def lossy_send_message(*args, **kwargs):
            if self.packets_to_drop:
                self.packets_to_drop -= 1
            else:
                alice_send_message(*args, **kwargs)

        self.alice.eva.send_message = lossy_send_message

        data = b'info', b'data'
        await self.alice.eva.send_binary(self.bob.my_peer, *data)

        assert self.bob.most_recent_received_data == data
        assert not self.packets_to_drop

    async def test_dynamically_changed_window_size(self):
        # In this test we send a single transfer from Alice to Bob with dynamically
        # changed windows size.

        block_size = 2
        blocks_count = 100

        self.alice.eva.settings.block_size = block_size
        self.bob.eva.settings.window_size = 1

        data = os.urandom(1), os.urandom(block_size * blocks_count)

        bob_send_message = self.bob.eva.send_message

        def wrapped_send_message(peer: Peer, message: VariablePayload):
            self.bob.eva.settings.window_size += 1
            bob_send_message(peer, message)

        self.bob.eva.send_message = wrapped_send_message

        await self.alice.eva.send_binary(self.bob.my_peer, *data)
        assert self.bob.received_data[self.alice.my_peer][0] == data
        assert self.bob.eva.settings.window_size > 1

    async def test_cheating_send_over_size(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send b`extra` binary data over the original size.

        self.bob.eva.settings.binary_size_limit = 5
        await self.send_sequence_from_alice_to_bob(
            WriteRequest(4, 1, b'info'),
            Data(0, 1, b'data'),
            Data(100, 1, b'extra'),  # over the window, should be ignored

            Data(1, 1, b''),
        )

        assert self.bob.most_recent_received_data == (b'info', b'data')

    async def test_wrong_message_order(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send packets in invalid order. These packets
        # should be delivered.

        self.bob.eva.settings.block_size = 2
        expected_data = b'ABCDEFJHI'
        await self.send_sequence_from_alice_to_bob(
            WriteRequest(len(expected_data), 1, b'info'),
            Data(0, 1, b'ABC'),
            Data(2, 1, b'JHI'),
            Data(1, 1, b'DEF'),

            Data(1, 1, b'xx'),  # should be ignored
            Data(2, 2, b'xx'),  # should be ignored

            Data(2, 1, b''),
        )

        assert self.bob.most_recent_received_data == (b'info', expected_data)

    async def test_wrong_message_order_and_wrong_nonce(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send packets with invalid nonce. These packets
        # should be dropped

        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send packets in invalid order. These packets
        # should be dropped

        self.bob.eva.settings.block_size = 2

        await self.send_sequence_from_alice_to_bob(
            WriteRequest(4, 1, b'info'),
            Data(0, 1, b'da'),
            Data(1, 43, b'xx'),  # should be dropped
            Data(1, 1, b'ta'),
            Data(2, 1, b''),
        )

        assert self.bob.most_recent_received_data == (b'info', b'data')

    async def test_send_binary_on_error(self):
        # In this test we try to send a single transfer from Alice to Bob.
        # On the Bob's side `_is_simultaneously_served_transfers_limit_exceeded` always return `True`
        # That is why Alice's attempt to sent any data to Bob will lead to `RequestRejected` exception.

        self.bob.eva._is_simultaneously_served_transfers_limit_exceeded = Mock(True)

        with pytest.raises(TransferLimitException) as exception:
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'data')
        assert exception.value.remote

        received_exception = self.bob.most_recent_received_exception
        assert type(received_exception) == TransferLimitException  # pylint: disable=unidiomatic-typecheck
        assert not received_exception.remote

    async def test_received_packet_that_have_no_transfer(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send packets without requesting WriteRequest

        await self.send_sequence_from_alice_to_bob(
            Data(0, 1, b'da'),
            Acknowledgement(0, 1, 0),
        )

        assert not self.alice.most_recent_received_exception
        assert not self.bob.most_recent_received_exception

    async def test_trim_on_error(self):
        # In this test we send a single transfer from Eva to Bob.
        # On Bob's size we set `binary_size_limit=100` to trigger `SizeException` error.
        # Also we set `block_size=15` in order to trim error message to 'Data s'
        self.bob.eva.settings.block_size = 15
        self.bob.eva.settings.binary_size_limit = 100
        with pytest.raises(SizeException) as exception:
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'0' * 101)

        assert str(exception.value) == 'Data s'


@pytest.fixture
async def eva():
    protocol = EVAProtocol(Mock())
    yield protocol
    await protocol.shutdown()


@pytest.fixture
def peer():
    return Mock()


async def test_on_write_request_data_size_le0(eva: EVAProtocol, peer):
    # validate that data_size can not be less or equal to 0
    with patch.object(EVAProtocol, '_finish_with_error') as method_mock:
        await eva.on_write_request_packet(peer, WriteRequest(0, 0, b''))
        await eva.on_write_request_packet(peer, WriteRequest(-1, 0, b''))
        assert peer not in eva.incoming
        assert method_mock.call_count == 2


async def test_on_write_request_with_transfers_limit(eva: EVAProtocol):
    # Test that in case of exceeded incoming transfers limit, TransferLimitException
    # will be returned
    eva.settings.max_simultaneous_transfers = 1
    eva._finish_with_error = Mock()

    await eva.on_write_request_packet(Mock(), WriteRequest(10, 0, b''))
    eva._finish_with_error.assert_not_called()

    await eva.on_write_request_packet(Mock(), WriteRequest(10, 0, b''))
    actual_exception = eva._finish_with_error.call_args[0][-1]
    assert isinstance(actual_exception, TransferLimitException)


async def test_on_error_correct_nonce(eva: EVAProtocol):
    # In this test we call `eva.on_error` and ensure that the corresponding transfer
    # is terminated
    peer = Mock()
    transfer = Mock(nonce=1)
    eva.outgoing[peer] = transfer

    await eva.on_error_packet(peer, Error(incoming=True, nonce=1, message=b'error', code=0))

    assert isinstance(transfer.finish.call_args.kwargs['exception'], TransferException)


async def test_on_error_wrong_nonce(eva: EVAProtocol):
    # In this test we call `eva.on_error` with incorrect nonce and ensure that
    # the corresponding transfer is not terminated
    peer = Mock()
    transfer = Mock(nonce=1)
    eva.outgoing[peer] = transfer

    await eva.on_error_packet(peer, Error(incoming=True, nonce=2, message=b'error', code=0))

    transfer.terminate.assert_not_called()


async def test_shutdown(eva: EVAProtocol):
    # Test that for all transfers will be called terminate in the case of a 'shutdown'
    transfer1 = Mock()
    transfer2 = Mock()
    transfer3 = Mock()

    eva.incoming['peer1'] = transfer1
    eva.incoming['peer2'] = transfer2

    eva.outgoing['peer3'] = transfer3

    await eva.shutdown()

    for t in [transfer1, transfer2, transfer3]:
        assert isinstance(t.finish.call_args.kwargs['exception'], TransferException)
