import datetime
import time
from decimal import Decimal


class TraderId(object):
    """Immutable class for representing the id of a trader."""

    def __init__(self, trader_id):
        """
        Initialise the trader id

        :param trader_id: String representing the trader id
        :type trader_id: str
        """
        super(TraderId, self).__init__()

        assert isinstance(trader_id, str), type(trader_id)

        self._trader_id = trader_id

    def __str__(self):
        """
        Return the string representation of the trader id

        :return: The string representation of the trader id
        :rtype: str
        """
        return "%s" % self._trader_id

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, TraderId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._trader_id == \
                   other._trader_id

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._trader_id)


class MessageNumber(object):
    """Immutable class for representing the number of a message."""

    def __init__(self, message_number):
        """
        Initialise the message number

        :param message_number: String representing the number of a message
        :type message_number: str
        """
        super(MessageNumber, self).__init__()

        assert isinstance(message_number, str), type(message_number)

        self._message_number = message_number

    def __str__(self):
        """
        Return the string representation of the message number

        :return: The string representation of the message number
        :rtype: str
        """
        return "%s" % self._message_number

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, MessageNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._message_number == \
                   other._message_number

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._message_number)


class MessageId(object):
    """Immutable class for representing the id of a message."""

    def __init__(self, trader_id, message_number):
        """
        Initialise the message id

        :param trader_id: The trader id who created the message
        :param message_number: The number of the message created
        :type trader_id: TraderId
        :type message_number: MessageNumber
        """
        super(MessageId, self).__init__()

        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(message_number, MessageNumber), type(message_number)

        self._trader_id = trader_id
        self._message_number = message_number

    @property
    def trader_id(self):
        """
        Return the trader id

        :return: The trader id of the message id
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def message_number(self):
        """
        Return the message number

        :return: The message number of the message id
        :rtype: MessageNumber
        """
        return self._message_number

    def __str__(self):
        """
        Return the string representation of the message id

        format: <trader_id>.<message_number>

        :return: The string representation of the message id
        :rtype: str
        """
        return "%s.%s" % (self._trader_id, self._message_number)

    def __eq__(self, other):
        """
        Check if two objects are the same

        :param other: An object to compare with
        :return: True if the object is the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, MessageId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._message_number) == \
                   (other._trader_id, other._message_number)

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the object is not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash((self._trader_id, self._message_number))


