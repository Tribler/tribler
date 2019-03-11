from __future__ import absolute_import

import logging
from decimal import Decimal

from six import text_type

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import Message, TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
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

    def __init__(self, transaction_id, assets, order_id, partner_order_id, timestamp):
        """
        :param transaction_id: An transaction id to identify the order
        :param assets: The asset pair to exchange
        :param order_id: The id of your order for this transaction
        :param partner_order_id: The id of the order of the other party
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type assets: AssetPair
        :type order_id: OrderId
        :type partner_order_id: OrderId
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self._transaction_id = transaction_id
        self._assets = assets
        self._transferred_assets = AssetPair(AssetAmount(0, assets.first.asset_id),
                                             AssetAmount(0, assets.second.asset_id))
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
        (trader_id, transaction_number, order_trader_id, order_number, partner_trader_id, partner_order_number,
         asset1_amount, asset1_type, asset1_transferred, asset2_amount, asset2_type, asset2_transferred,
         transaction_timestamp, sent_wallet_info, received_wallet_info, incoming_address, outgoing_address,
         partner_incoming_address, partner_outgoing_address, match_id) = data

        transaction_id = TransactionId(TraderId(bytes(trader_id)), TransactionNumber(transaction_number))
        transaction = cls(transaction_id,
                          AssetPair(AssetAmount(asset1_amount, str(asset1_type)),
                                    AssetAmount(asset2_amount, str(asset2_type))),
                          OrderId(TraderId(bytes(order_trader_id)), OrderNumber(order_number)),
                          OrderId(TraderId(bytes(partner_trader_id)), OrderNumber(partner_order_number)),
                          Timestamp(float(transaction_timestamp)))

        transaction._transferred_assets = AssetPair(AssetAmount(asset1_transferred, str(asset1_type)),
                                                    AssetAmount(asset2_transferred, str(asset2_type)))
        transaction.sent_wallet_info = sent_wallet_info
        transaction.received_wallet_info = received_wallet_info
        transaction.incoming_address = WalletAddress(str(incoming_address))
        transaction.outgoing_address = WalletAddress(str(outgoing_address))
        transaction.partner_incoming_address = WalletAddress(str(partner_incoming_address))
        transaction.partner_outgoing_address = WalletAddress(str(partner_outgoing_address))
        transaction.match_id = str(match_id)
        transaction._payments = payments

        return transaction

    @classmethod
    def from_block(cls, block_info):
        """
        Create a Transaction object based on information in a tx_init/tx_done block.
        """
        trader_id = block_info["tx"]["trader_id"]
        transaction_number = block_info["tx"]["transaction_number"]
        order_trader_id = block_info["tx"]["trader_id"]
        order_number = block_info["tx"]["order_number"]
        partner_trader_id = block_info["tx"]["partner_trader_id"]
        partner_order_number = block_info["tx"]["partner_order_number"]
        asset1_amount = block_info["tx"]["assets"]["first"]["amount"]
        asset1_type = block_info["tx"]["assets"]["first"]["type"]
        asset1_transferred = block_info["tx"]["transferred"]["first"]["amount"]
        asset2_amount = block_info["tx"]["assets"]["second"]["amount"]
        asset2_type = block_info["tx"]["assets"]["second"]["type"]
        asset2_transferred = block_info["tx"]["transferred"]["second"]["amount"]
        transaction_timestamp = block_info["tx"]["timestamp"]
        sent_wallet_info = False
        received_wallet_info = False
        incoming_address = None
        outgoing_address = None
        partner_incoming_address = None
        partner_outgoing_address = None
        match_id = ''

        transaction_id = TransactionId(TraderId(bytes(trader_id)), TransactionNumber(transaction_number))
        transaction = cls(transaction_id,
                          AssetPair(AssetAmount(asset1_amount, str(asset1_type)),
                                    AssetAmount(asset2_amount, str(asset2_type))),
                          OrderId(TraderId(bytes(order_trader_id)), OrderNumber(order_number)),
                          OrderId(TraderId(bytes(partner_trader_id)), OrderNumber(partner_order_number)),
                          Timestamp(float(transaction_timestamp)))

        transaction._transferred_assets = AssetPair(AssetAmount(asset1_transferred, str(asset1_type)),
                                                    AssetAmount(asset2_transferred, str(asset2_type)))
        transaction.sent_wallet_info = sent_wallet_info
        transaction.received_wallet_info = received_wallet_info
        transaction.incoming_address = WalletAddress(str(incoming_address))
        transaction.outgoing_address = WalletAddress(str(outgoing_address))
        transaction.partner_incoming_address = WalletAddress(str(partner_incoming_address))
        transaction.partner_outgoing_address = WalletAddress(str(partner_outgoing_address))
        transaction.match_id = str(match_id)

        return transaction

    def to_database(self):
        """
        Returns a database representation of a Transaction object.
        :rtype: tuple
        """
        return (text_type(self.transaction_id.trader_id), int(self.transaction_id.transaction_number),
                text_type(self.order_id.trader_id), int(self.order_id.order_number),
                text_type(self.partner_order_id.trader_id), int(self.partner_order_id.order_number),
                self.assets.first.amount, text_type(self.assets.first.asset_id), self.transferred_assets.first.amount,
                self.assets.second.amount, text_type(self.assets.second.asset_id),
                self.transferred_assets.second.amount, float(self.timestamp), self.sent_wallet_info,
                self.received_wallet_info, text_type(self.incoming_address), text_type(self.outgoing_address),
                text_type(self.partner_incoming_address), text_type(self.partner_outgoing_address),
                text_type(self.match_id))

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
        return cls(transaction_id, proposed_trade.assets, proposed_trade.recipient_order_id,
                   proposed_trade.order_id, Timestamp.now())

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def assets(self):
        """
        :rtype: AssetPair
        """
        return self._assets

    @property
    def transferred_assets(self):
        """
        :rtype: AssetPair
        """
        return self._transferred_assets

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

    def add_payment(self, payment):
        """
        Add a completed payment to this transaction and update its state.
        """
        self._logger.debug("Adding transferred assets %s to transaction %s",
                           payment.transferred_assets, self.transaction_id)
        if payment.transferred_assets.asset_id == self.transferred_assets.first.asset_id:
            self.transferred_assets.first += payment.transferred_assets
        else:
            self.transferred_assets.second += payment.transferred_assets
        self._payments.append(payment)

    def next_payment(self, order_is_ask):
        """
        Return the assets that this user has to send to the counterparty as a next step.
        :param order_is_ask: Whether the order is an ask or not.
        :return: An AssetAmount object, indicating how much we should send to the counterparty.
        """
        assets_to_transfer = self.assets.first if order_is_ask else self.assets.second
        self._logger.debug("Returning %s for the next payment (no incremental payments)", assets_to_transfer)
        return assets_to_transfer

    def is_payment_complete(self):
        return self.transferred_assets.first >= self.assets.first and \
               self.transferred_assets.second >= self.assets.second

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
            "assets": self.assets.to_dictionary(),
            "transferred": self.transferred_assets.to_dictionary(),
            "timestamp": float(self.timestamp),
            "payment_complete": self.is_payment_complete(),
            "status": self.status
        }


class StartTransaction(Message):
    """Class for representing a message to indicate the start of a payment set"""

    def __init__(self, trader_id, transaction_id, order_id, recipient_order_id, proposal_id, assets, timestamp):
        """
        :param trader_id: The trader ID who created the order
        :param transaction_id: A transaction id to identify the transaction
        :param order_id: My order id
        :param recipient_order_id: The order id of the recipient of this message
        :param proposal_id: The proposal ID associated with this start transaction message
        :param assets: The assets to be traded
        :param timestamp: A timestamp when the transaction was created
        :type trader_id: TraderId
        :type transaction_id: TransactionId
        :type proposal_id: int
        :type order_id: OrderId
        :type assets: AssetPair
        :type timestamp: Timestamp
        """
        super(StartTransaction, self).__init__(trader_id, timestamp)

        self._transaction_id = transaction_id
        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._proposal_id = proposal_id
        self._assets = assets

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
    def assets(self):
        """
        :return: The assets to be traded
        :rtype: AssetPair
        """
        return self._assets

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
            data.assets,
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
            self._assets
        )
