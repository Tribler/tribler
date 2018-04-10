import random
from base64 import b64decode

from Tribler.pyipv8.ipv8.deprecated.bloomfilter import BloomFilter
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed, Deferred, returnValue
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT, NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core import DeclineMatchReason, DeclinedTradeReason
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.order_manager import OrderManager
from Tribler.community.market.core.order_repository import DatabaseOrderRepository, MemoryOrderRepository
from Tribler.community.market.core.orderbook import DatabaseOrderBook
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.socket_address import SocketAddress
from Tribler.community.market.core.tick import Ask, Bid, Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, CounterTrade
from Tribler.community.market.core.transaction import StartTransaction, TransactionId, Transaction, TransactionNumber
from Tribler.community.market.core.transaction_manager import TransactionManager
from Tribler.community.market.core.transaction_repository import DatabaseTransactionRepository,\
    MemoryTransactionRepository
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.database import MarketDB
from Tribler.community.market.payload import InfoPayload, MatchPayload, TradePayload, StartTransactionPayload, \
    AcceptMatchPayload, OrderStatusRequestPayload, OrderStatusResponsePayload, WalletInfoPayload, PaymentPayload, \
    DeclineMatchPayload, DeclineTradePayload, OrderbookSyncPayload, PingPongPayload
from Tribler.community.market.reputation.temporal_pagerank_manager import TemporalPagerankReputationManager
from Tribler.community.market.tradechain.block import TradeChainBlock
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity, synchronized
from Tribler.pyipv8.ipv8.attestation.trustchain.payload import HalfBlockPayload, HalfBlockBroadcastPayload, \
    HalfBlockPairPayload, HalfBlockPairBroadcastPayload
from Tribler.pyipv8.ipv8.deprecated.payload import IntroductionRequestPayload, IntroductionResponsePayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache


class ProposedTradeRequestCache(NumberCache):
    """
    This cache keeps track of outstanding proposed trade messages.
    """
    def __init__(self, community, proposed_trade, match_id):
        super(ProposedTradeRequestCache, self).__init__(community.request_cache, u"proposed-trade",
                                                        proposed_trade.proposal_id)
        self.community = community
        self.proposed_trade = proposed_trade
        self.match_id = match_id

    def on_timeout(self):
        # Just remove the reserved quantity from the order
        order = self.community.order_manager.order_repository.find_by_id(self.proposed_trade.order_id)
        order.release_quantity_for_tick(self.proposed_trade.recipient_order_id, self.proposed_trade.quantity)
        self.community.order_manager.order_repository.update(order)

        if self.match_id:
            # Inform the matchmaker about the failed trade
            match_message = self.community.incoming_match_messages[self.match_id]
            self.community.send_decline_match_message(self.match_id, match_message.matchmaker_trader_id,
                                                      DeclineMatchReason.OTHER)


class OrderStatusRequestCache(RandomNumberCache):

    def __init__(self, community, request_deferred):
        super(OrderStatusRequestCache, self).__init__(community.request_cache, u"order-status-request")
        self.request_deferred = request_deferred

    @property
    def timeout_delay(self):
        return 20.0

    def on_timeout(self):
        self._logger.warning("No response in time from remote peer when requesting order status")


class PingRequestCache(RandomNumberCache):
    """
    This request cache keeps track of outstanding ping messages to matchmakers.
    """
    TIMEOUT_DELAY = 5.0

    def __init__(self, community, request_deferred):
        super(PingRequestCache, self).__init__(community.request_cache, u"ping")
        self.request_deferred = request_deferred

    @property
    def timeout_delay(self):
        return PingRequestCache.TIMEOUT_DELAY

    def on_timeout(self):
        self.request_deferred.callback(False)


