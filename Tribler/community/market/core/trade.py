import random

from Tribler.community.market.core.message import Message
from Tribler.community.market.core.order import OrderId
from Tribler.community.market.core.timestamp import Timestamp


class Trade(Message):
    """Abstract message class used for communicating with other nodes to find a trading partner"""

    def __init__(self, trader_id, order_id, recipient_order_id, proposal_id, timestamp):
        """
        Don't use this method directly, use one of the class methods.

        :param trader_id: String representing the trader id
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param timestamp: A timestamp wen this trade was created
        :type trader_id: TraderId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type timestamp: Timestamp
        """
        super(Trade, self).__init__(trader_id, timestamp)

        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._proposal_id = proposal_id

    @classmethod
    def propose(cls, trader_id, order_id, recipient_order_id, assets, timestamp):
        """
        Propose a trade to another node

        :param trader_id: String representing the trader id
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param assets: The assets to be traded
        :param timestamp: A timestamp wen this trade was created
        :type trader_id: TraderId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            trader_id,
            order_id,
            recipient_order_id,
            random.randint(0, 100000000),
            assets,
            timestamp
        )

    @classmethod
    def decline(cls, trader_id, timestamp, proposed_trade, decline_reason):
        """
        Decline a trade from another node

        :param trader_id: String representing the trader id
        :param timestamp: A timestamp when the trade was declined
        :param proposed_trade: A proposed trade that needs to be declined
        :param decline_reason: A reason for declining this trade
        :type trader_id: TraderId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :type decline_reason: int
        :return: A declined trade
        :rtype: DeclinedTrade
        """
        return DeclinedTrade(
            trader_id,
            proposed_trade.recipient_order_id,
            proposed_trade.order_id,
            proposed_trade.proposal_id,
            timestamp,
            decline_reason
        )

    @classmethod
    def counter(cls, trader_id, assets, timestamp, proposed_trade):
        """
        Counter a trade from another node

        :param trader_id: A message id to identify the trade
        :param assets: The assets to be traded in this counter offer
        :param timestamp: A timestamp when the trade was countered
        :param proposed_trade: A proposed trade that needs to be countered
        :type trader_id: TraderId
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: A counter trade
        :rtype: CounterTrade
        """
        return CounterTrade(
            trader_id,
            proposed_trade.recipient_order_id,
            proposed_trade.order_id,
            proposed_trade.proposal_id,
            assets,
            timestamp
        )

    @property
    def order_id(self):
        """
        :return: The order id
        :rtype: OrderId
        """
        return self._order_id

    @property
    def recipient_order_id(self):
        """
        :return: The order id
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

    def to_network(self):
        return NotImplemented


class ProposedTrade(Trade):
    """
    A proposed trade is send when a node whats to make a trade with another node. This trade cannot be made
    instantly because this node does not know if the tick from the other node is still available. Because of that a
    proposed trade is send first.
    """

    def __init__(self, trader_id, order_id, recipient_order_id, proposal_id, assets, timestamp):
        """
        Don't use this method directly, use the class methods from Trade or use the from_network

        :param trader_id: String representing the trader id
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param assets: The assets to be traded in the proposal
        :param timestamp: A timestamp wen this trade was created
        :type trader_id: TraderId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type assets: AssetPair
        :type timestamp: Timestamp
        """
        super(ProposedTrade, self).__init__(trader_id, order_id, recipient_order_id, proposal_id, timestamp)

        self._assets = assets

    @classmethod
    def from_network(cls, data):
        """
        Restore a proposed trade from the network

        :param data: TradePayload
        :return: Restored proposed trade
        :rtype: ProposedTrade
        """
        return cls(
            data.trader_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.assets,
            data.timestamp
        )

    @property
    def assets(self):
        """
        :return: The assets to be exchanged
        :rtype: AssetPair
        """
        return self._assets

    def to_network(self):
        """
        Return network representation of a proposed trade
        """
        return (
            self._trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._assets
        )


class CounterTrade(ProposedTrade):
    """
    Counter trades are send as a response to a proposed trade. If after receiving the order to be trade for
    is not fully available anymore, a counter offer is made with the quantity that is still left. This was
    done to insure that trades were made quickly and efficiently.
    """

    def __init__(self, trader_id, order_id, recipient_order_id, proposal_id, assets, timestamp):
        """
        Don't use this method directly, use one of the class methods of Trade or use from_network

        :param trader_id: String representing the trader id
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param assets: The assets to be traded in the proposal
        :param timestamp: A timestamp wen this trade was created
        :type trader_id: TraderId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type assets: AssetPair
        :type timestamp: Timestamp
        """
        super(CounterTrade, self).__init__(trader_id, order_id, recipient_order_id, proposal_id, assets, timestamp)

    @classmethod
    def from_network(cls, data):
        """
        Restore a counter trade from the network

        :param data: TradePayload
        :return: Restored counter trade
        :rtype: CounterTrade
        """
        return cls(
            data.trader_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.assets,
            data.timestamp
        )

    def to_network(self):
        """
        Return network representation of a counter trade
        """
        return (
            self._trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._assets
        )


class DeclinedTrade(Trade):
    """
    Declined trades are send as a response to a proposed trade or a counter trade. When a proposed trade has come in
    and there is no possibility to make a counter offer a declined trade is send to indicate the is no possibility
    to make a trade. When a counter trade has been received, there is a check for seeing if the trade was reserved,
    if the trade was not reserved then a declined trade is send.
    """

    def __init__(self, trader_id, order_id, recipient_order_id, proposal_id, timestamp, decline_reason):
        """
        Don't use this method directly, use one of the class methods from Trade or the from_network

        :param trader_id: String representing the trader id
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the order
        :param proposal_id: The ID of the trade proposal
        :param timestamp: A timestamp wen this trade was created
        :param decline_reason: A reason for declining this trade
        :type trader_id: TraderId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type timestamp: Timestamp
        :type decline_reason: int
        """
        super(DeclinedTrade, self).__init__(trader_id, order_id, recipient_order_id, proposal_id, timestamp)

        self._decline_reason = decline_reason

    @property
    def decline_reason(self):
        """
        :return: The reason why this match is declined
        :rtype: int
        """
        return self._decline_reason

    @classmethod
    def from_network(cls, data):
        """
        Restore a declined trade from the network

        :param data: DeclinedTradePayload
        :return: Restored declined trade
        :rtype: DeclinedTrade
        """
        return cls(
            data.trader_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.timestamp,
            data.decline_reason
        )

    def to_network(self):
        """
        Return network representation of a declined trade
        """
        return (
            self._trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._decline_reason
        )
