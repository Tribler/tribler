from pathlib import Path
from typing import List

from pony.orm import Database, count, db_session, select, sum

from tribler_core.modules.bandwidth_accounting import history, misc, transaction
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData


class BandwidthDatabase:
    """
    Simple database that stores bandwidth transactions in Tribler as a work graph.
    """
    CURRENT_DB_VERSION = 8
    MAX_HISTORY_ITEMS = 100  # The maximum number of history items to store.

    def __init__(self, db_path: Path, my_pub_key: bytes) -> None:
        """
        Sets up the persistence layer ready for use.
        :param db_path: The full path of the database.
        :param my_pub_key: The public key of the user operating the database.
        """
        self.db_path = db_path
        self.my_pub_key = my_pub_key
        create_db = str(db_path) == ":memory:" or not self.db_path.is_file()
        self.database = Database()

        self.MiscData = misc.define_binding(self.database)
        self.BandwidthTransaction = transaction.define_binding(self)
        self.BandwidthHistory = history.define_binding(self)

        self.database.bind(provider='sqlite', filename=str(db_path), create_db=create_db, timeout=120.0)
        self.database.generate_mapping(create_tables=create_db)

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(self.CURRENT_DB_VERSION))

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
