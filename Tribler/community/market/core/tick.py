import hashlib
import time

from Tribler.Core.Utilities.encoding import encode
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId, Message
from Tribler.community.market.core.order import OrderId, OrderNumber, Order
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.dispersy.crypto import ECCrypto

SIG_LENGTH = 64
PK_LENGTH = 74

EMPTY_SIG = '0'*SIG_LENGTH
EMPTY_PK = '0'*PK_LENGTH


class Tick(Message):
    """
    Abstract message class for representing a order on another node. This tick is replicating the order sitting on
    the node it belongs to.
    """
    TIME_TOLERANCE = 10  # A small tolerance for the timestamp, to account for network delays

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp, is_ask,
                 public_key=EMPTY_PK, signature=EMPTY_SIG):
        """
        Don't use this class directly, use one of the class methods

        :param message_id: A message id to identify the tick
        :param order_id: A order id to identify the order this tick represents
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :param public_key: The public key of the originator of this message
        :param signature: A signature of this message
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        :type public_key: str
        :type signature: str
        """
        super(Tick, self).__init__(message_id, timestamp)

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(public_key, str), type(public_key)
        assert isinstance(signature, str), type(signature)
        assert isinstance(is_ask, bool), type(is_ask)

        self._order_id = order_id
        self._price = price
        self._quantity = quantity
        self._timeout = timeout
        self._is_ask = is_ask
        self._public_key = public_key
        self._signature = signature

    @classmethod
    def from_database(cls, data):
        trader_id, message_number, order_number, price, price_type, quantity, quantity_type, timeout, timestamp,\
        is_ask, public_key, signature = data

        tick_cls = Ask if is_ask else Bid
        message_id = MessageId(TraderId(str(trader_id)), MessageNumber(str(message_number)))
        order_id = OrderId(TraderId(str(trader_id)), OrderNumber(order_number))
        return tick_cls(message_id, order_id, Price(price, str(price_type)), Quantity(quantity, str(quantity_type)),
                        Timeout(timeout), Timestamp(timestamp), str(public_key.decode('hex')),
                        str(signature.decode('hex')))

    def to_database(self):
        return (unicode(self.message_id.trader_id), unicode(self.message_id.message_number),
                int(self.order_id.order_number), float(self.price), unicode(self.price.wallet_id), float(self.quantity),
                unicode(self.quantity.wallet_id), float(self.timeout), float(self.timestamp), self.is_ask(),
                unicode(self._public_key.encode('hex')), unicode(self._signature.encode('hex')))

    @classmethod
    def from_order(cls, order, message_id):
        """
        Create a tick from an order

        :param order: The order that this tick represents
        :param message_id: The message id for the tick
        :return: The created tick
        :rtype: Tick
        """
        assert isinstance(order, Order), type(order)
        assert isinstance(message_id, MessageId), type(message_id)

        if order.is_ask():
            return Ask(message_id, order.order_id, order.price, order.total_quantity - order.traded_quantity,
                       order.timeout, order.timestamp)
        else:
            return Bid(message_id, order.order_id, order.price, order.total_quantity - order.traded_quantity,
                       order.timeout, order.timestamp)

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        """
        :param quantity: The new quantity
        :type quantity: Quantity
        """
        assert isinstance(quantity, Quantity), type(quantity)
        self._quantity = quantity

    @property
    def timeout(self):
        """
        Return when the tick is going to expire
        :rtype: Timeout
        """
        return self._timeout

    def is_ask(self):
        """
        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(self._timestamp) and \
            time.time() >= float(self.timestamp) - self.TIME_TOLERANCE

    def get_sign_data(self):
        return encode((int(self.order_id.order_number), float(self.price), str(self.price.wallet_id),
                       float(self.quantity), str(self.quantity.wallet_id), float(self.timeout), float(self.timestamp)))

    def sign(self, member):
        """
        Sign this tick using a private key.
        :param member: The member that signs this tick
        """
        crypto = ECCrypto()
        self._public_key = member.public_key
        self._signature = crypto.create_signature(member.private_key, self.get_sign_data())

    def has_valid_signature(self):
        crypto = ECCrypto()

        mid_match = hashlib.sha1(self._public_key).digest().encode('hex') == str(self.order_id.trader_id)
        return crypto.is_valid_signature(
            crypto.key_from_public_bin(self._public_key), self.get_sign_data(), self._signature) and mid_match

    def update_timestamp(self):
        """
        Update the timestamp of this tick and set it to the current time.
        """
        self._timestamp = Timestamp.now()

    def to_network(self):
        """
        Return network representation of the tick
        """
        return (
            self._order_id.trader_id,
            self._message_id.message_number,
            self._order_id.order_number,
            self._price,
            self._quantity,
            self._timeout,
            self._timestamp,
            self._public_key,
            self._signature
        )

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this tick.
        """
        return {
            "trader_id": str(self.order_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "message_id": str(self.message_id),
            "price": float(self.price),
            "price_type": self.price.wallet_id,
            "quantity": float(self.quantity),
            "quantity_type": self.quantity.wallet_id,
            "timeout": float(self.timeout),
            "timestamp": float(self.timestamp)
        }


class Ask(Tick):
    """Represents an ask from a order located on another node."""

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp,
                 public_key=EMPTY_PK, signature=EMPTY_SIG):
        """
        :param message_id: A message id to identify the ask
        :param order_id: A order id to identify the order this tick represents
        :param price: A price that needs to be paid for the ask
        :param quantity: The quantity that needs to be sold
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :param public_key: The public key of the originator of this message
        :param signature: A signature of this message
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type public_key: str
        :type signature: str
        """
        super(Ask, self).__init__(message_id, order_id, price, quantity, timeout, timestamp, True, public_key,
                                  signature)

    @classmethod
    def from_network(cls, data):
        """
        Restore an ask from the network

        :param data: OfferPayload
        :return: Restored ask
        :rtype: Ask
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'order_number'), isinstance(data.order_number, OrderNumber)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timeout'), isinstance(data.timeout, Timeout)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)
        assert hasattr(data, 'public_key'), isinstance(data.public_key, str)
        assert hasattr(data, 'signature'), isinstance(data.signature, str)

        return cls(
            MessageId(data.trader_id, data.message_number),
            OrderId(data.trader_id, data.order_number),
            data.price,
            data.quantity,
            data.timeout,
            data.timestamp,
            data.public_key,
            data.signature
        )


class Bid(Tick):
    """Represents a bid from a order located on another node."""

    def __init__(self, message_id, order_id, price, quantity, timeout, timestamp,
                 public_key=EMPTY_PK, signature=EMPTY_SIG):
        """
        :param message_id: A message id to identify the bid
        :param order_id: A order id to identify the order this tick represents
        :param price: A price that you are willing to pay for the bid
        :param quantity: The quantity that you want to buy
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :param public_key: The public key of the originator of this message
        :param signature: A signature of this message
        :type message_id: MessageId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type public_key: str
        :type signature: str
        """
        super(Bid, self).__init__(message_id, order_id, price, quantity, timeout, timestamp, False,
                                  public_key, signature)

    @classmethod
    def from_network(cls, data):
        """
        Restore a bid from the network

        :param data: OfferPayload
        :return: Restored bid
        :rtype: Bid
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'order_number'), isinstance(data.order_number, OrderNumber)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timeout'), isinstance(data.timeout, Timeout)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)
        assert hasattr(data, 'public_key'), isinstance(data.public_key, str)
        assert hasattr(data, 'signature'), isinstance(data.signature, str)

        return cls(
            MessageId(data.trader_id, data.message_number),
            OrderId(data.trader_id, data.order_number),
            data.price,
            data.quantity,
            data.timeout,
            data.timestamp,
            data.public_key,
            data.signature
        )