class Price(object):
    """Immutable class for representing a price."""

    def __init__(self, price):
        """
        Initialise the price

        Don't call this method directly, but use one of the factory methods: from_mil, from_float

        :param price: Integer representation of a price that is positive or zero
        :type price: int
        """
        super(Price, self).__init__()

        assert isinstance(price, int), type(price)

        if price < 0:
            raise ValueError("Price can not be negative")

        self._price = price

    @classmethod
    def from_mil(cls, mil_price):
        """
        Create a price from a mil format

        A mil is 0.0001 of a price unit

        :param mil_price: A mil price (mil = 0.0001)
        :type mil_price: int
        :return: The price
        :rtype: Price
        """
        return cls(mil_price)

    @classmethod
    def from_float(cls, float_price):
        """
        Create a price from a float format

        :param float_price: A float representation of a price
        :type float_price: float
        :return: The price
        :rtype: Price
        """
        price = int(Decimal(str(float_price)) * Decimal('10000'))
        return cls(price)

    def __int__(self):
        """
        Return the integer representation of the price

        :return: The string representation of the price
        :rtype: integer
        """
        return self._price

    def __str__(self):
        """
        Return the string representation of the price in mil units

        :return: The string representation of the price in mil units
        :rtype: str
        """
        return "%s" % (Decimal(str(self._price)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        """
        Add two prices together and return a new object with that amount

        :param other: A price object to add to the current price
        :type other: Price
        :return: The new price when both prices are added
        :rtype: Price
        """
        if isinstance(other, Price):
            return Price.from_mil(self._price + other._price)
        else:
            return NotImplemented

    def __iadd__(self, other):
        """
        Add two prices together and return a new object with that amount

        :param other: A price object to add to the current price
        :type other: Price
        :return: The new price when both prices are added
        :rtype: Price
        """
        return self.__add__(other)

    def __sub__(self, other):
        """
        Subtract two prices from each other and return a new object with that amount

        :param other: A price object to subtract from the current price
        :type other: Price
        :return: The new price when the second price is subtracted from the first
        :rtype: Price
        """
        if isinstance(other, Price):
            return Price.from_mil(self._price - other._price)
        else:
            return NotImplemented

    def __isub__(self, other):
        """
        Subtract two prices from each other and return a new object with that amount

        :param other: A price object to subtract from the current price
        :type other: Price
        :return: The new price when the second price is subtracted from the first
        :rtype: Price
        """
        return self.__sub__(other)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price < other._price
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price <= other._price
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Price):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._price == \
                   other._price

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __gt__(self, other):
        """
        Check if the supplied object is greater than this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price > other._price
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Price):
            return self._price >= other._price
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._price)


class Quantity(object):
    """Immutable class for representing quantity."""

    def __init__(self, quantity):
        """
        Initialise the quantity

        Don't call this method directly, but use one of the factory methods: from_mil, from_float

        :param quantity: Integer representation of a quantity that is positive or zero
        :type quantity: int
        """
        super(Quantity, self).__init__()

        assert isinstance(quantity, int), type(quantity)

        if quantity < 0:
            raise ValueError("Quantity must be positive")

        self._quantity = quantity

    @classmethod
    def from_mil(cls, mil_quantity):
        """
        Create a quantity from a mil format

        A mil is 0.0001 of a quantity unit

        :param mil_quantity: A mil quantity (mil = 0.0001)
        :type mil_quantity: int
        :return: The quantity
        :rtype: Quantity
        """
        return cls(mil_quantity)

    @classmethod
    def from_float(cls, float_quantity):
        """
        Create a quantity from a float format

        :param float_quantity: A float representation of a quantity
        :type float_quantity: float
        :return: The quantity
        :rtype: Quantity
        """
        quantity = int(Decimal(str(float_quantity)) * Decimal('10000'))
        return cls(quantity)

    def __int__(self):
        """
        Return the integer representation of the quantity

        :return: The string representation of the quantity
        :rtype: integer
        """
        return self._quantity

    def __str__(self):
        """
        Return the string representation of the quantity in mil units

        :return: The string representation of the quantity in mil units
        :rtype: str
        """
        return "%s" % (Decimal(str(self._quantity)) / Decimal('10000')).quantize(Decimal('0.0001'))

    def __add__(self, other):
        """
        Add two quantities together and return a new object with that amount

        :param other: A quantity object to add to the current quantity
        :type other: Quantity
        :return: The new quantity when both quantities are added
        :rtype: Quantity
        """
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity + other._quantity)
        else:
            return NotImplemented

    def __iadd__(self, other):
        """
        Add two quantities together and return a new object with that amount

        :param other: A quantity object to add to the current quantity
        :type other: Quantity
        :return: The new quantity when both quantities are added
        :rtype: Quantity
        """
        return self.__add__(other)

    def __sub__(self, other):
        """
        Subtract two quantities from each other and return a new object with that amount

        :param other: A quantity object to subtract from the current quantity
        :type other: Quantity
        :return: The new quantity when the second quantity is subtracted from the first
        :rtype: Quantity
        """
        if isinstance(other, Quantity):
            return Quantity.from_mil(self._quantity - other._quantity)
        else:
            return NotImplemented

    def __isub__(self, other):
        """
        Subtract two quantities from each other and return a new object with that amount

        :param other: A quantity object to subtract from the current quantity
        :type other: Quantity
        :return: The new quantity when the second quantity is subtracted from the first
        :rtype: Quantity
        """
        return self.__sub__(other)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity < other._quantity
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity <= other._quantity
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Quantity):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._quantity == \
                   other._quantity

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __gt__(self, other):
        """
        Check if the supplied object is greater than this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity > other._quantity
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Quantity):
            return self._quantity >= other._quantity
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._quantity)