class MarketCommunity(TrustChainCommunity):
    """
    Community for general asset trading.
    """
    BLOCK_CLASS = TradeChainBlock
    DB_CLASS = MarketDB
    DB_NAME = 'market'
    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000405825d086899ad4c48fcb24cf5fc3df44f909dde8"
                       "fc76486337c072c09f5e19753af9132e0a1ad13e90c70babf81eea9891fb73ca9bb3a52637a188358fe75769ccc7a"
                       "100e2f3ca602de3ce8ed4a8607c495eb90125cbcbc1c85c0a3868ea5faaca135083eadf0b757d99d4a22efbb44656"
                       "c105a5f8cf5c1339ccb238f62e715369630ad3a50301efe4c11f97f5d89fe".decode('hex'))

    def __init__(self, *args, **kwargs):
        self.is_matchmaker = kwargs.pop('is_matchmaker', True)
        self.tribler_session = kwargs.pop('tribler_session', None)
        self.wallets = kwargs.pop('wallets', {})
        use_database = kwargs.pop('use_database', True)

        kwargs['db_name'] = self.DB_NAME

        super(MarketCommunity, self).__init__(*args, **kwargs)
        self._use_main_thread = True  # Market community is unable to deal with thread pool message processing yet
        self.mid = self.my_peer.mid.encode('hex')
        self.mid_register = {}
        self.order_book = None
        self.market_database = self.persistence
        self.matching_engine = None
        self.incoming_match_messages = {}  # Map of TraderId -> Message (we save all incoming matches)
        self.transaction_manager = None
        self.reputation_dict = {}
        self.use_local_address = False
        self.matching_enabled = True
        self.message_repository = MemoryMessageRepository(self.mid)
        self.use_incremental_payments = False
        self.matchmakers = set()
        self.pending_matchmaker_deferreds = []
        self.request_cache = RequestCache()
        self.cancelled_orders = set()  # Keep track of cancelled orders so we don't add them again to the orderbook.
        self.broadcast_block = False

        if use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
            transaction_repository = DatabaseTransactionRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)
            transaction_repository = MemoryTransactionRepository(self.mid)

        self.order_manager = OrderManager(order_repository)
        self.transaction_manager = TransactionManager(transaction_repository)

        if self.is_matchmaker:
            self.enable_matchmaker()

        for trader in self.market_database.get_traders():
            self.update_ip(TraderId(str(trader[0])), (str(trader[1]), trader[2]))

        # Determine the reputation of peers every five minutes
        self.register_task("calculate_reputation", LoopingCall(self.compute_reputation)).start(300.0, now=False)

        # Register messages
        self.decode_map.update({
            chr(7): self.received_match,
            chr(8): self.received_accept_match,
            chr(9): self.received_decline_match,
            chr(10): self.received_proposed_trade,
            chr(11): self.received_decline_trade,
            chr(12): self.received_counter_trade,
            chr(13): self.received_start_transaction,
            chr(14): self.received_wallet_info,
            chr(15): self.received_payment_message,
            chr(16): self.received_order_status_request,
            chr(17): self.received_order_status,
            chr(18): self.received_info,
            chr(19): self.received_orderbook_sync,
            chr(20): self.received_ping,
            chr(21): self.received_pong
        })

        self.logger.info("Market community initialized with mid %s", self.mid)

    def should_sign(self, block):
        """
        Check whether we should sign the incoming block.
        """
        tx = block.transaction
        if tx["type"] == "tick" or tx["type"] == "cancel_order":
            self.logger.info("Signing %s block as matchmaker!", tx["type"])
            return True  # Just sign it
        elif tx["type"] == "tx_payment":
            txid = TransactionId(TraderId(tx["payment"]["trader_id"]),
                                 TransactionNumber(tx["payment"]["transaction_number"]))
            transaction = self.transaction_manager.find_by_id(txid)
            return bool(transaction)
        elif tx["type"] == "tx_init" or tx["type"] == "tx_done":
            txid = TransactionId(TraderId(tx["tx"]["trader_id"]), TransactionNumber(tx["tx"]["transaction_number"]))
            transaction = self.transaction_manager.find_by_id(txid)
            return bool(transaction)
        else:
            return False  # Unknown block type

    def enable_matchmaker(self):
        """
        Enable this node to be a matchmaker
        """
        self.order_book = DatabaseOrderBook(self.market_database)
        self.order_book.restore_from_database()
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))
        self.is_matchmaker = True

    def disable_matchmaker(self):
        """
        Disable the matchmaker status of this node
        """
        self.order_book = None
        self.matching_engine = None
        self.is_matchmaker = False

    def get_wallet_ids(self):
        """
        Return the IDs of all wallets in the market community.
        """
        return self.wallets.keys()

    def on_introduction_request(self, source_address, data):
        super(MarketCommunity, self).on_introduction_request(source_address, data)
        auth, _, _ = self._ez_unpack_auth(IntroductionRequestPayload, data)
        peer = Peer(auth.public_key_bin, source_address)
        self.send_info(peer)

        if self.is_matchmaker:
            self.send_orderbook_sync(peer)

    def on_introduction_response(self, source_address, data):
        super(MarketCommunity, self).on_introduction_response(source_address, data)
        auth, _, _ = self._ez_unpack_auth(IntroductionResponsePayload, data)
        peer = Peer(auth.public_key_bin, source_address)
        self.send_info(peer)

        if self.is_matchmaker:
            self.send_orderbook_sync(peer)

    def send_orderbook_sync(self, peer):
        """
        Send an orderbook sync message to a specific peer.
        """
        bloomfilter = self.get_orders_bloomfilter()
        message_id = self.message_repository.next_identity()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderbookSyncPayload(message_id, Timestamp.now(), bloomfilter).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 19, [auth, dist, payload])
        self.endpoint.send(peer.address, packet)

    def get_orders_bloomfilter(self):
        order_ids = [str(order_id) for order_id in self.order_book.get_order_ids()]
        orders_bloom_filter = BloomFilter(0.005, max(len(order_ids), 1), prefix=' ')
        if order_ids:
            orders_bloom_filter.add_keys(order_ids)
        return orders_bloom_filter

    @inlineCallbacks
    def unload(self):
        self.request_cache.clear()

        # Store all traders to the database
        for trader_id, sock_addr in self.mid_register.iteritems():
            self.market_database.add_trader_identity(trader_id, sock_addr[0], sock_addr[1])

        # Save the ticks to the database
        if self.is_matchmaker:
            self.order_book.save_to_database()
            self.order_book.shutdown_task_manager()
        yield super(MarketCommunity, self).unload()

    def get_ipv8_address(self):
        """
        Returns the address of the IPV8 instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.my_estimated_lan if self.use_local_address else self.my_estimated_wan

    def get_wallet_address(self, wallet_id):
        """
        Returns the address of the wallet with a specific identifier. Raises a ValueError if that wallet is not
        available.
        """
        if wallet_id not in self.wallets or not self.wallets[wallet_id].created:
            raise ValueError("Wallet %s not available" % wallet_id)

        return self.wallets[wallet_id].get_address()

    def get_order_addresses(self, order):
        """
        Return a tuple of incoming and outgoing payment address of an order.
        """
        if order.is_ask():
            return WalletAddress(self.wallets[order.price.wallet_id].get_address()),\
                   WalletAddress(self.wallets[order.total_quantity.wallet_id].get_address())
        else:
            return WalletAddress(self.wallets[order.total_quantity.wallet_id].get_address()), \
                   WalletAddress(self.wallets[order.price.wallet_id].get_address())

    def match_order_ids(self, order_ids):
        """
        Attempt to match the ticks with the provided order ids
        :param order_ids: The order ids to match
        """
        for order_id in order_ids:
            if self.order_book.tick_exists(order_id):
                self.match(self.order_book.get_tick(order_id))

    def match(self, tick):
        """
        Try to find a match for a specific tick and send proposed trade messages if there is a match
        :param tick: The tick to find matches for
        """
        if not self.matching_enabled:
            return

        order_tick_entry = self.order_book.get_tick(tick.order_id)
        if tick.quantity - order_tick_entry.reserved_for_matching <= Quantity(0, tick.quantity.wallet_id):
            self.logger.debug("Tick %s does not have any quantity to match!", tick.order_id)
            return

        matched_ticks = self.matching_engine.match(order_tick_entry)
        for _, tick_entry, trading_quantity in matched_ticks:
            tick_entry.reserve_for_matching(trading_quantity)
            order_tick_entry.reserve_for_matching(trading_quantity)
        self.send_match_messages(matched_ticks, tick.order_id)

    def lookup_ip(self, trader_id):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param trader_id: The public key of the node to send to
        :type trader_id: TraderId
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        assert isinstance(trader_id, TraderId), type(trader_id)
        return self.mid_register.get(trader_id)

    def update_ip(self, trader_id, ip):
        """
        Update the public key to ip mapping

        :param trader_id: The public key of the node
        :param ip: The ip and port of the node
        :type trader_id: TraderId
        :type ip: tuple
        """
        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(ip, tuple), type(ip)
        assert isinstance(ip[0], str)
        assert isinstance(ip[1], int)

        self.logger.debug("Updating ip of trader %s to (%s, %s)", trader_id, ip[0], ip[1])
        self.mid_register[trader_id] = ip

    def on_ask_timeout(self, ask):
        if not ask:
            return

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE, None, ask.to_dictionary())

    def on_bid_timeout(self, bid):
        if not bid:
            return

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE, None, bid.to_dictionary())

    def update_ips_from_block(self, block):
        """
        Update the IP addresses of ask/bid creators in a given block.
        """
        ask = block.transaction["ask"]
        bid = block.transaction["bid"]
        self.update_ip(TraderId(ask["trader_id"]), (ask["ip"], ask["port"]))
        self.update_ip(TraderId(bid["trader_id"]), (bid["ip"], bid["port"]))

    def process_tick_block(self, block):
        """
        Process a TradeChain block containing a tick, only if we have a verified order.
        :param block: The TradeChain block containing the tick
        """
        tick = Ask.from_block(block) if block.transaction["tick"]["is_ask"] else Bid.from_block(block)

        if self.persistence.get_linked(block):
            self.on_tick(tick, (block.transaction["tick"]["address"], block.transaction["tick"]["port"]))

    def process_tx_init_block(self, block):
        """
        Process a TradeChain block containing a transaction initialisation
        :param block: The TradeChain block containing the transaction initialisation
        """
        self.update_ips_from_block(block)
        if self.is_matchmaker:
            tx_dict = block.transaction
            self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"],
                                         Quantity(0, tx_dict["tx"]["quantity_type"]), unreserve=False)
            ask_order_id = OrderId(TraderId(tx_dict["ask"]["trader_id"]), OrderNumber(tx_dict["ask"]["order_number"]))
            bid_order_id = OrderId(TraderId(tx_dict["bid"]["trader_id"]), OrderNumber(tx_dict["bid"]["order_number"]))
            self.match_order_ids([ask_order_id, bid_order_id])

    def process_tx_done_block(self, block):
        """
        Process a TradeChain block containing a transaction completion
        :param block: The TradeChain block containing the transaction completion
        """
        self.update_ips_from_block(block)
        if self.is_matchmaker:
            tx_dict = block.transaction
            transferred_quantity = Quantity(tx_dict["tx"]["quantity"], tx_dict["tx"]["quantity_type"])
            self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"], transferred_quantity, unreserve=False)
            ask_order_id = OrderId(TraderId(tx_dict["ask"]["trader_id"]), OrderNumber(tx_dict["ask"]["order_number"]))
            bid_order_id = OrderId(TraderId(tx_dict["bid"]["trader_id"]), OrderNumber(tx_dict["bid"]["order_number"]))
            self.match_order_ids([ask_order_id, bid_order_id])

    def process_cancel_order_block(self, block):
        """
        Process a TradeChain block containing a order cancellation
        :param block: The TradeChain block containing the order cancellation
        """
        order_id = OrderId(TraderId(block.transaction["trader_id"]), OrderNumber(block.transaction["order_number"]))
        if self.is_matchmaker and self.order_book.tick_exists(order_id):
            self.order_book.remove_tick(order_id)
            self.cancelled_orders.add(order_id)

    def send_info(self, peer):
        """
        Send an info message to the target peer.
        """
        message_id = self.message_repository.next_identity()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = InfoPayload(message_id, Timestamp.now(), self.is_matchmaker).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 18, [auth, dist, payload])
        self.endpoint.send(peer.address, packet)

    def received_info(self, source_address, data):
        auth, _, payload = self._ez_unpack_auth(InfoPayload, data)
        if payload.is_matchmaker:
            self.add_matchmaker(Peer(auth.public_key_bin, source_address))

    def received_orderbook_sync(self, source_address, data):
        _, _, payload = self._ez_unpack_auth(OrderbookSyncPayload, data)

        if not self.is_matchmaker:
            return

        for order_id in self.order_book.get_order_ids():
            if str(order_id) not in payload.bloomfilter:
                is_ask = self.order_book.ask_exists(order_id)
                entry = self.order_book.get_ask(order_id) if is_ask else self.order_book.get_bid(order_id)

                # Send the block pair associated with this tick
                tick_block = self.persistence.get_block_with_hash(entry.tick.block_hash)
                if tick_block:
                    other_tick_block = self.persistence.get_linked(tick_block)
                    if other_tick_block:
                        self.send_block_pair(tick_block, other_tick_block, source_address)

    def ping_peer(self, peer):
        """
        Ping a specific peer. Return a deferred that fires with a boolean value whether the peer responded within time.
        """
        deferred = Deferred()
        cache = PingRequestCache(self, deferred)
        self.request_cache.add(cache)
        self.send_ping(peer, cache.number)
        return deferred

    def send_ping(self, peer, identifier):
        """
        Send a ping message with an identifier to a specific peer.
        """
        message_id = self.message_repository.next_identity()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(message_id, Timestamp.now(), identifier).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 20, [auth, dist, payload])
        self.endpoint.send(peer.address, packet)

    def received_ping(self, source_address, data):
        auth, _, payload = self._ez_unpack_auth(PingPongPayload, data)
        peer = Peer(auth.public_key_bin, source_address)

        self.send_pong(peer, payload.identifier)

    def send_pong(self, peer, identifier):
        """
        Send a pong message with an identifier to a specific peer.
        """
        message_id = self.message_repository.next_identity()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(message_id, Timestamp.now(), identifier).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 21, [auth, dist, payload])
        self.endpoint.send(peer.address, packet)

    def received_pong(self, _, data):
        _, _, payload = self._ez_unpack_auth(PingPongPayload, data)

        if not self.request_cache.has(u"ping", payload.identifier):
            self.logger.warning("ping cache with id %s not found", payload.identifier)
            return

        cache = self.request_cache.pop(u"ping", payload.identifier)
        reactor.callFromThread(cache.request_deferred.callback, True)

    def verify_offer_creation(self, price, price_wallet_id, quantity, quantity_wallet_id):
        if price_wallet_id == quantity_wallet_id:
            raise RuntimeError("You cannot trade between the same wallet")

        if price_wallet_id not in self.wallets or not self.wallets[price_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % price_wallet_id)

        if quantity_wallet_id not in self.wallets or not self.wallets[quantity_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % quantity_wallet_id)

        price_min_unit = self.wallets[price_wallet_id].min_unit()
        if float(price) < price_min_unit:
            raise RuntimeError("The price should be higher than or equal to the minimum unit of this currency (%f)."
                               % price_min_unit)

        quantity_min_unit = self.wallets[quantity_wallet_id].min_unit()
        if float(quantity) < quantity_min_unit:
            raise RuntimeError("The quantity should be higher than or equal to the minimum unit of this currency (%f)."
                               % quantity_min_unit)

    def create_ask(self, price, price_wallet_id, quantity, quantity_wallet_id, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param price_wallet_id: The type of the price (i.e. EUR, BTC)
        :param quantity: The quantity of the order
        :param price_wallet_id: The type of the price (i.e. EUR, BTC)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type price_wallet_id: str
        :type quantity: float
        :type quantity_wallet_id: str
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(price, price_wallet_id, quantity, quantity_wallet_id)

        # Convert values to value objects
        price = Price(price, price_wallet_id)
        quantity = Quantity(quantity, quantity_wallet_id)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_ask_order(price, quantity, timeout)

        # Create the tick
        tick = Tick.from_order(order)
        assert isinstance(tick, Ask), type(tick)

        def on_verified_ask(blocks):
            self.logger.info("Ask verified with price %s and quantity %s", price, quantity)
            order.set_verified()
            self.order_manager.order_repository.update(order)
            self.send_block_pair(*blocks)

            if self.is_matchmaker:
                tick.block_hash = blocks[0].hash
                # Search for matches
                self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
                self.match(tick)

            return order

        self.logger.info("Ask created with price %s and quantity %s", price, quantity)

        return self.create_new_tick_block(tick).addCallback(on_verified_ask)

    def create_bid(self, price, price_wallet_id, quantity, quantity_wallet_id, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param price_wallet_id: The type of the price (i.e. EUR, BTC)
        :param quantity: The quantity of the order
        :param price_wallet_id: The type of the price (i.e. EUR, BTC)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type price_wallet_id: str
        :type quantity: float
        :type quantity_wallet_id: str
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(price, price_wallet_id, quantity, quantity_wallet_id)

        # Convert values to value objects
        price = Price(price, price_wallet_id)
        quantity = Quantity(quantity, quantity_wallet_id)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_bid_order(price, quantity, timeout)

        # Create the tick
        tick = Tick.from_order(order)
        assert isinstance(tick, Bid), type(tick)

        def on_verified_bid(blocks):
            self.logger.info("Bid verified with price %s and quantity %s", price, quantity)
            order.set_verified()
            self.order_manager.order_repository.update(order)
            self.send_block_pair(*blocks)

            if self.is_matchmaker:
                tick.block_hash = blocks[0].hash
                # Search for matches
                self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
                self.match(tick)

            return order

        self.logger.info("Bid created with price %s and quantity %s", price, quantity)

        return self.create_new_tick_block(tick).addCallback(on_verified_bid)

    def received_half_block(self, source_address, data):
        super(MarketCommunity, self).received_half_block(source_address, data)

        _, payload = self._ez_unpack_noauth(HalfBlockPayload, data)
        block = TrustChainBlock.from_payload(payload, self.serializer)

        if "type" not in block.transaction:  # Every market block needs a type
            return

        if block.transaction["type"] == "tx_done":
            # If we have signed an incoming tx_done block, notify the matchmaker about this
            transaction_id = TransactionId(TraderId(block.transaction["tx"]["trader_id"]),
                                           TransactionNumber(block.transaction["tx"]["transaction_number"]))
            transaction = self.transaction_manager.find_by_id(transaction_id)
            if transaction and self.market_database.get_linked(block):
                self.notify_transaction_complete(transaction.to_dictionary(), mine=True)
                self.send_transaction_completed(transaction, block)

        if block.transaction["type"] != "tick" or \
                (block.transaction["type"] == "tick" and block.link_public_key != self.my_peer.public_key.key_to_bin()):
            self.process_market_block(block)

    def received_half_block_broadcast(self, source_address, data):
        super(MarketCommunity, self).received_half_block_broadcast(source_address, data)

        _, payload = self._ez_unpack_noauth(HalfBlockBroadcastPayload, data)
        block = TrustChainBlock.from_payload(payload, self.serializer)

        self.process_market_block(block)

    def process_market_block(self, block):
        if block.transaction["type"] == "tick":
            self.process_tick_block(block)
        elif block.transaction["type"] == "tx_init":
            self.process_tx_init_block(block)
        elif block.transaction["type"] == "tx_done":
            self.process_tx_done_block(block)
        elif block.transaction["type"] == "cancel_order":
            self.process_cancel_order_block(block)

    def received_half_block_pair(self, source_address, data):
        super(MarketCommunity, self).received_half_block_pair(source_address, data)

        _, payload = self._ez_unpack_noauth(HalfBlockPairPayload, data)
        block1, block2 = TrustChainBlock.from_pair_payload(payload, self.serializer)

        if block1.transaction["type"] == "tx_done" and block2.transaction["type"] == "tx_done":
            self.on_transaction_completed_message(block1, block2)
        elif block1.transaction["type"] == "tick" and block2.transaction["type"] == "tick":
            self.process_tick_block(block1)
            self.process_tick_block(block2)

    def received_half_block_pair_broadcast(self, source_address, data):
        super(MarketCommunity, self).received_half_block_pair_broadcast(source_address, data)

        _, payload = self._ez_unpack_noauth(HalfBlockPairBroadcastPayload, data)
        block1, block2 = TrustChainBlock.from_pair_payload(payload, self.serializer)
        if block1.transaction["type"] == "tx_done" and block2.transaction["type"] == "tx_done":
            self.on_transaction_completed_bc_message(block1, block2)
        elif block1.transaction["type"] == "tick" and block2.transaction["type"] == "tick":
            self.process_tick_block(block1)
            self.process_tick_block(block2)

    def add_matchmaker(self, matchmaker):
        """
        Add a matchmaker to the set of known matchmakers. Also check whether there are pending deferreds.
        """
        if matchmaker.public_key.key_to_bin() == self.my_peer.public_key.key_to_bin():
            return

        self.matchmakers.add(matchmaker)

        for matchmaker_deferred in self.pending_matchmaker_deferreds:
            matchmaker_deferred.callback(random.sample(self.matchmakers, 1)[0])

        self.pending_matchmaker_deferreds = []

    @inlineCallbacks
    def get_online_matchmaker(self):
        """
        Get an online matchmaker. If there is no matchmaker available, wait until there's one.
        :return: A Deferred that fires with a matchmaker.
        """
        while True:
            if not self.matchmakers:
                break
            random_matchmaker = random.sample(self.matchmakers, 1)[0]
            online = yield self.ping_peer(random_matchmaker)
            if not online:
                self.matchmakers.remove(random_matchmaker)
            else:
                returnValue(random_matchmaker)

        # We didn't find an online matchmaker; wait until we find one
        self.logger.info("No matchmaker found, wait until there's one available")
        matchmaker_deferred = Deferred()
        self.pending_matchmaker_deferreds.append(matchmaker_deferred)
        matchmaker = yield matchmaker_deferred
        returnValue(matchmaker)

    @synchronized
    def create_new_tick_block(self, tick):
        """
        Create a block on TradeChain defining a new tick (either ask or bid) by using a (matchmaker) witness node.

        :param tick: The tick we want to persist to the TradeChain.
        :type tick: Tick
        :return: A deferred that fires when the witness node has signed and returned the block.
        :rtype: Deferred
        """
        def create_send_block(matchmaker):
            tx_dict = {
                "type": "tick",
                "tick": tick.to_block_dict()
            }
            tx_dict["tick"]['address'], tx_dict["tick"]['port'] = self.get_ipv8_address()
            return self.sign_block(matchmaker, matchmaker.public_key.key_to_bin(), tx_dict)

        return self.get_online_matchmaker().addCallback(create_send_block)

    @synchronized
    def create_new_cancel_order_block(self, order):
        """
        Create a block on TradeChain defining a cancellation of an order by using a (matchmaker) witness node.

        :param order: The tick order to cancel
        :type order: Order
        :return: A deferred that fires when the witness node has signed and returned the block.
        :rtype: Deferred
        """
        def create_send_block(matchmaker):
            tx_dict = {
                "type": "cancel_order",
                "trader_id": str(order.order_id.trader_id),
                "order_number": int(order.order_id.order_number)
            }
            return self.sign_block(matchmaker, matchmaker.public_key.key_to_bin(), tx_dict)\
                .addCallback(lambda (blk1, blk2): blk1)

        return self.get_online_matchmaker().addCallback(create_send_block)

    @synchronized
    def create_new_tx_init_block(self, peer, ask_order_dict, bid_order_dict, transaction):
        """
        Create a block on TradeChain defining initiation of a transaction.

        :param: peer: The peer to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param transaction: The transaction that will be initiated
        :type peer: Peer
        :type ask_order_dict: dict
        :type bid_order_dict: dict
        :type transaction: Transaction
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "type": "tx_init",
            "ask": ask_order_dict,
            "bid": bid_order_dict,
            "tx": transaction.to_dictionary()
        }
        return self.sign_block(peer, peer.public_key.key_to_bin(), tx_dict)\
            .addCallback(lambda (blk1, blk2): blk1)

    @synchronized
    def create_new_tx_payment_block(self, peer, payment):
        """
        Create a block on TradeChain defining payment during a transaction.

        :param peer: The peer that we did this transaction with
        :param payment: The payment to record
        :type peer: Peer
        :type payment: Payment
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "type": "tx_payment",
            "payment": payment.to_dictionary()
        }
        return self.sign_block(peer, peer.public_key.key_to_bin(), tx_dict)\
            .addCallback(lambda (blk1, blk2): blk1)

    @synchronized
    def create_new_tx_done_block(self, peer, ask_order_dict, bid_order_dict, transaction):
        """
        Create a block on TradeChain defining completion of a transaction.

        :param: peer: The peer to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param transaction: The transaction that has been completed
        :type peer: Peer
        :type transaction: Transaction
        :type ask_order_dict: dict
        :type bid_order_dict: dict
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "type": "tx_done",
            "ask": ask_order_dict,
            "bid": bid_order_dict,
            "tx": transaction.to_dictionary()
        }
        return self.sign_block(peer, peer.public_key.key_to_bin(), tx_dict)\
            .addCallback(lambda (blk1, blk2): blk1)

    def on_tick(self, tick, address):
        """
        Process an incoming tick.
        :param tick: the received tick to process
        :param address: tuple of (ip_address, port) defining the internet address of the creator of the tick
        """
        self.logger.debug("%s received from trader %s (price: %s, quantity: %s)", type(tick),
                          str(tick.order_id.trader_id), tick.price, tick.quantity)

        # Update the mid register with the current address
        self.update_ip(tick.order_id.trader_id, address)

        if self.is_matchmaker:
            insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid
            timeout_method = self.on_ask_timeout if isinstance(tick, Ask) else self.on_bid_timeout

            if not self.order_book.tick_exists(tick.order_id) and tick.quantity > Quantity(0, tick.quantity.wallet_id) \
                    and tick.order_id not in self.cancelled_orders:
                self.logger.debug("Inserting %s from %s (price: %s, quantity: %s)",
                                  tick, tick.order_id, tick.price, tick.quantity)
                insert_method(tick).addCallback(timeout_method)
                if self.tribler_session:
                    subject = NTFY_MARKET_ON_ASK if isinstance(tick, Ask) else NTFY_MARKET_ON_BID
                    self.tribler_session.notifier.notify(subject, NTFY_UPDATE, None, tick.to_dictionary())

                if self.order_book.tick_exists(tick.order_id):
                    # Check for new matches against the orders of this node
                    for order in self.order_manager.order_repository.find_all():
                        order_tick_entry = self.order_book.get_tick(order.order_id)
                        if not order.is_valid() or not order_tick_entry:
                            continue

                        self.match(order_tick_entry.tick)

                    # Only after we have matched our own orders, do the matching with other ticks if necessary
                    self.match(tick)

    def send_match_messages(self, matching_ticks, order_id):
        return [self.send_match_message(match_id, tick_entry.tick, order_id, matching_quantity)
                for match_id, tick_entry, matching_quantity in matching_ticks]

    def send_match_message(self, match_id, tick, recipient_order_id, matched_quantity):
        """
        Send a match message to a specific node
        :param match_id: The ID of the match
        :param tick: The matched tick
        :param recipient_order_id: The order id of the recipient, matching the tick
        :param matched_quantity: The quantity that has been matched
        """
        assert isinstance(match_id, str), type(match_id)
        assert isinstance(tick, Tick), type(tick)
        assert isinstance(recipient_order_id, OrderId), type(recipient_order_id)
        assert isinstance(matched_quantity, Quantity), type(matched_quantity)

        payload = tick.to_network(self.message_repository.next_identity())

        # Add ttl and the local wan address of the trader that created the tick
        if str(tick.order_id.trader_id) == self.mid:
            tick_address = self.get_ipv8_address()
        else:
            tick_address = self.lookup_ip(tick.order_id.trader_id)

        payload += (SocketAddress(tick_address[0], tick_address[1]), )

        # Add recipient order number, matched quantity, trader ID of the matched person, our own trader ID and match ID
        my_id = TraderId(self.mid)
        payload += (recipient_order_id.order_number, matched_quantity, tick.order_id.trader_id, my_id, match_id)

        # Lookup the remote address of the peer with the pubkey
        if str(recipient_order_id.trader_id) == self.mid:
            address = self.get_ipv8_address()
        else:
            address = self.lookup_ip(recipient_order_id.trader_id)

        self.logger.debug("Sending match message with order id %s and tick order id %s to trader "
                          "%s (ip: %s, port: %s)", str(recipient_order_id),
                          str(tick.order_id), recipient_order_id.trader_id, *address)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = MatchPayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 7, [auth, dist, payload])
        self.endpoint.send(address, packet)

    def received_match(self, source_address, data):
        """
        We received a match message from a matchmaker.
        """
        auth, _, payload = self._ez_unpack_auth(MatchPayload, data)
        peer = Peer(auth.public_key_bin, source_address)

        self.logger.debug("We received a match message for order %s.%s (matched quantity: %s)",
                          TraderId(self.mid), payload.recipient_order_number, payload.match_quantity)

        # We got a match, check whether we can respond to this match
        self.update_ip(payload.matchmaker_trader_id, source_address)
        self.update_ip(payload.trader_id, (payload.address.ip, payload.address.port))
        self.add_matchmaker(peer)

        order_id = OrderId(TraderId(self.mid), payload.recipient_order_number)
        other_order_id = OrderId(payload.trader_id, payload.order_number)
        order = self.order_manager.order_repository.find_by_id(order_id)
        if not order:
            self.logger.warning("Cannot find order %s in order repository!", order_id)
            return

        # Store the message for later
        self.incoming_match_messages[payload.match_id] = payload

        if order.status != "open" or order.available_quantity == Quantity(0, order.available_quantity.wallet_id):
            # Send a declined trade back
            decline_reason = DeclineMatchReason.ORDER_COMPLETED if order.status != "open" \
                else DeclineMatchReason.OTHER
            self.send_decline_match_message(payload.match_id,
                                            payload.matchmaker_trader_id,
                                            decline_reason)
            return

        propose_quantity = Quantity(min(float(order.available_quantity), float(payload.match_quantity)),
                                    order.available_quantity.wallet_id)

        # Reserve the quantity
        order.reserve_quantity_for_tick(other_order_id, propose_quantity)
        self.order_manager.order_repository.update(order)

        propose_trade = Trade.propose(
            self.message_repository.next_identity(),
            order.order_id,
            other_order_id,
            payload.price,
            propose_quantity,
            Timestamp.now()
        )
        self.send_proposed_trade(propose_trade, payload.match_id)

    def send_accept_match_message(self, match_id, matchmaker_trader_id, quantity):
        address = self.lookup_ip(matchmaker_trader_id)

        self.logger.debug("Sending accept match message with match id %s to trader "
                          "%s (ip: %s, port: %s)", str(match_id), str(matchmaker_trader_id), *address)

        payload = (self.message_repository.next_identity(), Timestamp.now(), match_id, quantity)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = AcceptMatchPayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 8, [auth, dist, payload])
        self.endpoint.send(address, packet)

    def received_accept_match(self, _, data):
        _, _, payload = self._ez_unpack_auth(AcceptMatchPayload, data)

        order_id, matched_order_id, reserved_quantity = self.matching_engine.matches[payload.match_id]
        self.logger.debug("Received accept-match message (%s vs %s), modifying quantities if necessary",
                          order_id, matched_order_id)
        tick_entry = self.order_book.get_tick(order_id)
        matched_tick_entry = self.order_book.get_tick(matched_order_id)

        # The ticks could already have been removed
        if tick_entry:
            tick_entry.release_for_matching(reserved_quantity)
            tick_entry.reserve_for_matching(payload.quantity)

        if matched_tick_entry:
            matched_tick_entry.release_for_matching(reserved_quantity)
            matched_tick_entry.reserve_for_matching(payload.quantity)

        del self.matching_engine.matches[payload.match_id]
        self.matching_engine.matching_strategy.used_match_ids.remove(payload.match_id)

    def send_decline_match_message(self, match_id, matchmaker_trader_id, decline_reason):
        del self.incoming_match_messages[match_id]
        address = self.lookup_ip(matchmaker_trader_id)

        self.logger.debug("Sending decline match message with match id %s to trader "
                          "%s (ip: %s, port: %s)", str(match_id), str(matchmaker_trader_id), *address)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = (self.message_repository.next_identity(), Timestamp.now(), match_id, decline_reason)
        payload = DeclineMatchPayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 9, [auth, dist, payload])
        self.endpoint.send(address, packet)

    def received_decline_match(self, _, data):
        _, _, payload = self._ez_unpack_auth(DeclineMatchPayload, data)
        order_id, matched_order_id, quantity = self.matching_engine.matches[payload.match_id]
        self.logger.debug("Received decline-match message for tick %s matched with %s", order_id, matched_order_id)

        # It could be that one or both matched tick(s) have already been removed from the order book by a
        # tx_done block. We have to account for that and act accordingly.
        tick_entry = self.order_book.get_tick(order_id)
        matched_tick_entry = self.order_book.get_tick(matched_order_id)

        if tick_entry:
            tick_entry.release_for_matching(quantity)

        if matched_tick_entry:
            matched_tick_entry.release_for_matching(quantity)
            if tick_entry:
                tick_entry.block_for_matching(matched_tick_entry.order_id)
                matched_tick_entry.block_for_matching(tick_entry.order_id)

        del self.matching_engine.matches[payload.match_id]
        self.matching_engine.matching_strategy.used_match_ids.remove(payload.match_id)

        if matched_tick_entry and payload.decline_reason == DeclineMatchReason.OTHER_ORDER_COMPLETED:
            self.order_book.remove_tick(matched_tick_entry.order_id)
            self.order_book.completed_orders.append(matched_tick_entry.order_id)

        if payload.decline_reason == DeclineMatchReason.ORDER_COMPLETED and tick_entry:
            self.order_book.remove_tick(tick_entry.order_id)
            self.order_book.completed_orders.append(tick_entry.order_id)
        elif tick_entry:
            # Search for a new match
            self.match(tick_entry.tick)

    def cancel_order(self, order_id):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and (order.status == "open" or order.status == "unverified"):
            self.order_manager.cancel_order(order_id)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

            if order.verified:
                return self.create_new_cancel_order_block(order).addCallback(self.send_block)

        return succeed(None)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade, match_id):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        assert isinstance(match_id, str), type(match_id)
        payload = proposed_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, proposed_trade, match_id))

        # Add the local address to the payload
        payload += (SocketAddress(self.get_ipv8_address()[0], self.get_ipv8_address()[1]),)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 10, [auth, dist, payload])
        self.endpoint.send(self.lookup_ip(proposed_trade.recipient_order_id.trader_id), packet)

        self.logger.debug("Sending proposed trade with own order id %s and other order id %s to trader "
                          "%s, quantity: %s (ip: %s, port: %s)", str(proposed_trade.order_id),
                          str(proposed_trade.recipient_order_id), proposed_trade.recipient_order_id.trader_id,
                          proposed_trade.quantity, *self.lookup_ip(proposed_trade.recipient_order_id.trader_id))

    def check_trade_payload_validity(self, payload):
        if str(payload.recipient_order_id.trader_id) != str(self.mid):
            return False, "this payload is not meant for this node"

        if not self.order_manager.order_repository.find_by_id(payload.recipient_order_id):
            return False, "order does not exist"

        return True, ''

    def get_outstanding_proposals(self, order_id, partner_order_id):
        return [(proposal_id, cache) for proposal_id, cache in self.request_cache._identifiers.iteritems()
                if isinstance(cache, ProposedTradeRequestCache)
                and cache.proposed_trade.order_id == order_id
                and cache.proposed_trade.recipient_order_id == partner_order_id]

    def received_proposed_trade(self, _, data):
        _, _, payload = self._ez_unpack_auth(TradePayload, data)

        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of proposed trade payload failed: %s", validation[1])
            return

        proposed_trade = ProposedTrade.from_network(payload)

        self.logger.debug("Proposed trade received with id: %s", str(proposed_trade.message_id))

        # Update the known IP address of the sender of this proposed trade
        self.update_ip(proposed_trade.message_id.trader_id,
                       (payload.address.ip, payload.address.port))

        order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

        # We can have a race condition where an ask/bid is created simultaneously on two different nodes.
        # In this case, both nodes first send a proposed trade and then receive a proposed trade from the other
        # node. To counter this, we have the following check.
        outstanding_proposals = self.get_outstanding_proposals(order.order_id, proposed_trade.order_id)
        if not order.is_ask() and outstanding_proposals:
            # Discard current outstanding proposed trade and continue
            self.logger.info("Discarding current outstanding proposals for order %s", proposed_trade.order_id)
            for proposal_id, _ in outstanding_proposals:
                request = self.request_cache.pop(u"proposed-trade", int(proposal_id.split(':')[1]))
                order.release_quantity_for_tick(proposed_trade.order_id, request.proposed_trade.quantity)

        should_decline = True
        decline_reason = 0
        if not order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif order.status == "completed":
            decline_reason = DeclinedTradeReason.ORDER_COMPLETED
        elif order.status == "expired":
            decline_reason = DeclinedTradeReason.ORDER_EXPIRED
        elif order.available_quantity == Quantity(0, order.available_quantity.wallet_id):
            decline_reason = DeclinedTradeReason.ORDER_RESERVED
        elif not proposed_trade.has_acceptable_price(order.is_ask(), order.price):
            decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_decline = False

        if should_decline:
            declined_trade = Trade.decline(self.message_repository.next_identity(),
                                           Timestamp.now(), proposed_trade, decline_reason)
            self.logger.debug("Declined trade made with id: %s for proposed trade with id: %s "
                              "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s), reason: %s",
                              str(declined_trade.message_id), str(proposed_trade.message_id),
                              order.is_valid(), order.available_quantity, order.reserved_quantity,
                              order.traded_quantity, decline_reason)
            self.send_declined_trade(declined_trade)
        else:
            self.logger.debug("Proposed trade received with id: %s for order with id: %s",
                              str(proposed_trade.message_id), str(order.order_id))

            if order.available_quantity >= proposed_trade.quantity:  # Enough quantity left
                order.reserve_quantity_for_tick(proposed_trade.order_id, proposed_trade.quantity)
                self.order_manager.order_repository.update(order)
                self.start_transaction(proposed_trade, '')
            else:  # Not all quantity can be traded
                counter_quantity = order.available_quantity
                order.reserve_quantity_for_tick(proposed_trade.order_id, counter_quantity)
                self.order_manager.order_repository.update(order)

                counter_trade = Trade.counter(self.message_repository.next_identity(),
                                              counter_quantity, Timestamp.now(), proposed_trade)
                self.logger.debug("Counter trade made with quantity: %s for proposed trade with id: %s",
                                  str(counter_trade.quantity), str(proposed_trade.message_id))
                self.send_counter_trade(counter_trade)

    def send_declined_trade(self, declined_trade):
        assert isinstance(declined_trade, DeclinedTrade), type(declined_trade)
        payload = declined_trade.to_network()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = DeclineTradePayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 11, [auth, dist, payload])
        self.endpoint.send(self.lookup_ip(declined_trade.recipient_order_id.trader_id), packet)

    def received_decline_trade(self, _, data):
        _, _, payload = self._ez_unpack_auth(DeclineTradePayload, data)

        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of decline trade payload failed: %s", validation[1])
            return

        declined_trade = DeclinedTrade.from_network(payload)

        if not self.request_cache.has(u"proposed-trade", declined_trade.proposal_id):
            self.logger.warning("declined trade cache with id %s not found", declined_trade.proposal_id)
            return

        request = self.request_cache.pop(u"proposed-trade", declined_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)
        order.release_quantity_for_tick(declined_trade.order_id, request.proposed_trade.quantity)
        self.order_manager.order_repository.update(order)

        # Just remove the tick with the order id of the other party and try to find a new match
        self.logger.debug("Received declined trade (proposal id: %d), trying to find a new match for this order",
                          declined_trade.proposal_id)

        # Let the matchmaker know that we don't have a match
        match_payload = self.incoming_match_messages[request.match_id]
        match_decline_reason = DeclineMatchReason.OTHER
        if declined_trade.decline_reason == DeclinedTradeReason.ORDER_COMPLETED:
            match_decline_reason = DeclineMatchReason.OTHER_ORDER_COMPLETED

        self.send_decline_match_message(request.match_id, match_payload.matchmaker_trader_id, match_decline_reason)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        payload = counter_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, counter_trade, ''))

        # Add the local address to the payload
        payload += (SocketAddress(self.get_ipv8_address()[0], self.get_ipv8_address()[1]),)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 12, [auth, dist, payload])
        self.endpoint.send(self.lookup_ip(counter_trade.recipient_order_id.trader_id), packet)

    def received_counter_trade(self, _, data):
        _, _, payload = self._ez_unpack_auth(TradePayload, data)

        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of counter trade payload failed: %s", validation[1])
            return

        counter_trade = CounterTrade.from_network(payload)

        if not self.request_cache.has(u"proposed-trade", counter_trade.proposal_id):
            self.logger.warning("proposed trade cache with id %s not found", counter_trade.proposal_id)
            return

        request = self.request_cache.pop(u"proposed-trade", counter_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)
        should_decline = True
        decline_reason = 0
        if not order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif not counter_trade.has_acceptable_price(order.is_ask(), order.price):
            decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_decline = False

        if should_decline:
            declined_trade = Trade.decline(self.message_repository.next_identity(),
                                           Timestamp.now(), counter_trade, decline_reason)
            self.logger.debug("Declined trade made with id: %s for counter trade with id: %s",
                              str(declined_trade.message_id), str(counter_trade.message_id))
            self.send_declined_trade(declined_trade)
        else:
            order.release_quantity_for_tick(counter_trade.order_id, request.proposed_trade.quantity)
            order.reserve_quantity_for_tick(counter_trade.order_id, counter_trade.quantity)
            self.order_manager.order_repository.update(order)
            self.start_transaction(counter_trade, request.match_id)

            # Let the matchmaker know that we have a match
            match_payload = self.incoming_match_messages[request.match_id]
            self.send_accept_match_message(request.match_id, match_payload.matchmaker_trader_id,
                                           counter_trade.quantity)

    # Transactions
    def start_transaction(self, proposed_trade, match_id):
        order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)
        transaction = self.transaction_manager.create_from_proposed_trade(proposed_trade, match_id)
        start_transaction = StartTransaction(self.message_repository.next_identity(),
                                             transaction.transaction_id, order.order_id,
                                             proposed_trade.order_id, proposed_trade.proposal_id,
                                             proposed_trade.price, proposed_trade.quantity, Timestamp.now())
        self.send_start_transaction(transaction, start_transaction)

    # Start transaction
    def send_start_transaction(self, transaction, start_transaction):
        payload = start_transaction.to_network()

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = StartTransactionPayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 13, [auth, dist, payload])
        self.endpoint.send(self.lookup_ip(transaction.partner_order_id.trader_id), packet)

    def received_start_transaction(self, source_address, data):
        auth, _, payload = self._ez_unpack_auth(StartTransactionPayload, data)
        peer = Peer(auth.public_key_bin, source_address)

        start_transaction = StartTransaction.from_network(payload)

        if not self.request_cache.has(u"proposed-trade", start_transaction.proposal_id):
            return

        request = self.request_cache.pop(u"proposed-trade", start_transaction.proposal_id)

        # The recipient_order_id in the start_transaction message is our own order
        order = self.order_manager.order_repository.find_by_id(start_transaction.recipient_order_id)
        if not order:
            return

        # Let the matchmaker know that we have a match
        if request.match_id != '':
            match_payload = self.incoming_match_messages[request.match_id]
            self.send_accept_match_message(request.match_id, match_payload.matchmaker_trader_id,
                                           start_transaction.quantity)

        transaction = self.transaction_manager.create_from_start_transaction(start_transaction,
                                                                             request.match_id)
        incoming_address, outgoing_address = self.get_order_addresses(order)

        def build_tx_init_block(other_order_dict):
            my_order_dict = order.to_status_dictionary()
            my_order_dict["ip"], my_order_dict["port"] = self.get_ipv8_address()

            if order.is_ask():
                ask_order_dict = my_order_dict
                bid_order_dict = other_order_dict
            else:
                ask_order_dict = other_order_dict
                bid_order_dict = my_order_dict

            # Create a tx_init block to capture that we are going to initiate a transaction
            self.create_new_tx_init_block(peer, ask_order_dict, bid_order_dict, transaction).\
                addCallback(lambda _: self.send_wallet_info(transaction, incoming_address, outgoing_address))

        self.send_order_status_request(start_transaction.order_id).addCallback(build_tx_init_block)

    def send_order_status_request(self, order_id):
        self.logger.debug("Sending order status request to trader %s (number: %d)",
                          order_id.trader_id, order_id.order_number)

        request_deferred = Deferred()
        cache = self.request_cache.add(OrderStatusRequestCache(self, request_deferred))

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        message_id = self.message_repository.next_identity()
        payload = OrderStatusRequestPayload(message_id, Timestamp.now(), order_id, cache.number).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 16, [auth, dist, payload])
        self.endpoint.send(self.lookup_ip(order_id.trader_id), packet)

        return request_deferred

    def received_order_status_request(self, source_address, data):
        auth, dist, payload = self._ez_unpack_auth(OrderStatusRequestPayload, data)
        order = self.order_manager.order_repository.find_by_id(payload.order_id)

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()

        address = SocketAddress(self.get_ipv8_address()[0], self.get_ipv8_address()[1])
        order_payload = list(order.to_network(self.message_repository.next_identity()))
        order_payload.insert(len(order_payload) - 1, address)
        order_payload.append(payload.identifier)
        new_payload = OrderStatusResponsePayload(*order_payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 17, [auth, dist, new_payload])
        self.endpoint.send(source_address, packet)

    def received_order_status(self, _, data):
        _, _, payload = self._ez_unpack_auth(OrderStatusResponsePayload, data)
        request = self.request_cache.pop(u"order-status-request", payload.identifier)

        # Convert the order status to a dictionary that is saved on TradeChain
        order_dict = {
            "trader_id": str(payload.message_id.trader_id),
            "order_number": int(payload.order_number),
            "price": float(payload.price),
            "price_type": payload.price.wallet_id,
            "quantity": float(payload.quantity),
            "quantity_type": payload.quantity.wallet_id,
            "traded_quantity": float(payload.traded_quantity),
            "timeout": float(payload.timeout),
            "timestamp": float(payload.timestamp),
            "ip": payload.address.ip,
            "port": payload.address.port
        }

        reactor.callFromThread(request.request_deferred.callback, order_dict)

    def send_wallet_info(self, transaction, incoming_address, outgoing_address):
        assert isinstance(transaction, Transaction), type(transaction)

        # Update the transaction with the address information
        transaction.incoming_address = incoming_address
        transaction.outgoing_address = outgoing_address

        self.logger.debug("Sending wallet info to trader %s (incoming address: %s, outgoing address: %s",
                          transaction.partner_order_id.trader_id, incoming_address, outgoing_address)

        message_id = self.message_repository.next_identity()
        payload = (message_id, Timestamp.now(), transaction.transaction_id, incoming_address, outgoing_address)
        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()

        new_payload = WalletInfoPayload(*payload).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 14, [auth, dist, new_payload])
        self.endpoint.send(self.lookup_ip(transaction.partner_order_id.trader_id), packet)

        transaction.sent_wallet_info = True
        self.transaction_manager.transaction_repository.update(transaction)

    def received_wallet_info(self, _, data):
        _, _, payload = self._ez_unpack_auth(WalletInfoPayload, data)
        self.logger.info("Received wallet info from trader %s", payload.message_id.trader_id)

        transaction = self.transaction_manager.find_by_id(payload.transaction_id)
        transaction.received_wallet_info = True

        transaction.partner_outgoing_address = payload.outgoing_address
        transaction.partner_incoming_address = payload.incoming_address

        if not transaction.sent_wallet_info:
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)
            incoming_address, outgoing_address = self.get_order_addresses(order)
            self.send_wallet_info(transaction, incoming_address, outgoing_address)
        else:
            self.send_payment(transaction)

        self.transaction_manager.transaction_repository.update(transaction)

    def send_payment(self, transaction):
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)
        wallet_id = transaction.total_quantity.wallet_id if order.is_ask() else transaction.price.wallet_id

        wallet = self.wallets[wallet_id]
        if not wallet or not wallet.created:
            raise RuntimeError("No %s wallet present" % wallet_id)

        transfer_amount = transaction.next_payment(order.is_ask(), wallet.min_unit(), self.use_incremental_payments)
        if order.is_ask():
            transfer_quantity = transfer_amount
            transfer_price = Price(0.0, transaction.price.wallet_id)
        else:
            transfer_quantity = Quantity(0.0, transaction.total_quantity.wallet_id)
            transfer_price = transfer_amount

        payment_tup = (transfer_quantity, transfer_price)

        # While this conditional is not very pretty, the alternative is to move all this logic to the wallet which
        # requires the wallet to know about transactions, the market community and IPv8.
        if isinstance(wallet, TrustchainWallet):
            peer = Peer(b64decode(str(transaction.partner_incoming_address)),
                        address=self.lookup_ip(transaction.partner_order_id.trader_id))
            transfer_deferred = wallet.transfer(float(transfer_amount), peer)
        else:
            transfer_deferred = wallet.transfer(float(transfer_amount), str(transaction.partner_incoming_address))

        def on_payment_error(failure):
            """
            When a payment fails, log the error and still send a payment message to inform the other party that the
            payment has failed.
            """
            self.logger.error("Payment of %s to %s failed: %s", transfer_amount,
                              str(transaction.partner_incoming_address), failure.value)
            self.send_payment_message(PaymentId(''), transaction, payment_tup, False)

        success_cb = lambda txid: self.send_payment_message(PaymentId(txid), transaction, payment_tup, True)
        transfer_deferred.addCallbacks(success_cb, on_payment_error)

    def send_payment_message(self, payment_id, transaction, payment, success):
        if not success:
            self.abort_transaction(transaction)

        if success and float(payment[0]) > 0:  # Release some of the reserved quantity
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)
            order.add_trade(transaction.partner_order_id, payment[0])
            self.order_manager.order_repository.update(order)

        message_id = self.message_repository.next_identity()
        payment_message = self.transaction_manager.create_payment_message(
            message_id, payment_id, transaction, payment, success)
        self.logger.debug("Sending payment message with price %s and quantity %s (success? %s)",
                          payment_message.transferee_price, payment_message.transferee_quantity, success)

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_SENT, NTFY_UPDATE, None,
                                                 payment_message.to_dictionary())

        global_time = self.claim_global_time()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()

        new_payload = PaymentPayload(*payment_message.to_network()).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        packet = self._ez_pack(self._prefix, 15, [auth, dist, new_payload])
        self.endpoint.send(self.lookup_ip(transaction.partner_order_id.trader_id), packet)

    def received_payment_message(self, source_address, data):
        auth, _, payload = self._ez_unpack_auth(PaymentPayload, data)
        peer = Peer(auth.public_key_bin, source_address)

        payment = Payment.from_network(payload)
        self.logger.debug("Received payment message with price %s and quantity %s",
                          payment.transferee_price, payment.transferee_quantity)
        transaction = self.transaction_manager.find_by_id(payment.transaction_id)

        if not transaction or transaction.is_payment_complete():
            self.logger.warning("Transaction %s for payment message cannot be found", payment.transaction_id)
            return

        order = self.order_manager.order_repository.find_by_id(transaction.order_id)

        if not order:
            self.logger.warning("Order %s for payment message cannot be found", transaction.order_id)
            return

        if not payment.success:
            self.logger.debug("Payment with id %s not successful, aborting transaction", payment.payment_id)
            transaction.add_payment(payment)
            self.transaction_manager.transaction_repository.update(transaction)
            self.abort_transaction(transaction)

            if self.tribler_session:
                self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE,
                                                     None, payment.to_dictionary())
            return

        if order.is_ask():
            wallet_id = payment.transferee_price.wallet_id
        else:
            wallet_id = payment.transferee_quantity.wallet_id

        wallet = self.wallets[wallet_id]
        transaction_deferred = wallet.monitor_transaction(str(payment.payment_id))
        transaction_deferred.addCallback(lambda _: self.received_payment(peer, payment, transaction))

    def received_payment(self, peer, payment, transaction):
        self.logger.debug("Received payment with id %s (price: %s, quantity: %s)",
                          payment.payment_id, payment.transferee_price, payment.transferee_quantity)
        transaction.add_payment(payment)
        self.transaction_manager.transaction_repository.update(transaction)
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)

        if float(payment.transferee_quantity) > 0:  # Release some of the reserved quantity
            order.add_trade(transaction.partner_order_id, payment.transferee_quantity)
            self.order_manager.order_repository.update(order)

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE, None,
                                                 payment.to_dictionary())

        def on_tx_done_signed(block):
            """
            We received the signed block from the counterparty, wrap everything up
            """
            self.notify_transaction_complete(transaction.to_dictionary(), mine=True)
            self.send_transaction_completed(transaction, block)

        def build_tx_done_block(other_order_dict):
            my_order_dict = order.to_status_dictionary()
            my_order_dict["ip"], my_order_dict["port"] = self.get_ipv8_address()

            if order.is_ask():
                ask_order_dict = my_order_dict
                bid_order_dict = other_order_dict
            else:
                ask_order_dict = other_order_dict
                bid_order_dict = my_order_dict

            self.create_new_tx_done_block(peer, ask_order_dict, bid_order_dict, transaction)\
                .addCallback(on_tx_done_signed)

        # Record this payment on TradeChain
        def on_payment_recorded(_):
            if not transaction.is_payment_complete():
                self.send_payment(transaction)
            else:
                self.send_order_status_request(transaction.partner_order_id).addCallback(build_tx_done_block)

        self.create_new_tx_payment_block(peer, payment).addCallback(on_payment_recorded)

    def abort_transaction(self, transaction):
        """
        Abort a specific transaction by releasing all reserved quantity for this order.
        """
        self.logger.error("Aborting transaction %s", transaction.transaction_id)
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)
        if (transaction.total_quantity - transaction.transferred_quantity) > \
                Quantity(0, transaction.total_quantity.wallet_id):
            order.release_quantity_for_tick(transaction.partner_order_id,
                                            transaction.total_quantity - transaction.transferred_quantity)
            self.order_manager.order_repository.update(order)

    def notify_transaction_complete(self, tx_dict, mine=False):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None,
                                                 {"tx": tx_dict, "mine": mine})

    def send_transaction_completed(self, transaction, block):
        """
        Let the matchmaker know that the transaction has been completed.
        :param transaction: The completed transaction.
        :param block: The block created by this peer defining the transaction.
        """
        if not transaction.match_id or transaction.match_id not in self.incoming_match_messages:
            return

        self.logger.debug("Sending transaction completed (match id: %s)", transaction.match_id)

        # Lookup the remote address of the peer with the pubkey
        match_payload = self.incoming_match_messages[transaction.match_id]
        del self.incoming_match_messages[transaction.match_id]

        linked_block = self.market_database.get_linked(block) or block
        self.send_block_pair(block, linked_block, address=self.lookup_ip(match_payload.matchmaker_trader_id))

    def on_transaction_completed_message(self, block1, block2):
        tx_dict = block1.transaction
        self.logger.debug("Received transaction-completed message")
        if not self.is_matchmaker:
            return

        # Update ticks in order book, release the reserved quantity and find a new match
        quantity = Quantity(tx_dict["tx"]["quantity"], tx_dict["tx"]["quantity_type"])
        self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"], quantity)
        ask_order_id = OrderId(TraderId(tx_dict["ask"]["trader_id"]), OrderNumber(tx_dict["ask"]["order_number"]))
        bid_order_id = OrderId(TraderId(tx_dict["bid"]["trader_id"]), OrderNumber(tx_dict["bid"]["order_number"]))
        self.match_order_ids([ask_order_id, bid_order_id])

        # Broadcast the pair of blocks
        self.send_block_pair(block1, block2)

        order_id = OrderId(TraderId(tx_dict["tx"]["trader_id"]), OrderNumber(tx_dict["tx"]["order_number"]))
        tick_entry_sender = self.order_book.get_tick(order_id)
        if tick_entry_sender:
            self.match(tick_entry_sender.tick)

    def on_transaction_completed_bc_message(self, block1, _):
        self.logger.debug("Received transaction-completed-bc message")
        if not self.is_matchmaker or not self.persistence.get_linked(block1):
            return

        tx_dict = block1.transaction

        self.notify_transaction_complete(tx_dict["tx"])

        # Update ticks in order book, release the reserved quantity
        quantity = Quantity(tx_dict["tx"]["quantity"], tx_dict["tx"]["quantity_type"])
        self.order_book.update_ticks(tx_dict["ask"], tx_dict["bid"], quantity, unreserve=False)
        ask_order_id = OrderId(TraderId(tx_dict["ask"]["trader_id"]), OrderNumber(tx_dict["ask"]["order_number"]))
        bid_order_id = OrderId(TraderId(tx_dict["bid"]["trader_id"]), OrderNumber(tx_dict["bid"]["order_number"]))
        self.match_order_ids([ask_order_id, bid_order_id])

    def compute_reputation(self):
        """
        Compute the reputation of peers in the community
        """
        rep_manager = TemporalPagerankReputationManager(self.persistence.get_all_blocks())
        self.reputation_dict = rep_manager.compute(self.my_peer.public_key.key_to_bin())
