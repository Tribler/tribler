import asyncio
import logging
import os
import random
from collections import defaultdict
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ipv8.community import Community
from ipv8.test.base import TestBase

import pytest

from tribler_core.components.metadata_store.remote_query_community.eva_protocol import (
    Acknowledgement,
    EVAProtocol,
    EVAProtocolMixin,
    Error,
    SizeException,
    TimeoutException,
    Transfer,
    TransferException,
    TransferType,
    WriteRequest,
)

# fmt: off
# pylint: disable=redefined-outer-name

PYTEST_TIMEOUT_IN_SEC = 60

TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC = 0.2
TEST_DEFAULT_RETRANSMIT_INTERVAL_IN_SEC = 0.1
TEST_DEFAULT_SEGMENT_SIZE = 1200
TEST_START_MESSAGE_ID = 100


def create_transfer(block_count: int = 0, updated: int = 0) -> Transfer:
    transfer = Transfer(TransferType.INCOMING, b'', b'', 0)
    transfer.updated = updated
    transfer.block_count = block_count
    return transfer


async def drain_loop(loop):
    """Cool asyncio magic brewed by Vadim"""
    while True:
        if not loop._ready or not loop._scheduled:  # pylint: disable=protected-access
            break
        await asyncio.sleep(0)


class MockCommunity(EVAProtocolMixin, Community):  # pylint: disable=too-many-ancestors
    community_id = os.urandom(20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_data = defaultdict(lambda: [])
        self.sent_data = defaultdict(lambda: [])

        self.most_recent_received_data = None
        self.most_recent_received_exception = None
        self.most_recent_sent_data = None

        self.eva_init(
            timeout_interval_in_sec=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC,
            retransmit_interval_in_sec=TEST_DEFAULT_RETRANSMIT_INTERVAL_IN_SEC,
            start_message_id=TEST_START_MESSAGE_ID,
            terminate_by_timeout_enabled=False  # by default disable the termination
        )

        self.eva_register_receive_callback(self.on_receive)
        self.eva_register_send_complete_callback(self.on_send_complete)
        self.eva_register_error_callback(self.on_error)

    def on_receive(self, peer, info, data, nonce):
        self.most_recent_received_data = info, data, nonce
        self.received_data[peer].append(self.most_recent_received_data)

    def on_send_complete(self, peer, info, data, nonce):
        self.most_recent_sent_data = info, data, nonce
        self.sent_data[peer].append(self.most_recent_sent_data)

    def on_error(self, peer, exception):
        self.most_recent_received_exception = exception


class TestEVA(TestBase):
    def setUp(self):
        super().setUp()
        self.initialize(MockCommunity, 3)

        self.test_store = SimpleNamespace()

    async def test_one_chunk_binary(self):
        self.overlay(0).eva_send_binary(self.peer(1), b'test1', b'1234', 42)

        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(1).most_recent_received_data == (b'test1', b'1234', 42)
        assert len(self.overlay(0).sent_data[self.peer(1)]) == 1
        assert len(self.overlay(1).received_data[self.peer(0)]) == 1

    async def test_self_send(self):
        self.overlay(0).eva_send_binary(self.peer(0), b'test1', b'1234')

        await drain_loop(asyncio.get_event_loop())

        assert not self.overlay(0).most_recent_received_data
        assert len(self.overlay(0).sent_data[self.peer(1)]) == 0

    async def test_two_chunk_binary(self):
        data = b'test2', b'4321', 42
        self.overlay(0).block_size = 2
        self.overlay(0).eva_send_binary(self.peer(1), *data)

        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(1).most_recent_received_data == data
        assert len(self.overlay(0).sent_data[self.peer(1)]) == 1
        assert len(self.overlay(1).received_data[self.peer(0)]) == 1

    async def test_zero_transfer(self):
        self.overlay(0).eva_send_binary(self.peer(1), b'', b'')

        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(1).most_recent_received_data is None
        assert len(self.overlay(0).eva_protocol.outgoing) == 0
        assert len(self.overlay(1).eva_protocol.incoming) == 0

        assert len(self.overlay(0).sent_data[self.peer(1)]) == 0
        assert len(self.overlay(1).received_data[self.peer(0)]) == 0

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_one_megabyte_transfer(self):
        data_size = 1024 * 1024
        data = os.urandom(1), os.urandom(data_size), random.randrange(0, 256)

        self.overlay(0).eva_send_binary(self.peer(1), *data)

        await drain_loop(asyncio.get_event_loop())

        assert len(self.overlay(1).most_recent_received_data[1]) == data_size
        assert self.overlay(1).most_recent_received_data == data

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_termination_by_timeout(self):
        self.overlay(0).eva_protocol.terminate_by_timeout_enabled = True
        self.overlay(1).eva_protocol.terminate_by_timeout_enabled = True

        # breaks "on_data" function in community2 to make this community silent

        self.overlay(0).eva_protocol.window_size = 10
        self.overlay(1).eva_protocol.window_size = 20

        async def void(*_):
            await asyncio.sleep(0)

        self.overlay(1).eva_protocol.on_data = void

        self.overlay(0).eva_send_binary(self.peer(1), b'info', b'data')

        await self.deliver_messages(timeout=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC * 3)

        assert len(self.overlay(1).eva_protocol.incoming) == 0
        assert isinstance(self.overlay(1).most_recent_received_exception, TimeoutException)

        await self.deliver_messages(timeout=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC * 3)

        assert len(self.overlay(0).eva_protocol.outgoing) == 0
        assert isinstance(self.overlay(0).most_recent_received_exception, TimeoutException)

    async def test_retransmit(self):
        attempts = 2

        self.overlay(0).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_attempt_count = attempts

        # breaks "acknowledgement" function in community0 to make this community silent
        async def void(*_):
            await asyncio.sleep(0)

        self.overlay(0).eva_protocol.on_acknowledgement = void

        self.overlay(0).eva_send_binary(self.peer(1), b'info', b'data')
        await drain_loop(asyncio.get_event_loop())

        assert len(self.overlay(0).eva_protocol.outgoing) == 1
        assert len(self.overlay(1).eva_protocol.incoming) == 1

        assert self.overlay(1).eva_protocol.incoming[self.peer(0)].attempt == attempts

    async def test_retransmit_disabled(self):
        self.overlay(0).eva_protocol.retransmit_enabled = False
        self.overlay(1).eva_protocol.retransmit_enabled = False
        self.overlay(0).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_interval_in_sec = 0

        # breaks "acknowledgement" function in community0 to make this community silent
        async def void(*_):
            await asyncio.sleep(0)

        self.overlay(0).eva_protocol.on_acknowledgement = void

        self.overlay(0).eva_send_binary(self.peer(1), b'info', b'data')
        await drain_loop(asyncio.get_event_loop())

        assert len(self.overlay(0).eva_protocol.outgoing) == 1
        assert len(self.overlay(1).eva_protocol.incoming) == 1

        assert self.overlay(1).eva_protocol.incoming[self.peer(0)].attempt == 0

    async def test_size_limit(self):
        # test on a sender side
        self.overlay(2).eva_protocol.binary_size_limit = 4

        self.overlay(2).eva_send_binary(self.peer(0), b'info', b'12345')

        await drain_loop(asyncio.get_event_loop())

        assert isinstance(self.overlay(2).most_recent_received_exception, SizeException)
        assert not self.overlay(2).eva_protocol.outgoing
        assert not self.overlay(0).eva_protocol.incoming
        assert len(self.overlay(0).received_data[self.peer(1)]) == 0
        assert len(self.overlay(2).sent_data[self.peer(1)]) == 0

        # test on a receiver side
        self.overlay(0).most_recent_received_exception = None
        self.overlay(2).most_recent_received_exception = None

        self.overlay(0).eva_send_binary(self.peer(2), b'info', b'54321')

        await drain_loop(asyncio.get_event_loop())

        assert isinstance(self.overlay(0).most_recent_received_exception, TransferException)
        assert isinstance(self.overlay(2).most_recent_received_exception, SizeException)
        assert not self.overlay(2).eva_protocol.incoming
        assert not self.overlay(2).eva_protocol.outgoing
        assert len(self.overlay(0).sent_data[self.peer(2)]) == 0

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_duplex(self):
        count = 100
        block_size = 10

        self.overlay(0).eva_protocol.block_size = block_size
        self.overlay(1).eva_protocol.block_size = block_size

        data0 = os.urandom(1), os.urandom(block_size * count), random.randrange(0, 256)
        data1 = os.urandom(1), os.urandom(block_size * count), random.randrange(0, 256)

        self.overlay(0).eva_send_binary(self.peer(1), *data0)
        self.overlay(1).eva_send_binary(self.peer(0), *data1)

        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(0).most_recent_received_data == data1
        assert self.overlay(1).most_recent_received_data == data0

        assert not self.overlay(0).eva_protocol.incoming
        assert not self.overlay(0).eva_protocol.outgoing
        assert not self.overlay(1).eva_protocol.incoming
        assert not self.overlay(1).eva_protocol.outgoing
        assert len(self.overlay(0).sent_data[self.peer(1)]) == 1
        assert len(self.overlay(0).received_data[self.peer(1)]) == 1
        assert len(self.overlay(1).sent_data[self.peer(0)]) == 1
        assert len(self.overlay(1).received_data[self.peer(0)]) == 1

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_multiply_send(self):
        data_set_count = 10
        data_size = 1024

        data_list = [(os.urandom(1), os.urandom(data_size), random.randrange(0, 256)) for _ in range(data_set_count)]
        for data in data_list:
            self.overlay(0).eva_send_binary(self.peer(1), *data)

        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(1).received_data[self.peer(0)] == data_list
        assert not self.overlay(0).eva_protocol.scheduled

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_multiply_duplex(self):
        data_set_count = 5

        self.overlay(2).eva_protocol.terminate_by_timeout_enabled = False

        self.overlay(0).eva_protocol.block_size = 10
        self.overlay(1).eva_protocol.block_size = 10
        self.overlay(2).eva_protocol.block_size = 10

        # create 10 different data sets for each direction (0->1, 0->2, 1->0, 1->2, 2->0, 2->1)
        participants = [
            (self.peer(0), self.overlay(0)),
            (self.peer(1), self.overlay(1)),
            (self.peer(2), self.overlay(2)),
        ]

        data = [
            (p, list((os.urandom(1), os.urandom(50), random.randrange(0, 256)) for _ in range(data_set_count)))
            for p in permutations(participants, 2)
        ]

        for ((_, community), (peer, _)), data_set in data:
            for d in data_set:
                community.eva_send_binary(peer, *d)

        await drain_loop(asyncio.get_event_loop())

        assert len(self.overlay(0).received_data) == 2
        assert len(self.overlay(1).received_data) == 2
        assert len(self.overlay(2).received_data) == 2

        data_sets_checked = 0
        for ((peer, _), (_, community)), data_set in data:
            assert community.received_data[peer] == data_set
            data_sets_checked += 1

        assert data_sets_checked == 6

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_survive_when_multiply_packets_lost(self):
        self.overlay(0).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_interval_in_sec = 0

        lost_packets_count_estimation = 5
        data_set_count = 3

        block_count = 15
        block_size = 3
        window_size = 10

        packet_loss_probability = lost_packets_count_estimation / (block_count * data_set_count)

        self.overlay(0).eva_protocol.block_size = block_size
        self.overlay(1).eva_protocol.window_size = window_size

        self.overlay(1).eva_protocol.retransmit_attempt_count = lost_packets_count_estimation

        data = [(os.urandom(1), os.urandom(block_size * block_count), 0) for _ in range(data_set_count)]

        real_on_data1 = self.overlay(1).eva_protocol.on_data

        # store for the fake function
        self.test_store.actual_packets_lost = 0
        self.test_store.lost_packets_count_estimation = lost_packets_count_estimation
        self.test_store.packet_loss_probability = packet_loss_probability

        # modify "on_data" function to proxying all calls and to add a probability
        # to a packet loss
        async def fake_on_data1(peer, payload):
            chance_to_fake = random.random() < self.test_store.packet_loss_probability
            is_last_packet = len(payload.data_binary) == 0
            max_count_reached = self.test_store.actual_packets_lost >= self.test_store.lost_packets_count_estimation

            if chance_to_fake and not max_count_reached and not is_last_packet:
                self.test_store.actual_packets_lost += 1
                return

            await real_on_data1(peer, payload)

        self.overlay(1).eva_protocol.on_data = fake_on_data1

        for d in data:
            self.overlay(0).eva_send_binary(self.peer(1), *d)

        await drain_loop(asyncio.get_event_loop())

        logging.info(f'Estimated packet lost block_count/probability: '
                     f'{lost_packets_count_estimation}/{packet_loss_probability}')
        logging.info(f'Actual packet lost: {self.test_store.actual_packets_lost}')

        assert len(self.overlay(1).received_data[self.peer(0)]) == data_set_count
        assert self.overlay(1).received_data[self.peer(0)] == data

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_dynamically_changed_window_size(self):
        window_size = 5

        self.test_store.window_size_increment = -1
        self.test_store.actual_window_size = 0

        block_size = 2

        self.overlay(0).eva_protocol.block_size = block_size
        self.overlay(1).eva_protocol.window_size = window_size

        data = os.urandom(1), os.urandom(block_size * 100), 42

        real_on_send_acknowledgement1 = self.overlay(1).eva_protocol.send_acknowledgement

        def fake_eva_send_acknowledgement1(peer, transfer):
            if transfer.window_size == 1:
                # go up
                self.test_store.window_size_increment = 2

            transfer.window_size += self.test_store.window_size_increment

            self.test_store.actual_window_size = transfer.window_size
            real_on_send_acknowledgement1(peer, transfer)

        self.overlay(1).eva_protocol.send_acknowledgement = fake_eva_send_acknowledgement1

        self.overlay(0).eva_send_binary(self.peer(1), *data)
        await drain_loop(asyncio.get_event_loop())

        assert self.overlay(1).received_data[self.peer(0)][0] == data

    async def test_cheating_send_over_size(self):
        self.overlay(1).eva_protocol.binary_size_limit = 4
        acknowledgement_message_id = TEST_START_MESSAGE_ID + 1

        real_on_acknowledgement0 = self.overlay(0).decode_map[acknowledgement_message_id]

        def fake_on_acknowledgement0(peer, payload):
            transfer = self.overlay(0).eva_protocol.outgoing[self.peer(1)]
            transfer.data_binary = b'1' * 100
            transfer.count = 100
            return real_on_acknowledgement0(peer, payload)

        self.overlay(0).decode_map[acknowledgement_message_id] = fake_on_acknowledgement0

        self.overlay(0).eva_send_binary(self.peer(1), b'', b'12')

        await drain_loop(asyncio.get_event_loop())

        assert isinstance(self.overlay(0).most_recent_received_exception, TransferException)
        assert isinstance(self.overlay(1).most_recent_received_exception, SizeException)

    @pytest.mark.timeout(PYTEST_TIMEOUT_IN_SEC)
    async def test_wrong_message_order_and_wrong_nonce(self):
        self.overlay(0).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_interval_in_sec = 0
        self.overlay(1).eva_protocol.retransmit_attempt_count = 5

        data_set_count = 1

        block_count = 20
        block_size = 3
        window_size = 2

        self.overlay(0).eva_protocol.block_size = block_size
        self.overlay(1).eva_protocol.window_size = window_size

        data = [(os.urandom(1), os.urandom(block_size * block_count), 0) for _ in range(data_set_count)]

        real_on_acknowledgement = self.overlay(0).eva_protocol.on_acknowledgement

        self.test_store.acknowledgement_count_before_start = 2
        self.test_store.wrong_order_attempted = False
        self.test_store.wrong_nonce_attempted = False

        # test wrong message order and wrong nonce
        async def fake_on_acknowledgement(peer, payload):
            if self.test_store.acknowledgement_count_before_start > 0:
                self.test_store.acknowledgement_count_before_start -= 1
                await real_on_acknowledgement(peer, payload)
            elif not self.test_store.wrong_order_attempted:
                self.test_store.wrong_order_attempted = True
                payload.number = 0
                await real_on_acknowledgement(peer, payload)
            elif not self.test_store.wrong_nonce_attempted:
                self.test_store.wrong_nonce_attempted = True
                payload.nonce = 100
                await real_on_acknowledgement(peer, payload)
            else:
                await real_on_acknowledgement(peer, payload)

        self.overlay(0).eva_protocol.on_acknowledgement = fake_on_acknowledgement

        for d in data:
            self.overlay(0).eva_send_binary(self.peer(1), *d)
        await drain_loop(asyncio.get_event_loop())

        assert len(self.overlay(1).received_data[self.peer(0)]) == data_set_count
        assert self.overlay(1).received_data[self.peer(0)] == data

    async def test_received_packet_that_have_no_transfer(self):
        self.overlay(0).eva_protocol.terminate_by_timeout_enabled = True
        self.overlay(1).eva_protocol.terminate_by_timeout_enabled = True

        self.overlay(0).eva_protocol.timeout_interval_in_sec = 0
        self.overlay(1).eva_protocol.timeout_interval_in_sec = 0

        # wait to new timeout will be set up
        await self.deliver_messages(timeout=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC * 3)

        # try to send data with 0 timeout
        # it should lead to packet's send without presented transfer
        self.overlay(0).eva_send_binary(self.peer(1), b'', os.urandom(1000))
        await self.deliver_messages(timeout=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC * 3)

        assert len(self.overlay(0).eva_protocol.outgoing) == 0
        assert isinstance(self.overlay(0).most_recent_received_exception, TimeoutException)
        assert len(self.overlay(1).eva_protocol.incoming) == 0
        assert isinstance(self.overlay(1).most_recent_received_exception, TimeoutException)

        # then try to send an error message without corresponding transfer
        self.overlay(0).most_recent_received_exception = None
        self.overlay(1).most_recent_received_exception = None

        self.overlay(0).eva_send_message(self.peer(1), Error('message'.encode('utf-8')))
        await self.deliver_messages(timeout=TEST_DEFAULT_TERMINATE_INTERVAL_IN_SEC * 3)

        assert not self.overlay(0).most_recent_received_exception
        assert not self.overlay(1).most_recent_received_exception


@pytest.fixture
def eva():
    return EVAProtocol(Mock())


@pytest.fixture
def peer():
    return Mock()


@pytest.mark.asyncio
async def test_on_write_request_data_size_le0(eva: EVAProtocol, peer):
    # validate that data_size can not be less or equal to 0
    with patch.object(EVAProtocol, '_incoming_error') as method_mock:
        await eva.on_write_request(peer, WriteRequest(0, 0, b''))
        await eva.on_write_request(peer, WriteRequest(-1, 0, b''))
        assert peer not in eva.incoming
        assert method_mock.call_count == 2


@pytest.mark.asyncio
async def test_on_acknowledgement_window_size_attr(eva: EVAProtocol, peer):
    transfer = create_transfer(block_count=10)
    eva.outgoing[peer] = transfer
    window_size = 0

    # validate that window_size can not be less or equal to 0
    await eva.on_acknowledgement(peer, Acknowledgement(1, window_size, 0))
    assert transfer.window_size == eva.MIN_WINDOWS_SIZE

    # validate that window_size can not be greater than binary_size_limit
    window_size = eva.binary_size_limit + 1
    await eva.on_acknowledgement(peer, Acknowledgement(1, window_size, 0))
    assert transfer.window_size == eva.binary_size_limit
