from __future__ import annotations

import os
import socket
from typing import TYPE_CHECKING

from ipv8.test.base import TestBase
from ipv8.test.mocking.endpoint import MockEndpointListener

from tribler.core.rendezvous.community import RendezvousCommunity, RendezvousSettings
from tribler.core.rendezvous.database import RendezvousDatabase
from tribler.core.rendezvous.payload import PullRecordPayload, RecordPayload

if TYPE_CHECKING:
    from ipv8.community import CommunitySettings
    from ipv8.test.mocking.ipv8 import MockIPv8


class TestUserActivityCommunity(TestBase[RendezvousCommunity]):
    """
    Tests for the rendezvous community.
    """

    def setUp(self) -> None:
        """
        Create two communities.
        """
        super().setUp()

        self.initialize(RendezvousCommunity, 2)

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Add a memory database to both nodes.
        """
        return super().create_node(RendezvousSettings(database=RendezvousDatabase(":memory:")),
                                   create_dht, enable_statistics)

    def database(self, i: int) -> RendezvousDatabase:
        """
        Get the database manager of node i.
        """
        return self.overlay(i).composition.database

    async def test_pull_known_crawler(self) -> None:
        """
        Test if a known crawler is allowed to crawl.
        """
        self.database(1).add(self.peer(0), 0.0, 10.0)
        self.overlay(1).composition.crawler_mid = self.mid(0)

        with self.assertReceivedBy(0, [RecordPayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PullRecordPayload(self.mid(1)))
            await self.deliver_messages()
        payload, = received

        self.assertEqual(self.key_bin(0), payload.public_key)
        self.assertEqual(socket.inet_pton(socket.AF_INET6 if int(os.environ.get("TEST_IPV8_WITH_IPV6", "0"))
                                          else socket.AF_INET, self.address(0)[0]), payload.ip)
        self.assertEqual(self.address(0)[1], payload.port)
        self.assertEqual(0.0, payload.start)
        self.assertEqual(10.0, payload.stop)

    async def test_pull_unknown_crawler(self) -> None:
        """
        Test if an unknown crawler does not receive any information.
        """
        self.database(1).add(self.peer(0), 0.0, 10.0)
        self.overlay(1).composition.crawler_mid = bytes(b ^ 255 for b in self.mid(0))

        with self.assertReceivedBy(0, []):
            self.overlay(0).ez_send(self.peer(1), PullRecordPayload(self.mid(1)))
            await self.deliver_messages()

    async def test_pull_replay_attack(self) -> None:
        """
        Test if an unknown crawler does not receive any information.
        """
        self.add_node_to_experiment(self.create_node())
        self.database(1).add(self.peer(0), 0.0, 10.0)
        self.overlay(1).composition.crawler_mid = self.mid(0)
        self.overlay(2).composition.crawler_mid = self.mid(0)

        packet_sniffer = MockEndpointListener(self.overlay(1).endpoint)
        self.overlay(1).endpoint.add_listener(packet_sniffer)
        self.overlay(0).ez_send(self.peer(1), PullRecordPayload(self.mid(1)))
        await self.deliver_messages()
        packet, _ = packet_sniffer.received_packets
        _, data = packet

        with self.assertReceivedBy(1, []):
            self.endpoint(1).send(self.address(2), data)
            await self.deliver_messages()
