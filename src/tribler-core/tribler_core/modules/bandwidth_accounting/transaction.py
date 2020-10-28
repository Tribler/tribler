"""
This file defines the required data structures for the bandwidth accounting mechanism.
Note that we define two different class types of BandwidthTransaction: one for the object that resides outside the
Pony database and another one that represents the class inside Pony.
We make this separation to workaround the fact that Pony does not support objects that are created outside a database
context.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.keyvault.keys import Key
from ipv8.messaging.serialization import default_serializer

from pony.orm import PrimaryKey, Required, db_session

from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.payload import BandwidthTransactionPayload


@dataclass
class BandwidthTransactionData:
    """
    This class defines a data class for a bandwidth transaction.
    """
    sequence_number: int
    public_key_a: bytes
    public_key_b: bytes
    signature_a: bytes
    signature_b: bytes
    amount: int
    timestamp: int = int(round(time.time() * 1000))

    def pack(self, signature_a=True, signature_b=True) -> bytes:
        """
        Encode this block for transport.
        :param signature_a: False to pack EMPTY_SIG in the location of signature A, true to pack the signature A field.
        :param signature_b: False to pack EMPTY_SIG in the location of signature B, true to pack the signature B field.
        :return: the database_blob the data was packed into.
        """
        args = [self.sequence_number, self.public_key_a, self.public_key_b,
                self.signature_a if signature_a else EMPTY_SIGNATURE,
                self.signature_b if signature_b else EMPTY_SIGNATURE, self.amount, self.timestamp]
        return default_serializer.pack_serializable(BandwidthTransactionPayload(*args, 0))

    def sign(self, key: Key, as_a: bool) -> None:
        """
        Signs this block with the given key
        :param key: The key to sign this block with.
        :param as_a: Whether we are signing this block as party A or B.
        """
        if as_a:
            # Party A is the first to sign the transaction
            self.signature_a = default_eccrypto.create_signature(
                key, self.pack(signature_a=False, signature_b=False))
        else:
            # Party B is the first to sign the transaction
            self.signature_b = default_eccrypto.create_signature(
                key, self.pack(signature_b=False))

    def is_valid(self) -> bool:
        """
        Validate the signatures in the transaction.
        return: True if the transaction is valid, False otherwise
        """
        if self.signature_a != EMPTY_SIGNATURE:
            # Verify signature A
            pck = self.pack(signature_a=False, signature_b=False)
            valid_signature = default_eccrypto.is_valid_signature(
                default_eccrypto.key_from_public_bin(self.public_key_a), pck, self.signature_a)
            if not valid_signature:
                return False

        if self.signature_b != EMPTY_SIGNATURE:
            # Verify signature B
            pck = self.pack(signature_b=False)
            valid_signature = default_eccrypto.is_valid_signature(
                default_eccrypto.key_from_public_bin(self.public_key_b), pck, self.signature_b)
            if not valid_signature:
                return False

        if self.sequence_number < 1:
            return False

        return True

    @classmethod
    def from_payload(cls, payload: BandwidthTransactionPayload) -> BandwidthTransaction:  # noqa: F821
        """
        Create a block according to a given payload.
        This method can be used when receiving a block from the network.
        :param payload: The payload to convert to a transaction.
        :return A BandwidthTransaction, constructed from the provided payload.
        """
        return cls(payload.sequence_number, payload.public_key_a, payload.public_key_b,
                   payload.signature_a, payload.signature_b, payload.amount, payload.timestamp)

    @classmethod
    def from_db(cls, db_obj: BandwidthTransaction) -> BandwidthTransactionData:  # noqa: F821
        """
        Return a BandwidthTransaction object from a database object.
        :param db_obj: The database object to convert.
        :return A BandwidthTransaction object, based on the database object.
        """
        return BandwidthTransactionData(db_obj.sequence_number, db_obj.public_key_a, db_obj.public_key_b,
                                        db_obj.signature_a, db_obj.signature_b, db_obj.amount, db_obj.timestamp)

    def get_db_kwargs(self) -> Dict:
        """
        Return the database arguments for easy insertion in a Pony database.
        :return A dictionary with keyword arguments for database insertion.
        """
        return {
            "sequence_number": self.sequence_number,
            "public_key_a": self.public_key_a,
            "public_key_b": self.public_key_b,
            "signature_a": self.signature_a,
            "signature_b": self.signature_b,
            "amount": self.amount,
            "timestamp": self.timestamp
        }


def define_binding(bandwidth_database):
    db = bandwidth_database.database

    class BandwidthTransaction(db.Entity):
        """
        This class describes a bandwidth transaction that resides in the database.
        """
        sequence_number = Required(int)
        public_key_a = Required(bytes, index=True)
        public_key_b = Required(bytes, index=True)
        signature_a = Required(bytes)
        signature_b = Required(bytes)
        amount = Required(int, size=64)
        timestamp = Required(int, size=64)
        PrimaryKey(sequence_number, public_key_a, public_key_b)

        @classmethod
        @db_session
        def insert(cls, transaction: BandwidthTransaction) -> None:
            """
            Insert a BandwidthTransaction object in the database.
            Remove the last transaction with that specific counterparty while doing so.
            :param transaction: The transaction to insert in the database.
            """
            for tx in cls.select(
                    lambda c: c.public_key_a == transaction.public_key_a and
                              c.public_key_b == transaction.public_key_b):
                tx.delete()
            db.commit()
            cls(**transaction.get_db_kwargs())

            if transaction.public_key_a == bandwidth_database.my_pub_key or \
                    transaction.public_key_b == bandwidth_database.my_pub_key:
                # Update the balance history
                timestamp = int(round(time.time() * 1000))
                db.BandwidthHistory(timestamp=timestamp, balance=bandwidth_database.get_my_balance())
                num_entries = db.BandwidthHistory.select().count()
                if num_entries > bandwidth_database.MAX_HISTORY_ITEMS:
                    # Delete the entry with the lowest timestamp
                    entry = list(db.BandwidthHistory.select().order_by(db.BandwidthHistory.timestamp))[0]
                    entry.delete()

    return BandwidthTransaction