class Timeout(object):
    """Immutable class for representing a timeout."""

    def __init__(self, timeout):
        """
        Initialise the timeout

        :param timeout: Float representation of a timeout
        :type timeout: float
        """
        super(Timeout, self).__init__()

        assert isinstance(timeout, float), type(timeout)

        if timeout < 0:
            raise ValueError("Timeout can not be negative")

        self._timeout = timeout

    def is_timed_out(self, timestamp):
        """
        Return if a timeout has occurred

        :param timestamp: A timestamp
        :type timestamp: Timestamp
        :return: True if timeout has occurred, False otherwise
        :rtype: bool
        """
        assert isinstance(timestamp, Timestamp), type(timestamp)

        if self._timeout < timestamp:
            return True
        else:
            return False

    def __float__(self):
        """
        Return the float representation of the timeout

        :return: The float representation of the timeout
        :rtype: float
        """
        return self._timeout

    def __str__(self):
        """
        Return the string representation of the timeout

        :return: The string representation of the timeout
        :rtype: str
        """
        return "%s" % datetime.datetime.fromtimestamp(self._timeout)

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._timeout)


class Timestamp(object):
    """Immutable class for representing a timestamp."""

    def __init__(self, timestamp):
        """
        Initialise the timestamp

        :param timestamp: Float representation of a timestamp
        :type timestamp: float
        """
        super(Timestamp, self).__init__()

        assert isinstance(timestamp, float), type(timestamp)

        if timestamp < 0:
            raise ValueError("Timestamp can not be negative")

        self._timestamp = timestamp

    @classmethod
    def now(cls):
        """
        Create a timestamp with the time set to the current time

        :return: A timestamp
        :rtype: Timestamp
        """
        return cls(time.time())

    def __float__(self):
        """
        Return the float representation of the timestamp

        :return: The float representation of the timestamp
        :rtype: float
        """
        return self._timestamp

    def __str__(self):
        """
        Return the string representation of the timestamp

        :return: The string representation of the timestamp
        :rtype: str
        """
        return "%s" % datetime.datetime.fromtimestamp(self._timestamp)

    def __lt__(self, other):
        """
        Check if the supplied object is less than this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp < other._timestamp
        if isinstance(other, float):
            return self._timestamp < other
        else:
            return NotImplemented

    def __le__(self, other):
        """
        Check if the supplied object is less than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is lower or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp <= other._timestamp
        if isinstance(other, float):
            return self._timestamp <= other
        else:
            return NotImplemented

    def __eq__(self, other):
        """
        Check if two object are the same

        :param other: An object to compare with
        :return: True if the objects are the same, False otherwise
        :rtype: bool
        """
        if not isinstance(other, Timestamp):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._timestamp == \
                   other._timestamp

    def __ne__(self, other):
        """
        Check if two objects are not the same

        :param other: An object to compare with
        :return: True if the objects are not the same, False otherwise
        :rtype: bool
        """
        return not self.__eq__(other)

    def __gt__(self, other):
        """
        Check if the supplied object is greater than this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp > other._timestamp
        if isinstance(other, float):
            return self._timestamp > other
        else:
            return NotImplemented

    def __ge__(self, other):
        """
        Check if the supplied object is greater than or equal to this object

        :param other: An object to compare with
        :return: True if the supplied objects is bigger or equal, False otherwise
        :rtype: bool
        """
        if isinstance(other, Timestamp):
            return self._timestamp >= other._timestamp
        if isinstance(other, float):
            return self._timestamp >= other
        else:
            return NotImplemented

    def __hash__(self):
        """
        Return the hash value of this object

        :return: The hash value
        :rtype: integer
        """
        return hash(self._timestamp)


class Message(object):
    """Abstract class for representing a message."""

    def __init__(self, message_id, timestamp, is_tick):
        """
        Initialise the message

        Don't use this class directly

        :param message_id: A message id to identify the message
        :param timestamp: A timestamp when the message was created
        :param is_tick: A bool to indicate if this message is a tick
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type is_tick: bool
        """
        super(Message, self).__init__()

        assert isinstance(message_id, MessageId), type(message_id)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        assert isinstance(is_tick, bool), type(is_tick)

        self._message_id = message_id
        self._timestamp = timestamp
        self._is_tick = is_tick

    @property
    def message_id(self):
        """
        Return the message id of the message

        :return: The message id
        :rtype: MessageId
        """
        return self._message_id

    @property
    def timestamp(self):
        """
        Return the timestamp of the message

        :return: The timestamp
        :rtype: Timestamp
        """
        return self._timestamp

    def is_tick(self):
        """
        Return if the message is a tick

        :return: True if message is a tick, False otherwise
        :rtype: bool
        """
        return self._is_tick


class Tick(Message):
    """Abstract class for representing a tick."""

    def __init__(self, message_id, price, quantity, timeout, timestamp, is_ask):
        """
        Initialise the tick

        Don't use this class directly

        :param message_id: A message id to identify the tick
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :type message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        """
        super(Tick, self).__init__(message_id, timestamp, True)

        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(is_ask, bool), type(is_ask)

        self._price = price
        self._quantity = quantity
        self._timeout = timeout
        self._is_ask = is_ask

    @property
    def price(self):
        """
        Return the price of the tick

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity of the tick

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        """
        Set the quantity of the tick

        :param quantity: The new quantity
        :type quantity: Quantity
        """
        assert isinstance(quantity, Quantity), type(quantity)
        self._quantity = quantity

    @property
    def timeout(self):
        """
        Return when the tick is going to expire

        :return: The timeout
        :rtype: Timeout
        """
        return self._timeout

    def is_ask(self):
        """
        Return if this tick is an ask

        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    def is_valid(self):
        """
        Return if the tick is still valid

        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(Timestamp.now())

    def to_network(self):
        """
        Return network representation of the tick

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <price>, <quantity>, <timeout>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            str(self._message_id.trader_id),
            str(self._message_id.message_number),
            int(self._price),
            int(self._quantity),
            float(self._timeout),
            float(self._timestamp),
        )


class Ask(Tick):
    """Class representing an ask."""

    def __init__(self, message_id, price, quantity, timeout, timestamp):
        """
        Initialise the ask

        :param message_id: A message id to identify the ask
        :param price: A price that needs to be paid for the ask
        :param quantity: The quantity that needs to be sold
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :type message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Ask, self).__init__(message_id, price, quantity, timeout, timestamp, True)

    @classmethod
    def create(cls, message_id, price, quantity, timeout, timestamp):
        """
        Create an ask

        :param message_id: A message id to identify the ask
        :param price: A price that needs to be paid for the ask
        :param quantity: The quantity that needs to be sold
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :type message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        return cls(message_id, price, quantity, timeout, timestamp)

    @classmethod
    def from_network(cls, data):
        """
        Restore an ask from the network

        :param data: object with (trader_id, message_number, price, quantity, timeout, timestamp) properties
        :return: Restored ask
        :rtype: Ask
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timeout')
        assert hasattr(data, 'timestamp')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timeout(data.timeout),
            Timestamp(data.timestamp),
        )


