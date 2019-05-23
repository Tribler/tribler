from __future__ import absolute_import

from ipv8.database import database_blob

from six import text_type

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.message import Message, TraderId
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress


class Payment(Message):
    """Class representing a payment."""

    def __init__(self, trader_id, transaction_id, transferred_assets, address_from, address_to, payment_id,
                 timestamp, success):
        super(Payment, self).__init__(trader_id, timestamp)
        self._transaction_id = transaction_id
        self._transferred_assets = transferred_assets
        self._address_from = address_from
        self._address_to = address_to
        self._payment_id = payment_id
        self._success = success

    @classmethod
    def from_database(cls, data):
        """
        Create a Payment object based on information in the database.
        """
        (trader_id, transaction_trader_id, transaction_number, payment_id, transferred_amount, transferred_id,
         address_from, address_to, timestamp, success) = data

        transaction_id = TransactionId(TraderId(bytes(transaction_trader_id)), TransactionNumber(transaction_number))
        return cls(TraderId(bytes(trader_id)), transaction_id, AssetAmount(transferred_amount, str(transferred_id)),
                   WalletAddress(str(address_from)), WalletAddress(str(address_to)), PaymentId(str(payment_id)),
                   Timestamp(timestamp), bool(success))

    def to_database(self):
        """
        Returns a database representation of a Payment object.
        :rtype: tuple
        """
        return (database_blob(bytes(self.trader_id)), database_blob(bytes(self.transaction_id.trader_id)),
                int(self.transaction_id.transaction_number), text_type(self.payment_id), self.transferred_assets.amount,
                text_type(self.transferred_assets.asset_id), text_type(self.address_from),
                text_type(self.address_to), int(self.timestamp), self.success)

    @property
    def transaction_id(self):
        return self._transaction_id

    @property
    def transferred_assets(self):
        return self._transferred_assets

    @property
    def address_from(self):
        return self._address_from

    @property
    def address_to(self):
        return self._address_to

    @property
    def payment_id(self):
        return self._payment_id

    @property
    def success(self):
        return self._success

    @classmethod
    def from_network(cls, data):
        """
        Restore a payment from the network

        :param data: PaymentPayload
        :return: Restored payment
        :rtype: Payment
        """
        return cls(
            data.trader_id,
            data.transaction_id,
            data.transferred_assets,
            data.address_from,
            data.address_to,
            data.payment_id,
            data.timestamp,
            data.success
        )

    def to_network(self):
        """
        Return network representation of the multi chain payment
        """
        return (
            self._trader_id,
            self._timestamp,
            self._transaction_id,
            self._transferred_assets,
            self._address_from,
            self._address_to,
            self._payment_id,
            self._success
        )

    def to_dictionary(self):
        return {
            "trader_id": self.transaction_id.trader_id.as_hex(),
            "transaction_number": int(self.transaction_id.transaction_number),
            "transferred": self.transferred_assets.to_dictionary(),
            "payment_id": str(self.payment_id),
            "address_from": str(self.address_from),
            "address_to": str(self.address_to),
            "timestamp": int(self.timestamp),
            "success": self.success
        }
