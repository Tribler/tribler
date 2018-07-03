import logging
from decimal import Decimal

from Tribler.community.market.core.message import TraderId, Message
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import ProposedTrade
from Tribler.community.market.core.wallet_address import WalletAddress


class TransactionNumber(object):
    """Used for having a validated instance of a transaction number that we can easily check if it still valid."""

    def __init__(self, transaction_number):
        """
        :type transaction_number: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TransactionNumber, self).__init__()

        if not isinstance(transaction_number, int):
            raise ValueError("Transaction number must be an integer")

        self._transaction_number = transaction_number

    def __int__(self):
        return self._transaction_number

    def __str__(self):
        return "%s" % self._transaction_number

    def __eq__(self, other):
        if not isinstance(other, TransactionNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._transaction_number == \
                   other._transaction_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._transaction_number)


class TransactionId(object):
    """Used for having a validated instance of a transaction id that we can easily check if it still valid."""

    def __init__(self, trader_id, transaction_number):
        """
        :param trader_id: The trader id who created the order
        :param transaction_number: The number of the transaction created
        :type trader_id: TraderId
        :type transaction_number: TransactionNumber
        """
        super(TransactionId, self).__init__()

        self._trader_id = trader_id
        self._transaction_number = transaction_number

    @property
    def trader_id(self):
        """
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def transaction_number(self):
        """
        :rtype: TransactionNumber
        """
        return self._transaction_number

    def __str__(self):
        """
        format: <trader_id>.<transaction_number>
        """
        return "%s.%s" % (self.trader_id, self.transaction_number)

    def __eq__(self, other):
        if not isinstance(other, TransactionId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self.trader_id, self.transaction_number) == \
                   (other.trader_id, other.transaction_number)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._trader_id, self.transaction_number))


