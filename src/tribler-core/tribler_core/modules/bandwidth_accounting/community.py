from __future__ import annotations

from asyncio import Future
from binascii import unhexlify
from pathlib import Path
from typing import Dict

from ipv8.community import Community
from ipv8.peer import AddressType, Peer
from ipv8.requestcache import RequestCache

from pony.orm import db_session

from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.cache import BandwidthTransactionSignCache
from tribler_core.modules.bandwidth_accounting.database import BandwidthDatabase
from tribler_core.modules.bandwidth_accounting.payload import BandwidthTransactionPayload
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData
from tribler_core.utilities.unicode import hexlify


class BandwidthAccountingCommunity(Community):
    """
    Community around bandwidth accounting and payouts.
    """
    community_id = unhexlify('51780a6418d9f150ec0a97ee2b4b12886cf56370')
    DB_NAME = 'bandwidth'
    version = b'\x02'

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the community.
        :param persistence: The database that stores transactions, will be created if not provided.
        :param database_path: The path at which the database will be created. Defaults to the current working directory.
        """
        self.database = kwargs.pop('database', None)
        self.database_path = Path(kwargs.pop('database_path', ''))

        super().__init__(*args, **kwargs)

        self.request_cache = RequestCache()
        self.my_pk = self.my_peer.public_key.key_to_bin()

        if not self.database:
            self.database = BandwidthDatabase(self.database_path, self.my_pk)

        self.add_message_handler(BandwidthTransactionPayload, self.received_transaction)

        self.logger.info("Started bandwidth accounting community with public key %s", hexlify(self.my_pk))

    def construct_signed_transaction(self, peer: Peer, amount: int) -> BandwidthTransactionData:
        """
        Construct a new signed bandwidth transaction.
        :param peer: The counterparty of the transaction.
        :param amount: The amount of bytes to payout.
        :return A signed BandwidthTransaction.
        """
        peer_pk = peer.public_key.key_to_bin()
        latest_tx = self.database.get_latest_transaction(self.my_pk, peer_pk)
        total_amount = latest_tx.amount + amount if latest_tx else amount
        next_seq_num = latest_tx.sequence_number + 1 if latest_tx else 1
        tx = BandwidthTransactionData(next_seq_num, self.my_pk, peer_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, total_amount)
        tx.sign(self.my_peer.key, as_a=True)
        return tx

    def do_payout(self, peer: Peer, amount: int) -> Future:
        """
        Conduct a payout with a given amount of bytes to a peer.
        :param peer: The counterparty of the payout.
        :param amount: The amount of bytes to payout.
        :return A Future that fires when the counterparty has acknowledged the payout.
        """
        tx = self.construct_signed_transaction(peer, amount)
        with db_session:
            self.database.BandwidthTransaction.insert(tx)
        cache = self.request_cache.add(BandwidthTransactionSignCache(self, tx))
        self.send_transaction(tx, peer, cache.number)

        return cache.future

    def send_transaction(self, transaction: BandwidthTransactionData, peer: Peer, request_id: int) -> None:
        """
        Send a provided transaction to another party.
        :param transaction: The BandwidthTransaction to send to the other party.
        :param peer: The peer that will receive the transaction.
        :param request_id: The identifier of the message, is usually provided by a request cache.
        """
        payload = BandwidthTransactionPayload.from_transaction(transaction, request_id)
        packet = self._ez_pack(self._prefix, 1, [payload], False)
        self.endpoint.send(peer.address, packet)

    async def received_transaction(self, source_address: AddressType, data: bytes) -> None:
        """
        Callback when we receive a transaction from another peer.
        :param source_address: The network address of the peer that has sent us the transaction.
        :param data: The serialized, raw data in the packet.
        """
        payload = self._ez_unpack_noauth(BandwidthTransactionPayload, data, global_time=False)
        tx = BandwidthTransactionData.from_payload(payload)

        if not tx.is_valid():
            self.logger.info("Transaction %s not valid, ignoring it", tx)
            return

        latest_tx = self.database.get_latest_transaction(tx.public_key_a, tx.public_key_b)

        if payload.public_key_b == self.my_peer.public_key.key_to_bin():
            from_peer = Peer(payload.public_key_a, source_address)
            if latest_tx:
                # Check if the amount in the received transaction is higher than the amount of the latest one
                # in the database.
                if payload.amount > latest_tx.amount:
                    # Sign it, store it, and send it back
                    tx.sign(self.my_peer.key, as_a=False)
                    self.database.BandwidthTransaction.insert(tx)
                    self.send_transaction(tx, from_peer, payload.request_id)
                else:
                    self.logger.info("Received older bandwidth transaction - sending back the latest one")
                    self.send_transaction(latest_tx, from_peer, payload.request_id)
            else:
                # This transaction is the first one with party A. Sign it, store it, and send it back.
                tx.sign(self.my_peer.key, as_a=False)
                self.database.BandwidthTransaction.insert(tx)
                from_peer = Peer(payload.public_key_a, source_address)
                self.send_transaction(tx, from_peer, payload.request_id)
        elif payload.public_key_a == self.my_peer.public_key.key_to_bin():
            # It seems that we initiated this transaction. Check if we are waiting for it.
            cache = self.request_cache.get("bandwidth-tx-sign", payload.request_id)
            if not cache:
                self.logger.info("Received bandwidth transaction %s without associated cache entry, ignoring it", tx)
                return

            if not latest_tx or (latest_tx and latest_tx.amount >= tx.amount):
                self.database.BandwidthTransaction.insert(tx)

            cache.future.set_result(tx)

    def get_statistics(self) -> Dict:
        """
        Return a dictionary with bandwidth statistics, including the total amount of bytes given and taken, and the
        number of unique peers you helped/that helped you.
        :return: A dictionary with statistics.
        """
        my_pk = self.my_peer.public_key.key_to_bin()
        return {
            "id": hexlify(my_pk),
            "total_given": self.database.get_total_given(my_pk),
            "total_taken": self.database.get_total_taken(my_pk),
            "num_peers_helped": self.database.get_num_peers_helped(my_pk),
            "num_peers_helped_by": self.database.get_num_peers_helped_by(my_pk)
        }

    async def unload(self) -> None:
        """
        Unload this community by shutting down the request cache and database.
        """
        self.logger.info("Unloading the bandwidth accounting community.")

        await self.request_cache.shutdown()
        self.database.shutdown()

        await super().unload()


class BandwidthAccountingTestnetCommunity(BandwidthAccountingCommunity):
    """
    This community defines the testnet for bandwidth accounting.
    """
    DB_NAME = 'bandwidth_testnet'
    community_id = unhexlify('e7de42f46f9ef225f4a5fc32ed0a0ce9a8ea4af6')
