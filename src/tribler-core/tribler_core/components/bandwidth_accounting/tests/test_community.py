from asyncio import sleep

from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from tribler_core.components.bandwidth_accounting.community.cache import BandwidthTransactionSignCache
from tribler_core.components.bandwidth_accounting.community.bandwidth_accounting_community \
    import BandwidthAccountingCommunity
from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData, EMPTY_SIGNATURE
from tribler_core.utilities.utilities import MEMORY_DB


class TestBandwidthAccountingCommunity(TestBase):

    def setUp(self):
        super().setUp()
        self.initialize(BandwidthAccountingCommunity, 2)

    def create_node(self):
        db = BandwidthDatabase(db_path=MEMORY_DB, my_pub_key=b"0000")
        ipv8 = MockIPv8("curve25519", BandwidthAccountingCommunity, database=db,
                        settings=BandwidthAccountingSettings())
        community = ipv8.get_overlay(BandwidthAccountingCommunity)
        # Dumb workaround for MockIPv8 not supporting key injection
        community.database.my_pub_key = ipv8.my_peer.public_key.key_to_bin()
        return ipv8

    async def test_single_transaction(self):
        """
        Test a simple transaction between two parties.
        """
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 1024)

        from_pk = self.nodes[0].my_peer.public_key.key_to_bin()
        assert self.nodes[0].overlay.database.get_total_taken(from_pk) == 1024
        assert self.nodes[1].overlay.database.get_total_taken(from_pk) == 1024

    async def test_multiple_transactions(self):
        """
        Test multiple, subsequent transactions between two parties.
        """
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 1500)

        from_pk = self.nodes[0].my_peer.public_key.key_to_bin()
        assert self.nodes[0].overlay.database.get_total_taken(from_pk) == 2000
        assert self.nodes[1].overlay.database.get_total_taken(from_pk) == 2000

    async def test_bilateral_transaction(self):
        """
        Test creating a transaction from A to B and one from B to A.
        """
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)
        await self.nodes[1].overlay.do_payout(self.nodes[0].overlay.my_peer, 1500)

        pk1 = self.nodes[0].my_peer.public_key.key_to_bin()
        pk2 = self.nodes[1].my_peer.public_key.key_to_bin()
        assert self.nodes[0].overlay.database.get_total_taken(pk1) == 500
        assert self.nodes[1].overlay.database.get_total_taken(pk1) == 500
        assert self.nodes[0].overlay.database.get_total_taken(pk2) == 1500
        assert self.nodes[1].overlay.database.get_total_taken(pk2) == 1500

    async def test_bilateral_transaction_timestamps(self):
        """
        Test creating subsequent transactions and check whether the timestamps are different.
        """
        tx1 = await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)
        await sleep(0.1)
        tx2 = await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)
        assert tx1.timestamp != tx2.timestamp

    async def test_invalid_transaction(self):
        """
        Test sending a transaction with an invalid signature to the counterparty, which should be ignored.
        """
        other_peer = self.nodes[1].my_peer
        tx = self.nodes[0].overlay.construct_signed_transaction(other_peer, 300)
        tx.signature_a = b"invalid"
        self.nodes[0].overlay.database.BandwidthTransaction.insert(tx)
        cache = self.nodes[0].overlay.request_cache.add(BandwidthTransactionSignCache(self.nodes[0].overlay, tx))
        self.nodes[0].overlay.send_transaction(tx, other_peer.address, cache.number)

        await self.deliver_messages()

        assert self.nodes[1].overlay.database.get_total_taken(self.nodes[0].my_peer.public_key.key_to_bin()) == 0

    async def test_ignore_unknown_transaction(self):
        """
        Test whether we are ignoring a transaction that is not in our cache.
        """
        pk1 = self.nodes[0].my_peer.public_key.key_to_bin()
        pk2 = self.nodes[1].my_peer.public_key.key_to_bin()

        tx = BandwidthTransactionData(1, pk1, pk2, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 1000)
        tx.sign(self.nodes[0].my_peer.key, as_a=True)
        self.nodes[0].overlay.send_transaction(tx, self.nodes[1].my_peer.address, 1234)
        await self.deliver_messages()
        assert not self.nodes[0].overlay.database.get_latest_transaction(pk1, pk2)

    async def test_concurrent_transaction_out_of_order(self):
        """
        Test creating multiple transactions, while the other party is offline and receives messages out of order.
        """
        pk1 = self.nodes[0].my_peer.public_key.key_to_bin()
        pk2 = self.nodes[1].my_peer.public_key.key_to_bin()

        tx1 = BandwidthTransactionData(1, pk1, pk2, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 1000)
        tx2 = BandwidthTransactionData(2, pk1, pk2, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)

        # Send them in reverse order
        cache = self.nodes[0].overlay.request_cache.add(BandwidthTransactionSignCache(self.nodes[0].overlay, tx1))
        self.nodes[0].overlay.send_transaction(tx2, self.nodes[1].my_peer.address, cache.number)
        await self.deliver_messages()

        # This one should be ignored by node 1
        cache = self.nodes[0].overlay.request_cache.add(BandwidthTransactionSignCache(self.nodes[0].overlay, tx1))
        self.nodes[0].overlay.send_transaction(tx1, self.nodes[1].my_peer.address, cache.number)
        await self.deliver_messages()

        # Both parties should have the transaction with amount 2000 in their database
        assert self.nodes[0].overlay.database.get_total_taken(pk1) == 2000
        assert self.nodes[1].overlay.database.get_total_taken(pk1) == 2000

    async def test_querying_peer(self):
        """
        Test whether node C can query node B to get the transaction between A and B.
        """
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)

        # Add an additional node to the experiment
        self.add_node_to_experiment(self.create_node())
        self.nodes[2].overlay.query_transactions(self.nodes[1].my_peer)

        await self.deliver_messages()

        pk1 = self.nodes[0].my_peer.public_key.key_to_bin()
        assert self.nodes[2].overlay.database.get_total_taken(pk1) == 500

    async def test_query_random_peer(self):
        """
        Test whether node C can query node B to get the transaction between A and B.
        """
        await self.nodes[0].overlay.do_payout(self.nodes[1].overlay.my_peer, 500)

        # Add an additional node to the experiment
        self.add_node_to_experiment(self.create_node())
        self.nodes[2].overlay.query_random_peer()

        await self.deliver_messages()

        pk1 = self.nodes[0].my_peer.public_key.key_to_bin()
        assert self.nodes[2].overlay.database.get_total_taken(pk1) == 500