class Bid(Tick):
    """Class representing a bid."""

    def __init__(self, message_id, price, quantity, timeout, timestamp):
        """
        Initialise the bid

        :param message_id: A message id to identify the bid
        :param price: A price that you are willing to pay for the bid
        :param quantity: The quantity that you want to buy
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :type message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Bid, self).__init__(message_id, price, quantity, timeout, timestamp, False)

    @classmethod
    def create(cls, message_id, price, quantity, timeout, timestamp):
        """
        Create a bid

        :param message_id: A message id to identify the bid
        :param price: A price that you are willing to pay for the bid
        :param quantity: The quantity that you want to buy
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :type message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        return cls(message_id, price, quantity, timeout, timestamp)

    @classmethod
    def from_network(cls, data):
        """
        Restore a bid from the network

        :param data: object with (trader_id, message_number, price, quantity, timeout, timestamp) properties
        :return: Restored bid
        :rtype: Bid
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timeout')
        assert hasattr(data, 'timestamp')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timeout(data.timeout),
            Timestamp(data.timestamp),
        )


class Trade(Message):
    """Abstract class representing a trade."""

    def __init__(self, message_id, recipient_message_id, timestamp, quick, proposed, accepted):
        """
        Initialise the trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param recipient_message_id: A message id to identify the traded party
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :param proposed: A bool to indicate if this trade is proposed
        :param accepted: A bool to indicate if this trade is accepted
        :type message_id: MessageId
        :type recipient_message_id: MessageId
        :type timestamp: Timestamp
        :type quick: bool
        :type proposed: bool
        :type accepted: bool
        """
        super(Trade, self).__init__(message_id, timestamp, False)

        assert isinstance(recipient_message_id, MessageId), type(recipient_message_id)
        assert isinstance(proposed, bool), type(proposed)
        assert isinstance(accepted, bool), type(accepted)
        assert isinstance(quick, bool), type(quick)

        self._recipient_message_id = recipient_message_id
        self._proposed = proposed
        self._accepted = accepted
        self._quick = quick

    @classmethod
    def propose(cls, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp):
        """
        Propose a trade

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type recipient_message_id: MessageId
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            sender_message_id,
            recipient_message_id,
            price,
            quantity,
            timestamp,
            False
        )

    @classmethod
    def quick_propose(cls, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp):
        """
        Propose a quick-trade

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            sender_message_id,
            recipient_message_id,
            price,
            quantity,
            timestamp,
            True
        )

    @classmethod
    def accept(cls, message_id, timestamp, proposed_trade):
        """
        Accept a trade

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp when the trade was accepted
        :param proposed_trade: A proposed trade that needs to be accepted
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: An accepted trade
        :rtype: AcceptedTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return AcceptedTrade(
            message_id,
            proposed_trade.sender_message_id,
            proposed_trade.recipient_message_id,
            proposed_trade.price,
            proposed_trade.quantity,
            timestamp,
            proposed_trade.is_quick()
        )

    @classmethod
    def decline(cls, message_id, timestamp, proposed_trade):
        """
        Decline a trade

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp when the trade was declined
        :param proposed_trade: A proposed trade that needs to be declined
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: A declined trade
        :rtype: DeclinedTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return DeclinedTrade(
            message_id,
            proposed_trade.recipient_message_id,
            timestamp,
            proposed_trade.is_quick()
        )

    @property
    def recipient_message_id(self):
        """
        Return the message id of the party to trade with

        :return: The message id
        :rtype: MessageId
        """
        return self._recipient_message_id

    def is_proposed(self):
        """
        Return if this trade was proposed

        :return: True if this trade was proposed, False otherwise
        :rtype: bool
        """
        return self._proposed

    def is_accepted(self):
        """
        Return if this trade was accepted

        :return: True if this trade was accepted, False otherwise
        :rtype: bool
        """
        return self._accepted

    def is_quick(self):
        """
        Return if this trade was a quick-trade

        :return: True if this trade was a quick-trade, False otherwise
        :rtype: bool
        """
        return self._quick

    def to_network(self):
        return NotImplemented


class ProposedTrade(Trade):
    """Class representing a proposed trade."""

    def __init__(self, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp, quick):
        """
        Initialise a proposed trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(ProposedTrade, self).__init__(message_id, recipient_message_id, timestamp, quick, True, False)

        assert isinstance(sender_message_id, MessageId), type(sender_message_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._sender_message_id = sender_message_id
        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a proposed trade from the network

        :param data: object with (trader_id, message_number, sender_trader_id, sender_message_number, recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick) properties
        :return: Restored proposed trade
        :rtype: ProposedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'sender_trader_id')
        assert hasattr(data, 'sender_message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.sender_trader_id), MessageNumber(data.sender_message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def sender_message_id(self):
        """
        Return the message id of the sender party

        :return: The message id
        :rtype: MessageId
        """
        return self._sender_message_id

    @property
    def price(self):
        """
        Return the price

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of a proposed trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <sender_trader_id>, <sender_message_number>, <recipient_trader_id>, <recipient_message_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_message_id.trader_id)]
        ), (
                   str(self._message_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._sender_message_id.trader_id),
                   str(self._sender_message_id.message_number),
                   str(self._recipient_message_id.trader_id),
                   str(self._recipient_message_id.message_number),
                   int(self._price),
                   int(self._quantity),
                   float(self._timestamp),
                   bool(self._quick)
               )


class AcceptedTrade(Trade):
    """Class representing an accepted trade."""

    def __init__(self, message_id, sender_message_id, recipient_message_id, price, quantity, timestamp, quick):
        """
        Initialise an accepted trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param sender_message_id: A message id to identify the sending party
        :param recipient_message_id: A message id to identify the traded party
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type sender_message_id: MessageId
        :type recipient_message_id: MessageId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(AcceptedTrade, self).__init__(message_id, recipient_message_id, timestamp, quick, False, True)

        assert isinstance(sender_message_id, MessageId), type(sender_message_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._sender_message_id = sender_message_id
        self._price = price
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore an accepted trade from the network

        :param data: object with (trader_id, message_number, sender_trader_id, sender_message_number, recipient_trader_id, recipient_message_number, price, quantity, timestamp, quick) properties
        :return: Restored accepted trade
        :rtype: AcceptedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'sender_trader_id')
        assert hasattr(data, 'sender_message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'price')
        assert hasattr(data, 'quantity')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.sender_trader_id), MessageNumber(data.sender_message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Price.from_mil(data.price),
            Quantity(data.quantity),
            Timestamp(data.timestamp),
            data.quick
        )

    @property
    def sender_message_id(self):
        """
        Return the message id of the sender party

        :return: The message id
        :rtype: MessageId
        """
        return self._sender_message_id

    @property
    def price(self):
        """
        Return the price

        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        Return the quantity

        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of an accepted trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <sender_trader_id>, <sender_message_number>, <recipient_trader_id>, <recipient_message_number>, <price>, <quantity>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            str(self._message_id.trader_id),
            str(self._message_id.message_number),
            str(self._sender_message_id.trader_id),
            str(self._sender_message_id.message_number),
            str(self._recipient_message_id.trader_id),
            str(self._recipient_message_id.message_number),
            int(self._price),
            int(self._quantity),
            float(self._timestamp),
            bool(self._quick)
        )


class DeclinedTrade(Trade):
    """Class representing a declined trade."""

    def __init__(self, message_id, declined_message_id, timestamp, quick):
        """
        Initialise a declined trade

        Don't use this method directly

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp wen this trade was created
        :param quick: A bool to indicate if this trade was a quick-trade
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type quick: bool
        """
        super(DeclinedTrade, self).__init__(message_id, declined_message_id, timestamp, quick, False, False)

    @classmethod
    def from_network(cls, data):
        """
        Restore a declined trade from the network

        :param data: object with (trader_id, message_number, recipient_trader_id, recipient_message_number, timestamp, quick) properties
        :return: Restored declined trade
        :rtype: DeclinedTrade
        """
        assert hasattr(data, 'trader_id')
        assert hasattr(data, 'message_number')
        assert hasattr(data, 'recipient_trader_id')
        assert hasattr(data, 'recipient_message_number')
        assert hasattr(data, 'timestamp')
        assert hasattr(data, 'quick')

        return cls(
            MessageId(TraderId(data.trader_id), MessageNumber(data.message_number)),
            MessageId(TraderId(data.recipient_trader_id), MessageNumber(data.recipient_message_number)),
            Timestamp(data.timestamp),
            data.quick
        )

    def to_network(self):
        """
        Return network representation of a declined trade

        :return: tuple(<destination public identifiers>),tuple(<trader_id>, <message_number>, <recipient_trader_id>, <recipient_message_number>, <timestamp>, <quick>)
        :rtype: tuple, tuple
        """
        return tuple(
            [str(self._recipient_message_id.trader_id)]
        ), (
                   str(self._message_id.trader_id),
                   str(self._message_id.message_number),
                   str(self._recipient_message_id.trader_id),
                   str(self._recipient_message_id.message_number),
                   float(self._timestamp),
                   bool(self._quick)
               )
