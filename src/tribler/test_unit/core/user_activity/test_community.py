from unittest.mock import AsyncMock, Mock, call

from ipv8.test.base import TestBase
from ipv8.test.mocking.endpoint import MockEndpointListener

from tribler.core.database.layers.user_activity import UserActivityLayer
from tribler.core.user_activity.community import UserActivityCommunity
from tribler.core.user_activity.payload import InfohashPreferencePayload, PullPreferencePayload


class TestUserActivityCommunity(TestBase[UserActivityCommunity]):
    """
    Tests for the UserActivityCommunity class.
    """

    def setUp(self) -> None:
        """
        Create two communities.
        """
        super().setUp()

        self.initialize(UserActivityCommunity, 2)

    def database_manager(self, i: int) -> UserActivityLayer:
        """
        Get the database manager of node i.
        """
        return self.overlay(i).composition.manager.database_manager

    async def test_gossip_aggregate(self) -> None:
        """
        Test if valid aggregates are gossiped to a random connected peer.
        """
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.database_manager(0).get_random_query_aggregate = Mock(return_value=(
            "test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0]
        ))

        with self.assertReceivedBy(1, [InfohashPreferencePayload]) as received:
            self.overlay(0).gossip()
            await self.deliver_messages()
        payload, = received

        self.assertEqual("test", payload.query)
        self.assertListEqual([b"\x00" * 20, b"\x01" * 20], payload.infohashes)
        self.assertListEqual([1.0, 2.0], payload.weights)
        self.assertEqual(call(1), self.database_manager(0).get_random_query_aggregate.call_args)
        self.assertEqual(call("test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0], self.key_bin(0)),
                         self.database_manager(1).store_external.call_args)
        self.assertEqual(call(b"\x01" * 20), self.overlay(1).composition.manager.check.call_args)

    async def test_gossip_no_aggregate(self) -> None:
        """
        Test if missing aggregates are not gossiped.
        """
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.database_manager(0).get_random_query_aggregate = Mock(return_value=None)

        with self.assertReceivedBy(1, []):
            self.overlay(0).gossip()
            await self.deliver_messages()

    async def test_gossip_target_peer(self) -> None:
        """
        Test if gossip can be sent to a target peer.
        """
        self.add_node_to_experiment(self.create_node())
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.overlay(2).composition.manager = AsyncMock()
        self.database_manager(0).get_random_query_aggregate = Mock(return_value=(
            "test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0]
        ))

        with self.assertReceivedBy(1, []), self.assertReceivedBy(2, [InfohashPreferencePayload]) as received:
            self.overlay(0).gossip([self.peer(2)])
            await self.deliver_messages()
        payload, = received

        self.assertEqual("test", payload.query)
        self.assertListEqual([b"\x00" * 20, b"\x01" * 20], payload.infohashes)
        self.assertListEqual([1.0, 2.0], payload.weights)
        self.assertEqual(call(0), self.database_manager(0).get_random_query_aggregate.call_args)
        self.assertEqual(call("test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0], self.key_bin(0)),
                         self.database_manager(2).store_external.call_args)
        self.assertEqual(call(b"\x01" * 20), self.overlay(2).composition.manager.check.call_args)

    async def test_pull_known_crawler(self) -> None:
        """
        Test if a known crawler is allowed to crawl.
        """
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.overlay(1).composition.crawler_mid = self.mid(0)
        self.database_manager(1).get_random_query_aggregate = Mock(return_value=(
            "test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0]
        ))

        with self.assertReceivedBy(0, [InfohashPreferencePayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PullPreferencePayload(self.mid(1)))
            await self.deliver_messages()
        payload, = received

        self.assertEqual("test", payload.query)
        self.assertListEqual([b"\x00" * 20, b"\x01" * 20], payload.infohashes)
        self.assertListEqual([1.0, 2.0], payload.weights)
        self.assertEqual(call(0), self.database_manager(1).get_random_query_aggregate.call_args)

    async def test_pull_unknown_crawler(self) -> None:
        """
        Test if an unknown crawler does not receive any information.
        """
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.overlay(1).composition.crawler_mid = bytes(b ^ 255 for b in self.mid(0))
        self.database_manager(1).get_random_query_aggregate = Mock(return_value=(
            "test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0]
        ))

        with self.assertReceivedBy(0, []):
            self.overlay(0).ez_send(self.peer(1), PullPreferencePayload(self.mid(1)))
            await self.deliver_messages()

    async def test_pull_replay_attack(self) -> None:
        """
        Test if an unknown crawler does not receive any information.
        """
        self.add_node_to_experiment(self.create_node())
        self.overlay(0).composition.manager = AsyncMock()
        self.overlay(1).composition.manager = AsyncMock()
        self.overlay(2).composition.manager = AsyncMock()
        self.overlay(1).composition.crawler_mid = self.mid(0)
        self.overlay(2).composition.crawler_mid = self.mid(0)
        self.database_manager(1).get_random_query_aggregate = Mock(return_value=(
            "test", [b"\x00" * 20, b"\x01" * 20], [1.0, 2.0]
        ))

        packet_sniffer = MockEndpointListener(self.overlay(1).endpoint)
        self.overlay(1).endpoint.add_listener(packet_sniffer)
        self.overlay(0).ez_send(self.peer(1), PullPreferencePayload(self.mid(1)))
        await self.deliver_messages()
        packet, _ = packet_sniffer.received_packets
        _, data = packet

        with self.assertReceivedBy(1, []):
            self.endpoint(1).send(self.address(2), data)
            await self.deliver_messages()
