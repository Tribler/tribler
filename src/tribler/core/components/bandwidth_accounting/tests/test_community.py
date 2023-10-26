from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer

from tribler.core.components.bandwidth_accounting.community.bandwidth_accounting_community import (
    BandwidthAccountingCommunity,
)
from tribler.core.components.bandwidth_accounting.community.cache import BandwidthTransactionSignCache
from tribler.core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler.core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData, EMPTY_SIGNATURE
from tribler.core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8, TriblerTestBase
from tribler.core.utilities.utilities import MEMORY_DB

ID1, ID2, ID3 = range(3)


class TestBandwidthAccountingCommunity(TriblerTestBase):

    def setUp(self):
        super().setUp()
        self.initialize(BandwidthAccountingCommunity, 2)

    def create_node(self, *args, **kwargs):
        peer = Peer(default_eccrypto.generate_key("curve25519"), address=("1.2.3.4", 5))
        db = BandwidthDatabase(db_path=MEMORY_DB, my_pub_key=peer.public_key.key_to_bin())
        ipv8 = TriblerMockIPv8(peer, BandwidthAccountingCommunity, database=db,
                               settings=BandwidthAccountingSettings())
        return ipv8

    def database(self, i):
        return self.overlay(i).database

    def add_cache(self, i, cache):
        return self.overlay(i).request_cache.add(cache)

    async def test_single_transaction(self):
        """
        Test a simple transaction between two parties.
        """
        await self.overlay(ID1).do_payout(self.peer(ID2), 1024)

        assert self.database(ID1).get_total_taken(self.key_bin(ID1)) == 1024
        assert self.database(ID2).get_total_taken(self.key_bin(ID1)) == 1024

    async def test_multiple_transactions(self):
        """
        Test multiple, subsequent transactions between two parties.
        """
        await self.overlay(ID1).do_payout(self.peer(ID2), 500)
        await self.overlay(ID1).do_payout(self.peer(ID2), 1500)

        assert self.database(ID1).get_total_taken(self.key_bin(ID1)) == 2000
        assert self.database(ID2).get_total_taken(self.key_bin(ID1)) == 2000

    async def test_bilateral_transaction(self):
        """
        Test creating a transaction from A to B and one from B to A.
        """
        await self.overlay(ID1).do_payout(self.peer(ID2), 500)
        await self.overlay(ID2).do_payout(self.peer(ID1), 1500)

        assert self.database(ID1).get_total_taken(self.key_bin(ID1)) == 500
        assert self.database(ID2).get_total_taken(self.key_bin(ID1)) == 500
        assert self.database(ID1).get_total_taken(self.key_bin(ID2)) == 1500
        assert self.database(ID2).get_total_taken(self.key_bin(ID2)) == 1500

    async def test_bilateral_transaction_timestamps(self):
        """
        Test creating subsequent transactions and check whether the timestamps are different.
        """
        tx1 = await self.overlay(ID1).do_payout(self.peer(ID2), 500)
        tx2 = await self.overlay(ID1).do_payout(self.peer(ID2), 500)

        assert tx1.timestamp != tx2.timestamp

    async def test_invalid_transaction(self):
        """
        Test sending a transaction with an invalid signature to the counterparty, which should be ignored.
        """
        tx = self.overlay(ID1).construct_signed_transaction(self.peer(ID2), 300)
        tx.signature_a = b"invalid"
        self.database(ID1).BandwidthTransaction.insert(tx)
        cache = self.add_cache(ID1, BandwidthTransactionSignCache(self.overlay(ID1), tx))
        self.overlay(ID1).send_transaction(tx, self.address(ID2), cache.number)

        await self.deliver_messages()

        assert self.database(ID2).get_total_taken(self.key_bin(ID1)) == 0

    async def test_ignore_unknown_transaction(self):
        """
        Test whether we are ignoring a transaction that is not in our cache.
        """
        tx = BandwidthTransactionData(ID2, self.key_bin(ID1), self.key_bin(ID2), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 1000)
        tx.sign(self.private_key(ID1), as_a=True)
        self.overlay(ID1).send_transaction(tx, self.address(ID2), 1234)

        await self.deliver_messages()

        assert not self.database(ID1).get_latest_transaction(self.key_bin(ID1), self.key_bin(ID2))

    async def test_concurrent_transaction_out_of_order(self):
        """
        Test creating multiple transactions, while the other party is offline and receives messages out of order.
        """
        tx1 = BandwidthTransactionData(1, self.key_bin(ID1), self.key_bin(ID2), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 1000)
        tx2 = BandwidthTransactionData(2, self.key_bin(ID1), self.key_bin(ID2), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)

        # Send them in reverse order
        cache = self.add_cache(ID1, BandwidthTransactionSignCache(self.overlay(ID1), tx1))
        self.overlay(ID1).send_transaction(tx2, self.address(ID2), cache.number)
        await self.deliver_messages()

        # This one should be ignored by node 1
        cache = self.add_cache(ID1, BandwidthTransactionSignCache(self.overlay(ID1), tx1))
        self.overlay(ID1).send_transaction(tx1, self.address(ID2), cache.number)
        await self.deliver_messages()

        # Both parties should have the transaction with amount 2000 in their database
        assert self.database(ID1).get_total_taken(self.key_bin(ID1)) == 2000
        assert self.database(ID2).get_total_taken(self.key_bin(ID1)) == 2000

    async def test_querying_peer(self):
        """
        Test whether node C can query node B to get the transaction between A and B.
        """
        await self.overlay(ID1).do_payout(self.peer(ID2), 500)

        self.add_node_to_experiment(self.create_node())
        self.overlay(ID3).query_transactions(self.peer(ID2))

        await self.deliver_messages()

        assert self.database(ID3).get_total_taken(self.key_bin(ID1)) == 500

    async def test_query_random_peer(self):
        """
        Test whether node C can query node B to get the transaction between A and B.
        """
        await self.overlay(ID1).do_payout(self.peer(ID2), 500)

        self.add_node_to_experiment(self.create_node())
        self.overlay(ID3).query_random_peer()

        await self.deliver_messages()

        assert self.database(ID3).get_total_taken(self.key_bin(ID1)) == 500
