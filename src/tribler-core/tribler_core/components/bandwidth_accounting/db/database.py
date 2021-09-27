from pathlib import Path
from typing import List, Optional, Union

from pony.orm import Database, count, db_session, select, sum

from tribler_core.components.bandwidth_accounting.db import history, misc, transaction as db_transaction
from tribler_core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData
from tribler_core.utilities.utilities import MEMORY_DB


class BandwidthDatabase:
    """
    Simple database that stores bandwidth transactions in Tribler as a work graph.
    """
    CURRENT_DB_VERSION = 9
    MAX_HISTORY_ITEMS = 100  # The maximum number of history items to store.

    def __init__(self, db_path: Union[Path, type(MEMORY_DB)], my_pub_key: bytes,
                 store_all_transactions: bool = False) -> None:
        """
        Sets up the persistence layer ready for use.
        :param db_path: The full path of the database.
        :param my_pub_key: The public key of the user operating the database.
        :param store_all_transactions: Whether we store all pairwise transactions in the database. This is disabled by
        default and used for data collection purposes.
        """
        self.my_pub_key = my_pub_key
        self.store_all_transactions = store_all_transactions

        self.database = Database()
        # This attribute is internally called by Pony on startup, though pylint cannot detect it
        # with the static analysis.
        # pylint: disable=unused-variable

        @self.database.on_connect(provider='sqlite')
        def sqlite_sync_pragmas(_, connection):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = 1")
            cursor.execute("PRAGMA temp_store = 2")
            # pylint: enable=unused-variable

        self.MiscData = misc.define_binding(self.database)
        self.BandwidthTransaction = db_transaction.define_binding(self)
        self.BandwidthHistory = history.define_binding(self)

        if db_path is MEMORY_DB:
            create_db = True
            db_path_string = ":memory:"
        else:
            create_db = not db_path.is_file()
            db_path_string = str(db_path)

        self.database.bind(provider='sqlite', filename=db_path_string, create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(self.CURRENT_DB_VERSION))

    def has_transaction(self, transaction: BandwidthTransactionData) -> bool:
        """
        Return whether a transaction is persisted to the database.
        :param transaction: The transaction to check.
        :return: A boolean value, indicating whether we have the transaction in the database or not.
        """
        return self.BandwidthTransaction.exists(public_key_a=transaction.public_key_a,
                                                public_key_b=transaction.public_key_b,
                                                sequence_number=transaction.sequence_number)

    @db_session
    def get_my_latest_transactions(self, limit: Optional[int] = None) -> List[BandwidthTransactionData]:
        """
        Return all latest transactions involving you.
        :param limit: An optional integer, to limit the number of results returned. Pass None to get all results.
        :return A list containing all latest transactions involving you.
        """
        results = []
        db_txs = select(tx for tx in self.BandwidthTransaction
                        if tx.public_key_a == self.my_pub_key or tx.public_key_b == self.my_pub_key)\
            .limit(limit)
        for db_tx in db_txs:
            results.append(BandwidthTransactionData.from_db(db_tx))
        return results

    @db_session
    def get_latest_transaction(self, public_key_a: bytes, public_key_b: bytes) -> BandwidthTransactionData:
        """
        Return the latest transaction between two parties, or None if no such transaction exists.
        :param public_key_a: The public key of the party transferring the bandwidth.
        :param public_key_b: The public key of the party receiving the bandwidth.
        :return The latest transaction between the two specified parties, or None if no such transaction exists.
        """
        db_obj = self.BandwidthTransaction.get(public_key_a=public_key_a, public_key_b=public_key_b)
        return BandwidthTransactionData.from_db(db_obj) if db_obj else None

    @db_session
    def get_latest_transactions(self, public_key: bytes, limit: Optional[int] = 100) -> List[BandwidthTransactionData]:
        """
        Return the latest transactions of a given public key, or an empty list if no transactions exist.
        :param public_key: The public key of the party transferring the bandwidth.
        :param limit: The number of transactions to return. (Default: 100)
        :return The latest transactions of the specified public key, or an empty list if no transactions exist.
        """
        db_txs = select(tx for tx in self.BandwidthTransaction
                        if public_key in (tx.public_key_a, tx.public_key_b))\
            .limit(limit)
        return [BandwidthTransactionData.from_db(db_txn) for db_txn in db_txs]

    @db_session
    def get_total_taken(self, public_key: bytes) -> int:
        """
        Return the total amount of bandwidth taken by a given party.
        :param public_key: The public key of the peer of which we want to determine the total taken.
        :return The total amount of bandwidth taken by the specified peer, in bytes.
        """
        return sum(transaction.amount for transaction in self.BandwidthTransaction
                   if transaction.public_key_a == public_key)

    @db_session
    def get_total_given(self, public_key: bytes) -> int:
        """
        Return the total amount of bandwidth given by a given party.
        :param public_key: The public key of the peer of which we want to determine the total given.
        :return The total amount of bandwidth given by the specified peer, in bytes.
        """
        return sum(transaction.amount for transaction in self.BandwidthTransaction
                   if transaction.public_key_b == public_key)

    @db_session
    def get_balance(self, public_key: bytes) -> int:
        """
        Return the bandwidth balance (total given - total taken) of a specific peer.
        :param public_key: The public key of the peer of which we want to determine the balance.
        :return The bandwidth balance the specified peer, in bytes.
        """
        return self.get_total_given(public_key) - self.get_total_taken(public_key)

    def get_my_balance(self) -> int:
        """
        Return your bandwidth balance, which is the total amount given minus the total amount taken.
        :return Your bandwidth balance, in bytes.
        """
        return self.get_balance(self.my_pub_key)

    @db_session
    def get_num_peers_helped(self, public_key: bytes) -> int:
        """
        Return the number of unique peers that a peer with the provided public key has helped.
        :param public_key: The public key of the peer of which we want to determine this number.
        :return The unique number of peers helped by the specified peer.
        """
        result = list(select(count(g.public_key_b) for g in self.BandwidthTransaction if g.public_key_a == public_key))
        return result[0]

    @db_session
    def get_num_peers_helped_by(self, public_key: bytes) -> int:
        """
        Return the number of unique peers that a peer with the provided public key has been helped by.
        :param public_key: The public key of the peer of which we want to determine this number.
        :return The unique number of peers that helped the specified peer.
        """
        result = list(select(count(g.public_key_a) for g in self.BandwidthTransaction if g.public_key_b == public_key))
        return result[0]

    @db_session
    def get_history(self) -> List:
        """
        Get the history of your bandwidth balance as an ordered list.
        :return A list. Each item in this list contains a timestamp and a balance.
        """
        history = []
        for history_item in self.BandwidthHistory.select().order_by(self.BandwidthHistory.timestamp):
            history.append({"timestamp": history_item.timestamp, "balance": history_item.balance})

        return history

    def shutdown(self) -> None:
        """
        Shutdown the database.
        """
        self.database.disconnect()
