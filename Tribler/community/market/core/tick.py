from __future__ import absolute_import

import time
from binascii import hexlify, unhexlify

from ipv8.attestation.trustchain.block import GENESIS_HASH
from ipv8.database import database_blob
from ipv8.util import old_round

from six import text_type

from Tribler.community.market import MAX_ORDER_TIMEOUT
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class Tick(object):
    """
    Abstract tick class for representing a order on another node. This tick is replicating the order sitting on
    the node it belongs to.
    """
    TIME_TOLERANCE = 10 * 1000  # A small tolerance for the timestamp, to account for network delays

    def __init__(self, order_id, assets, timeout, timestamp, is_ask, traded=0, block_hash=GENESIS_HASH):
        """
        Don't use this class directly, use one of the class methods

        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :param traded: How much assets have been traded already
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        :type traded: int
        :type block_hash: str
        """
        self._order_id = order_id
        self._assets = assets
        self._timeout = timeout
        self._timestamp = timestamp
        self._is_ask = is_ask
        self._traded = traded
        self._block_hash = block_hash

    @classmethod
    def from_database(cls, data):
        trader_id, order_number, asset1_amount, asset1_type, asset2_amount, asset2_type, timeout, timestamp,\
        is_ask, traded, block_hash = data

        tick_cls = Ask if is_ask else Bid
        order_id = OrderId(TraderId(trader_id), OrderNumber(order_number))
        return tick_cls(order_id, AssetPair(AssetAmount(asset1_amount, str(asset1_type)),
                                            AssetAmount(asset2_amount, str(asset2_type))),
                        Timeout(timeout), Timestamp(timestamp), traded=traded, block_hash=str(block_hash))

    def to_database(self):
        return (database_blob(bytes(self.order_id.trader_id)), int(self.order_id.order_number),
                self.assets.first.amount, text_type(self.assets.first.asset_id), self.assets.second.amount,
                text_type(self.assets.second.asset_id), int(self.timeout), int(self.timestamp), self.is_ask(),
                self.traded, database_blob(self.block_hash))

    @classmethod
    def from_order(cls, order):
        """
        Create a tick from an order

        :param order: The order that this tick represents
        :return: The created tick
        :rtype: Tick
        """
        if order.is_ask():
            return Ask(order.order_id, order.assets, order.timeout, order.timestamp, traded=order.traded_quantity)
        else:
            return Bid(order.order_id, order.assets, order.timeout, order.timestamp, traded=order.traded_quantity)

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def assets(self):
        """
        :rtype: AssetPair
        """
        return self._assets

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self.assets.price

    @property
    def timeout(self):
        """
        Return when the tick is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        Return the timestamp of the order
        :rtype: Timestamp
        """
        return self._timestamp

    def is_ask(self):
        """
        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    @property
    def traded(self):
        """
        Return how much assets have been traded already
        :rtype int
        """
        return self._traded

    @traded.setter
    def traded(self, new_traded):
        """
        :param new_traded: The new amount of traded assets
        :type new_traded: int
        """
        self._traded = new_traded

    @property
    def block_hash(self):
        """
        Return the hash of the associated block
        :rtype str
        """
        return self._block_hash

    @block_hash.setter
    def block_hash(self, new_hash):
        """
        :param new_hash: The new block hash
        :type new_hash: str
        """
        self._block_hash = new_hash

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(self._timestamp) and \
               int(old_round(time.time() * 1000)) >= int(self.timestamp) - self.TIME_TOLERANCE and \
               int(self._timeout) <= MAX_ORDER_TIMEOUT

    def to_network(self):
        """
        Return network representation of the tick
        """
        return (
            self._order_id.trader_id,
            self._timestamp,
            self._order_id.order_number,
            self._assets,
            self._timeout,
            self._traded,
        )

    def to_block_dict(self):
        """
        Return a block dictionary representation of the tick, will be stored on the TrustChain
        """
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "assets": self.assets.to_dictionary(),
            "timeout": int(self.timeout),
            "timestamp": int(self.timestamp),
            "traded": self.traded
        }

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this tick.
        """
        return {
            "trader_id": self.order_id.trader_id.as_hex(),
            "order_number": int(self.order_id.order_number),
            "assets": self.assets.to_dictionary(),
            "timeout": int(self.timeout),
            "timestamp": int(self.timestamp),
            "traded": self.traded,
            "block_hash": hexlify(self.block_hash),
        }

    def __str__(self):
        """
        Return the string representation of this tick.
        """
        return "<%s P: %f, Q: %s, O: %s>" % \
               (self.__class__.__name__, float(self.price.amount), self.assets.first, str(self.order_id))


class Ask(Tick):
    """Represents an ask from a order located on another node."""

    def __init__(self, order_id, assets, timeout, timestamp, traded=0, block_hash=GENESIS_HASH):
        """
        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :param traded: How much assets have been traded already
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type traded: int
        :type block_hash: str
        """
        super(Ask, self).__init__(order_id, assets, timeout, timestamp, True, traded=traded, block_hash=block_hash)

    @classmethod
    def from_block(cls, block):
        """
        Restore an ask from a TrustChain block

        :param data: TrustChainBlock
        :return: Restored ask
        :rtype: Ask
        """
        tx_dict = block.transaction["tick"]
        return cls(
            OrderId(TraderId(unhexlify(tx_dict["trader_id"])), OrderNumber(tx_dict["order_number"])),
            AssetPair.from_dictionary(tx_dict["assets"]),
            Timeout(tx_dict["timeout"]),
            Timestamp(tx_dict["timestamp"]),
            traded=tx_dict["traded"],
            block_hash=block.hash
        )


class Bid(Tick):
    """Represents a bid from a order located on another node."""

    def __init__(self, order_id, assets, timeout, timestamp, traded=0, block_hash=GENESIS_HASH):
        """
        :param order_id: A order id to identify the order this tick represents
        :param assets: The assets being sold/bought
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :param traded: How much assets have been traded already
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type assets: AssetPair
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type traded: int
        :type block_hash: str
        """
        super(Bid, self).__init__(order_id, assets, timeout, timestamp, False, traded=traded, block_hash=block_hash)

    @classmethod
    def from_block(cls, block):
        """
        Restore a bid from a TrustChain block

        :param data: TrustChainBlock
        :return: Restored bid
        :rtype: Bid
        """
        tx_dict = block.transaction["tick"]
        return cls(
            OrderId(TraderId(unhexlify(tx_dict["trader_id"])), OrderNumber(tx_dict["order_number"])),
            AssetPair.from_dictionary(tx_dict["assets"]),
            Timeout(tx_dict["timeout"]),
            Timestamp(tx_dict["timestamp"]),
            traded=tx_dict["traded"],
            block_hash=block.hash
        )