class Transaction(object):
    """Class for representing a transaction between two nodes"""

    def __init__(self, transaction_id, price, quantity, order_id, partner_order_id, timestamp):
        """
        :param transaction_id: An transaction id to identify the order
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param order_id: The id of your order for this transaction
        :param partner_order_id: The id of the order of the other party
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type price: Price
        :type quantity: Quantity
        :type order_id: OrderId
        :type partner_order_id: OrderId
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._transaction_id = transaction_id
        self._price = price
        self._transferred_price = Price(0, price.wallet_id)
        self._total_price = Price(float(price) * float(quantity), price.wallet_id)
        self._quantity = quantity
        self._transferred_quantity = Quantity(0, quantity.wallet_id)
        self._order_id = order_id
        self._partner_order_id = partner_order_id
        self._timestamp = timestamp

        self.sent_wallet_info = False
        self.received_wallet_info = False
        self.incoming_address = None
        self.outgoing_address = None
        self.partner_incoming_address = None
        self.partner_outgoing_address = None
        self.match_id = ''

        self._payments = []
        self._current_payment = 0

    @classmethod
    def from_database(cls, data, payments):
        """
        Create a Transaction object based on information in the database.
        """
        trader_id, transaction_number, order_trader_id, order_number, partner_trader_id, partner_order_number, price,\
        price_type, transferred_price, quantity, quantity_type, transferred_quantity, transaction_timestamp,\
        sent_wallet_info, received_wallet_info, incoming_address, outgoing_address, partner_incoming_address,\
        partner_outgoing_address, match_id = data

        transaction_id = TransactionId(TraderId(str(trader_id)), TransactionNumber(transaction_number))
        transaction = cls(transaction_id, Price(price, str(price_type)),
                          Quantity(quantity, str(quantity_type)), OrderId(TraderId(str(order_trader_id)),
                                                                          OrderNumber(order_number)),
                          OrderId(TraderId(str(partner_trader_id)), OrderNumber(partner_order_number)),
                          Timestamp(float(transaction_timestamp)))

        transaction._transferred_price = Price(transferred_price, str(price_type))
        transaction._transferred_quantity = Quantity(transferred_quantity, str(quantity_type))
        transaction.sent_wallet_info = sent_wallet_info
        transaction.received_wallet_info = received_wallet_info
        transaction.incoming_address = WalletAddress(str(incoming_address))
        transaction.outgoing_address = WalletAddress(str(outgoing_address))
        transaction.partner_incoming_address = WalletAddress(str(partner_incoming_address))
        transaction.partner_outgoing_address = WalletAddress(str(partner_outgoing_address))
        transaction.match_id = str(match_id)
        transaction._payments = payments

        return transaction

    def to_database(self):
        """
        Returns a database representation of a Transaction object.
        :rtype: tuple
        """
        return (unicode(self.transaction_id.trader_id), int(self.transaction_id.transaction_number),
                unicode(self.order_id.trader_id), int(self.order_id.order_number),
                unicode(self.partner_order_id.trader_id), int(self.partner_order_id.order_number), float(self.price),
                unicode(self.price.wallet_id), float(self.transferred_price), float(self.total_quantity),
                unicode(self.total_quantity.wallet_id), float(self.transferred_quantity), float(self.timestamp),
                self.sent_wallet_info, self.received_wallet_info, unicode(self.incoming_address),
                unicode(self.outgoing_address), unicode(self.partner_incoming_address),
                unicode(self.partner_outgoing_address), unicode(self.match_id))

    @classmethod
    def from_proposed_trade(cls, proposed_trade, transaction_id):
        """
        :param proposed_trade: The proposed trade to create the transaction for
        :param transaction_id: The transaction id to use for this transaction
        :type proposed_trade: ProposedTrade
        :type transaction_id: TransactionId
        :return: The created transaction
        :rtype: Transaction
        """
        return cls(transaction_id, proposed_trade.price, proposed_trade.quantity, proposed_trade.recipient_order_id,
                   proposed_trade.order_id, proposed_trade.timestamp)

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._price

    @property
    def total_price(self):
        """
        :rtype: Price
        """
        return self._total_price

    @property
    def transferred_price(self):
        """
        :rtype: Price
        """
        return self._transferred_price

    @property
    def total_quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @property
    def transferred_quantity(self):
        """
        :rtype: Quantity
        """
        return self._transferred_quantity

    @property
    def order_id(self):
        """
        Return the id of your order
        :rtype: OrderId
        """
        return self._order_id

    @property
    def partner_order_id(self):
        """
        :rtype: OrderId
        """
        return self._partner_order_id

    @property
    def payments(self):
        """
        :rtype: [Payment]
        """
        return self._payments

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    @property
    def status(self):
        """
        Return the status of this transaction, can be one of these: "pending", "completed", "error".
        :rtype: str
        """
        if len([payment for payment in self.payments if not payment.success]):
            return "error"
        return "completed" if self.is_payment_complete() else "pending"

    @staticmethod
    def unitize(amount, min_unit):
        """
        Return an a amount that is a multiple of min_unit.
        """
        if Decimal(str(amount)) % Decimal(str(min_unit)) == Decimal(0):
            return amount

        return (int(amount / min_unit) + 1) * min_unit

    def add_payment(self, payment):
        self._logger.debug("Adding price %s and quantity %s to transaction %s",
                           payment.transferee_price, payment.transferee_quantity, self.transaction_id)
        self._transferred_quantity += payment.transferee_quantity
        self._transferred_price += payment.transferee_price
        self._logger.debug("Transferred price: %s, transferred quantity: %s",
                           self.transferred_price, self.transferred_quantity)
        self._payments.append(payment)

    def last_payment(self, is_ask):
        for payment in reversed(self._payments):
            if is_ask and float(payment.transferee_quantity) > 0:
                return payment
            elif not is_ask and float(payment.transferee_price) > 0:
                return payment
        return None

    def next_payment(self, order_is_ask, min_unit, incremental):
        if not incremental:
            # Don't use incremental payments, just return the full amount
            ret_val = self.total_quantity if order_is_ask else self.total_price
            self._logger.debug("Returning %s for the next payment (no incremental payments)", ret_val)
            return ret_val

        last_payment = self.last_payment(not order_is_ask)
        if not last_payment:
            # Just return the lowest unit possible
            return Quantity(min_unit, self.total_quantity.wallet_id) if order_is_ask else \
                Price(min_unit, self.total_price.wallet_id)

        # We determine the percentage of the last payment of the total amount
        if order_is_ask:
            if self.transferred_price >= self.total_price:  # Complete the trade
                return self.total_quantity - self.transferred_quantity

            percentage = float(last_payment.transferee_price) / float(self.total_price)
            transfer_amount = Transaction.unitize(float(percentage * float(self.total_quantity)), min_unit) * 2
            if transfer_amount > float(self.total_quantity - self.transferred_quantity):
                transfer_amount = float(self.total_quantity - self.transferred_quantity)
            return Quantity(transfer_amount, self.total_quantity.wallet_id)
        else:
            if self.transferred_quantity >= self.total_quantity:  # Complete the trade
                return self.total_price - self.transferred_price

            percentage = float(last_payment.transferee_quantity) / float(self.total_quantity)
            transfer_amount = Transaction.unitize(float(percentage * float(self.total_price)), min_unit) * 2
            if transfer_amount > float(self.total_price - self.transferred_price):
                transfer_amount = float(self.total_price - self.transferred_price)
            return Price(transfer_amount, self.total_price.wallet_id)

    def is_payment_complete(self):
        return self.transferred_price >= self.total_price and self.transferred_quantity >= self.total_quantity

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this transaction.
        """
        return {
            "trader_id": str(self.transaction_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "partner_trader_id": str(self.partner_order_id.trader_id),
            "partner_order_number": int(self.partner_order_id.order_number),
            "transaction_number": int(self.transaction_id.transaction_number),
            "price": float(self.price),
            "price_type": self.price.wallet_id,
            "transferred_price": float(self.transferred_price),
            "quantity": float(self.total_quantity),
            "quantity_type": self.total_quantity.wallet_id,
            "transferred_quantity": float(self.transferred_quantity),
            "timestamp": float(self.timestamp),
            "payment_complete": self.is_payment_complete(),
            "status": self.status
        }


class StartTransaction(Message):
    """Class for representing a message to indicate the start of a payment set"""

    def __init__(self, trader_id, transaction_id, order_id, recipient_order_id, proposal_id,
                 price, quantity, timestamp):
        """
        :param trader_id: The trader ID who created the order
        :param transaction_id: A transaction id to identify the transaction
        :param order_id: My order id
        :param recipient_order_id: The order id of the recipient of this message
        :param proposal_id: The proposal ID associated with this start transaction message
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp when the transaction was created
        :type trader_id: TraderId
        :type transaction_id: TransactionId
        :type proposal_id: int
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        """
        super(StartTransaction, self).__init__(trader_id, timestamp)

        self._transaction_id = transaction_id
        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._proposal_id = proposal_id
        self._price = price
        self._quantity = quantity

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def recipient_order_id(self):
        """
        :rtype: OrderId
        """
        return self._recipient_order_id

    @property
    def proposal_id(self):
        """
        :return: The proposal id
        :rtype: int
        """
        return self._proposal_id

    @property
    def price(self):
        """
        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a start transaction message from the network

        :param data: StartTransactionPayload
        :return: Restored start transaction
        :rtype: StartTransaction
        """
        return cls(
            data.trader_id,
            data.transaction_id,
            data.order_id,
            data.recipient_order_id,
            data.proposal_id,
            data.price,
            data.quantity,
            data.timestamp
        )

    def to_network(self):
        """
        Return network representation of the start transaction message
        """
        return (
            self._trader_id,
            self._timestamp,
            self._transaction_id,
            self._order_id,
            self._recipient_order_id,
            self._proposal_id,
            self._price,
            self._quantity,
        )
