from Tribler.community.market.core.message import MessageId, Message, TraderId, MessageNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId
from Tribler.community.market.core.wallet_address import WalletAddress


class Payment(Message):
    """Class representing a payment."""

    def __init__(self, message_id, transaction_id, transferee_quantity, transferee_price,
                 address_from, address_to, payment_id, timestamp, success):
        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(transferee_quantity, Quantity), type(transferee_quantity)
        assert isinstance(transferee_price, Price), type(transferee_price)
        assert isinstance(address_from, WalletAddress), type(address_from)
        assert isinstance(address_to, WalletAddress), type(address_to)
        assert isinstance(payment_id, PaymentId), type(payment_id)
        assert isinstance(success, bool), type(success)

        super(Payment, self).__init__(message_id, timestamp)
        self._transaction_id = transaction_id
        self._transferee_quantity = transferee_quantity
        self._transferee_price = transferee_price
        self._address_from = address_from
        self._address_to = address_to
        self._payment_id = payment_id
        self._success = success

    @classmethod
    def from_database(cls, data):
        """
        Create a Payment object based on information in the database.
        """
        trader_id, message_number, transaction_trader_id, transaction_number, payment_id, transferee_quantity,\
        quantity_type, transferee_price, price_type, address_from, address_to, timestamp, success = data

        message_id = MessageId(TraderId(str(trader_id)), MessageNumber(int(message_number)))
        transaction_id = TransactionId(TraderId(str(transaction_trader_id)), TransactionNumber(transaction_number))
        return cls(message_id, transaction_id, Quantity(transferee_quantity, str(quantity_type)),
                   Price(transferee_price, str(price_type)), WalletAddress(str(address_from)),
                   WalletAddress(str(address_to)), PaymentId(str(payment_id)), Timestamp(float(timestamp)),
                   bool(success))

    def to_database(self):
        """
        Returns a database representation of a Payment object.
        :rtype: tuple
        """
        return (unicode(self.message_id.trader_id), unicode(self.message_id.message_number),
                unicode(self.transaction_id.trader_id), int(self.transaction_id.transaction_number),
                unicode(self.payment_id), float(self.transferee_quantity),
                unicode(self.transferee_quantity.wallet_id), float(self.transferee_price),
                unicode(self.transferee_price.wallet_id), unicode(self.address_from),
                unicode(self.address_to), float(self.timestamp), self.success)

    @property
    def transaction_id(self):
        return self._transaction_id

    @property
    def transferee_quantity(self):
        return self._transferee_quantity

    @property
    def transferee_price(self):
        return self._transferee_price

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
            data.message_id,
            data.transaction_id,
            data.transferee_quantity,
            data.transferee_price,
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
            self._message_id,
            self._timestamp,
            self._transaction_id,
            self._transferee_quantity,
            self._transferee_price,
            self._address_from,
            self._address_to,
            self._payment_id,
            self._success
        )

    def to_dictionary(self):
        return {
            "trader_id": str(self.transaction_id.trader_id),
            "transaction_number": int(self.transaction_id.transaction_number),
            "price": float(self.transferee_price),
            "price_type": self.transferee_price.wallet_id,
            "quantity": float(self.transferee_quantity),
            "quantity_type": self.transferee_quantity.wallet_id,
            "payment_id": str(self.payment_id),
            "address_from": str(self.address_from),
            "address_to": str(self.address_to),
            "timestamp": float(self.timestamp),
            "success": self.success
        }
