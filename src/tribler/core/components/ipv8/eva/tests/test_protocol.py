import asyncio
import collections
import logging
import os
import random
from asyncio import AbstractEventLoop
from collections import defaultdict
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from ipv8.community import Community
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.test.base import TestBase
from ipv8.types import Peer

from tribler.core.components.ipv8.eva.exceptions import SizeException, TimeoutException, TransferException, \
    TransferLimitException, ValueException
from tribler.core.components.ipv8.eva.protocol import Acknowledgement, Data, EVAProtocol, Error, TransferResult, \
    WriteRequest
from tribler.core.components.ipv8.eva.transfer.outgoing_transfer import OutgoingTransfer

# pylint: disable=redefined-outer-name, protected-access, attribute-defined-outside-init


TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC = 0.2
TEST_DEFAULT_RETRANSMIT_INTERVAL_IN_SEC = 0.1
TEST_DEFAULT_SEGMENT_SIZE = 1200
TEST_START_MESSAGE_ID = 100


async def drain_loop(loop: AbstractEventLoop):
    """Cool asyncio magic brewed by Vadim"""
    while True:
        if not loop._ready or not loop._scheduled:  # pylint: disable=protected-access
            break
        await asyncio.sleep(0)


class MockCommunity(Community):  # pylint: disable=too-many-ancestors
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

        self.eva = EVAProtocol(self, timeout_interval_in_sec=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC,
                               retransmit_interval_in_sec=TEST_DEFAULT_RETRANSMIT_INTERVAL_IN_SEC,
                               start_message_id=TEST_START_MESSAGE_ID,
                               terminate_by_timeout_enabled=False,  # by default disable the termination
                               on_receive=self.on_receive, on_send_complete=self.on_send_complete,
                               on_error=self.on_error)

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


class TestEVA(TestBase):
    def setUp(self):
        super().setUp()
        self.initialize(MockCommunity, 3)

        self.test_store = SimpleNamespace()

    @property
    def alice(self) -> MockCommunity:
        return self.overlay(0)

    @property
    def bob(self) -> MockCommunity:
        return self.overlay(1)

    @property
    def carol(self) -> MockCommunity:
        return self.overlay(2)

    async def send_sequence_from_alice_to_bob(self, *sequence: VariablePayload):
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
            data = (b'info', os.urandom(self.alice.eva.block_size * blocks_count))
            self.bob.eva.window_size = window_size
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
        self.alice.block_size = 2
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
        self.alice.eva.terminate_by_timeout_enabled = True
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

        self.bob.eva.terminate_by_timeout_enabled = True
        self.bob.eva.retransmit_interval_in_sec = 0

        await self.bob.eva.on_write_request_packet(self.alice.my_peer, WriteRequest(4, 1, b'info'))

        transfer = self.bob.eva.incoming[self.alice.my_peer]

        await self.bob.error_has_been_raised.wait()

        assert isinstance(self.bob.most_recent_received_exception, TimeoutException)
        assert transfer.attempt == self.bob.eva.retransmit_attempt_count

    async def test_retransmit_disabled(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will not answer the Bob in this test.
        # Therefore, Bob should accomplish `0` attempts of
        # re-sending Acknowledgement to Alice and ends up with TimeoutException
        # exception.

        self.bob.eva.retransmit_enabled = False
        self.bob.eva.terminate_by_timeout_enabled = True
        self.bob.eva.retransmit_interval_in_sec = 0

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
        self.bob.eva.binary_size_limit = 4
        with pytest.raises(TransferException):
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'12345')

        # Second, try to exceed size limit on a sender (alice) side.
        self.alice.eva.binary_size_limit = 4
        with pytest.raises(SizeException):
            await self.alice.eva.send_binary(self.bob.my_peer, b'info', b'12345')

    async def test_duplex_transfer(self):
        # In this test we send a single transfer from Alice to Bob and `1 transfer
        # from Bob to Alice at the same time.

        block_count = 100
        block_size = 10

        self.alice.eva.block_size = block_size
        self.bob.eva.block_size = block_size

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
        assert len(self.alice.eva.scheduled[self.bob.my_peer]) == data_set_count - 1

        await drain_loop(asyncio.get_event_loop())  # wait for transfer's complete

        for future in futures:
            assert future.done()

        assert self.bob.received_data[self.alice.my_peer] == alice_data_list
        assert not self.alice.eva.scheduled

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

        self.bob.eva.retransmit_attempt_count = lost_packets_count_estimation
        self.alice.eva.retransmit_interval_in_sec = 1
        self.bob.eva.retransmit_interval_in_sec = 0.1

        for participant in [self.alice, self.bob]:
            participant.eva.block_size = 3
            participant.eva.window_size = 10

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

        self.alice.eva.retransmit_interval_in_sec = 0
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

        self.alice.eva.block_size = block_size
        self.bob.eva.window_size = 1

        data = os.urandom(1), os.urandom(block_size * blocks_count)

        bob_send_message = self.bob.eva.send_message

        def wrapped_send_message(peer: Peer, message: VariablePayload):
            self.bob.eva.window_size += 1
            bob_send_message(peer, message)

        self.bob.eva.send_message = wrapped_send_message

        await self.alice.eva.send_binary(self.bob.my_peer, *data)
        assert self.bob.received_data[self.alice.my_peer][0] == data
        assert self.bob.eva.window_size > 1

    async def test_cheating_send_over_size(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send b`extra` binary data over the original size.

        self.bob.eva.binary_size_limit = 5
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

        self.bob.eva.block_size = 2
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

        self.bob.eva.block_size = 2

        await self.send_sequence_from_alice_to_bob(
            WriteRequest(4, 1, b'info'),
            Data(0, 1, b'da'),
            Data(1, 43, b'xx'),  # should be dropped
            Data(1, 1, b'ta'),
            Data(2, 1, b''),
        )

        assert self.bob.most_recent_received_data == (b'info', b'data')

    async def test_received_packet_that_have_no_transfer(self):
        # In this test we send a single transfer from Alice to Bob.
        # Alice will try to send packets without requesting WriteRequest

        await self.send_sequence_from_alice_to_bob(
            Data(0, 1, b'da'),
            Acknowledgement(0, 1, 0),
        )

        assert not self.alice.most_recent_received_exception
        assert not self.bob.most_recent_received_exception


@pytest.fixture
def eva():
    protocol = EVAProtocol(Mock())
    yield protocol
    protocol.shutdown()


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


def test_is_simultaneously_served_transfers_limit_exceeded(eva: EVAProtocol):
    # In this test we will try to exceed `max_simultaneous_transfers` limit.
    eva.max_simultaneous_transfers = 3

    assert not eva._is_simultaneously_served_transfers_limit_exceeded()

    eva.incoming['peer1'] = Mock()
    eva.outgoing['peer2'] = Mock()

    assert not eva._is_simultaneously_served_transfers_limit_exceeded()

    eva.outgoing['peer3'] = Mock()
    assert eva._is_simultaneously_served_transfers_limit_exceeded()


async def test_send_binary_with_transfers_limit(eva: EVAProtocol):
    # Test that in case `max_simultaneous_transfers` limit exceeded, call of
    # `send_binary` function will lead to schedule a transfer
    eva.max_simultaneous_transfers = 2
    assert eva.send_binary(peer=Mock(), info=b'info', data=b'data')
    assert not eva.scheduled

    assert eva.send_binary(peer=Mock(), info=b'info', data=b'data')
    assert not eva.scheduled

    assert eva.send_binary(peer=Mock(), info=b'info', data=b'data')
    assert eva._is_simultaneously_served_transfers_limit_exceeded()
    assert eva.scheduled


async def test_on_write_request_with_transfers_limit(eva: EVAProtocol):
    # Test that in case of exceeded incoming transfers limit, TransferLimitException
    # will be returned
    eva.max_simultaneous_transfers = 1
    eva._finish_with_error = Mock()

    await eva.on_write_request_packet(Mock(), WriteRequest(10, 0, b''))
    eva._finish_with_error.assert_not_called()

    await eva.on_write_request_packet(Mock(), WriteRequest(10, 0, b''))
    actual_exception = eva._finish_with_error.call_args[0][-1]
    assert isinstance(actual_exception, TransferLimitException)


def test_send_scheduled_with_transfers_limit(eva: EVAProtocol):
    # Test that `max_simultaneous_transfers` limit uses during `send_scheduled`
    eva.max_simultaneous_transfers = 2
    eva.scheduled['peer1'] = collections.deque([Mock()])
    eva.scheduled['peer2'] = collections.deque([Mock()])
    eva.scheduled['peer3'] = collections.deque([Mock()])
    eva.send_scheduled()

    assert len(eva.scheduled['peer1']) == 0
    assert len(eva.scheduled['peer2']) == 0
    assert len(eva.scheduled['peer3']) == 1


def test_send_write_request_finished_transfer(eva: EVAProtocol):
    transfer = OutgoingTransfer(protocol=eva, peer=Mock(), info=b'123', data=b'456', nonce=42)
    transfer.finished = True
    assert not eva.send_write_request(transfer)


async def test_on_error_correct_nonce(eva: EVAProtocol):
    # In this test we call `eva.on_error` and ensure that the corresponding transfer
    # is terminated
    peer = Mock()
    nonce = 1
    transfer = Mock(nonce=nonce)
    eva.outgoing[peer] = transfer

    await eva.on_error_packet(peer, Error(nonce, b'error'))

    assert isinstance(transfer.finish.call_args.kwargs['exception'], TransferException)


async def test_on_error_wrong_nonce(eva: EVAProtocol):
    # In this test we call `eva.on_error` with incorrect nonce and ensure that
    # the corresponding transfer is not terminated
    peer = Mock()
    nonce = 1
    transfer = Mock(nonce=nonce)
    eva.outgoing[peer] = transfer

    await eva.on_error_packet(peer, Error(nonce + 1, b'error'))

    transfer.terminate.assert_not_called()


def test_shutdown(eva: EVAProtocol):
    # Test that for all transfers will be called terminate in the case of a 'shutdown'
    transfer1 = Mock()
    transfer2 = Mock()
    transfer3 = Mock()

    eva.incoming['peer1'] = transfer1
    eva.incoming['peer2'] = transfer2

    eva.outgoing['peer3'] = transfer3

    eva.shutdown()

    for t in [transfer1, transfer2, transfer3]:
        assert isinstance(t.finish.call_args.kwargs['exception'], TransferException)




