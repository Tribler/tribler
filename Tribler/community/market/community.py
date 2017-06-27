import time
from base64 import b64decode

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall, deferLater

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT, NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import OrderId, Order
from Tribler.community.market.core.order_manager import OrderManager
from Tribler.community.market.core.order_repository import DatabaseOrderRepository, MemoryOrderRepository
from Tribler.community.market.core.orderbook import DatabaseOrderBook
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid, Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, CounterTrade
from Tribler.community.market.core.transaction import StartTransaction, TransactionId, Transaction
from Tribler.community.market.core.transaction_manager import TransactionManager
from Tribler.community.market.core.transaction_repository import DatabaseTransactionRepository,\
    MemoryTransactionRepository
from Tribler.community.market.core.ttl import Ttl
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.database import MarketDB
from Tribler.community.market.payload import OfferPayload, TradePayload, DeclinedTradePayload,\
    StartTransactionPayload, TransactionPayload, WalletInfoPayload, MarketIntroPayload, OfferSyncPayload,\
    PaymentPayload, CancelOrderPayload
from Tribler.community.market.reputation.pagerank_manager import PagerankReputationManager
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.requestcache import IntroductionRequestCache, NumberCache
from Tribler.dispersy.resolution import PublicResolution


class ProposedTradeRequestCache(NumberCache):
    """
    This cache keeps track of outstanding proposed trade messages.
    """
    def __init__(self, community, proposed_trade):
        super(ProposedTradeRequestCache, self).__init__(community.request_cache, u"proposed-trade",
                                                        proposed_trade.proposal_id)
        self.community = community
        self.proposed_trade = proposed_trade

    def on_timeout(self):
        # Just remove the reserved quantity from the order
        order = self.community.order_manager.order_repository.find_by_id(self.proposed_trade.order_id)
        order.release_quantity_for_tick(self.proposed_trade.recipient_order_id, self.proposed_trade.quantity)
        self.community.order_manager.order_repository.update(order)

        self._logger.debug("Proposed trade timed out, trying to find a new match for this order")
        self.community.order_book.remove_tick(self.proposed_trade.recipient_order_id)
        self.community.match(order)


class MarketCommunity(Community):
    """
    Community for general asset trading.
    """

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Tue Mar 22 23:29:40 2016
        # curve: NID_sect571r1
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059c773
        # dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8dbbb634906989395d36
        # 6888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdfdabb434396d23945d1239f88de4935
        # 467424c7cc02b6579e45f63ee
        # pub-sha1 dda25d128ebabe6b588384d05b8ff46153f98c78
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQBWa8MCSUDS7o7TqJmYYKOCSRyNgWc
        # dz2sKayfuE1Q+mvYrMA1EnpvXBGHORX5uaRg4RbszMz8XbG12LqGvXAYhupF2Nu7
        # Y0kGmJOV02aIjQCPQRmtDn9Fudq3+z14oAZcX3qGa3jLjlm5p9BIzA1lDFqGvf2r
        # tDQ5bSOUXRI5+I3kk1RnQkx8wCtleeRfY+4=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403e6f247258f60430f570cb02f5d830426fefaec" \
                     "76a506db6e806ea0f10ee6061996f54fe6960e19978b32a0c92ece60dc0b85deaa07b7fd13fa6e54205154f78c1a" \
                     "294effb43801045fb17124a85e42a338275d109da989942337dbc6c3b06dc2c4c62d0c2b64f2cdfe02aad5c058be" \
                     "23027e4b99fc7271a94d176f020543e06da7a371f9794240dae44e9bc130a1a6".decode('hex')
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def __init__(self, *args, **kwargs):
        super(MarketCommunity, self).__init__(*args, **kwargs)
        self.mid = None
        self.mid_register = {}
        self.relayed_ticks = {}  # Dictionary of OrderId -> Timestamp
        self.relayed_cancels = []
        self.order_manager = None
        self.order_book = None
        self.market_database = None
        self.matching_engine = None
        self.tribler_session = None
        self.tradechain_community = None
        self.wallets = None
        self.transaction_manager = None
        self.reputation_dict = {}
        self.use_local_address = False
        self.matching_enabled = True
        self.use_incremental_payments = True
        self.validate_tick_signatures = True
        self.pending_proposed_trades = []  # List of tuple (order_id, ProposedTrade)

    def initialize(self, tribler_session=None, tradechain_community=None, wallets=None, use_database=True):
        super(MarketCommunity, self).initialize()

        self.mid = self.my_member.mid.encode('hex')
        message_repository = MemoryMessageRepository(self.mid)
        self.market_database = MarketDB(self.dispersy.working_directory)
        self.order_book = DatabaseOrderBook(message_repository, self.market_database)
        self.order_book.restore_from_database()

        for trader in self.market_database.get_traders():
            self.update_ip(TraderId(str(trader[0])), (str(trader[1]), trader[2]))

        if use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
            transaction_repository = DatabaseTransactionRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)
            transaction_repository = MemoryTransactionRepository(self.mid)

        self.order_manager = OrderManager(order_repository)
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))
        self.tribler_session = tribler_session
        self.tradechain_community = tradechain_community
        self.wallets = wallets or {}
        self.transaction_manager = TransactionManager(transaction_repository)

        # Determine the reputation of peers every five minutes
        self.register_task("calculate_reputation", LoopingCall(self.compute_reputation)).start(300.0, now=False)

        self._logger.info("Market community initialized with mid %s", self.mid)

    def initiate_meta_messages(self):
        return super(MarketCommunity, self).initiate_meta_messages() + [
            Message(self, u"ask",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_tick_message,
                    self.on_tick),
            Message(self, u"bid",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_tick_message,
                    self.on_tick),
            Message(self, u"cancel-order",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    CancelOrderPayload(),
                    self.check_message,
                    self.on_cancel_order),
            Message(self, u"offer-sync",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    OfferSyncPayload(),
                    self.check_tick_message,
                    self.on_offer_sync),
            Message(self, u"proposed-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_trade_message,
                    self.on_proposed_trade),
            Message(self, u"declined-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    DeclinedTradePayload(),
                    self.check_trade_message,
                    self.on_declined_trade),
            Message(self, u"counter-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_trade_message,
                    self.on_counter_trade),
            Message(self, u"start-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    StartTransactionPayload(),
                    self.check_transaction_message,
                    self.on_start_transaction),
            Message(self, u"wallet-info",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    WalletInfoPayload(),
                    self.check_transaction_message,
                    self.on_wallet_info),
            Message(self, u"payment",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    PaymentPayload(),
                    self.check_transaction_message,
                    self.on_payment_message),
            Message(self, u"end-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TransactionPayload(),
                    self.check_transaction_message,
                    self.on_end_transaction)
        ]

    def _initialize_meta_messages(self):
        super(MarketCommunity, self)._initialize_meta_messages()

        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution,
                      ori.distribution, ori.destination, MarketIntroPayload(), ori.check_callback, ori.handle_callback)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), MarketConversion(self)]

    def get_wallet_ids(self):
        """
        Return the IDs of all wallets in the market community.
        """
        return self.wallets.keys()

    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        order_ids = [str(order_id) for order_id in self.order_book.get_order_ids()]
        if len(order_ids) == 0:
            orders_bloom_filter = None
        else:
            orders_bloom_filter = BloomFilter(0.005, len(order_ids), prefix=' ')
            orders_bloom_filter.add_keys(order_ids)

        cache = self._request_cache.add(IntroductionRequestCache(self, destination))
        payload = (destination.sock_addr, self._dispersy.lan_address, self._dispersy.wan_address, True,
                   self._dispersy.connection_type, None, cache.number, orders_bloom_filter)

        destination.walk(time.time())
        self.add_candidate(destination)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=payload)

        self._logger.debug(u"%s %s sending introduction request to %s", self.cid.encode("HEX"), type(self), destination)

        self._dispersy.store_update_forward([request], False, False, True)
        return request

    def on_introduction_request(self, messages):
        super(MarketCommunity, self).on_introduction_request(messages)

        for message in messages:
            orders_bloom_filter = message.payload.orders_bloom_filter
            for order_id in self.order_book.get_order_ids():
                if not orders_bloom_filter or str(order_id) not in orders_bloom_filter:
                    is_ask = self.order_book.ask_exists(order_id)
                    entry = self.order_book.get_ask(order_id) if is_ask else self.order_book.get_bid(order_id)
                    self.send_offer_sync(message.candidate, entry.tick)

    def check_message(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                self._logger.debug("Allowing message %s", message)
                yield message
            else:
                self._logger.debug("Delaying message %s", message)
                yield DelayMessageByProof(message)

    def check_tick_message(self, messages):
        for message in messages:
            if message.name == u"offer-sync":
                tick = Ask.from_network(message.payload)\
                    if message.payload.is_ask else Bid.from_network(message.payload)
            else:
                tick = Ask.from_network(message.payload)\
                    if message.name == u"ask" else Bid.from_network(message.payload)
            allowed, _ = self._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            if tick.order_id.trader_id == TraderId(self.mid):
                yield DropMessage(message, "We don't accept ticks originating from ourselves")
                continue

            if self.validate_tick_signatures and not tick.has_valid_signature():
                yield DropMessage(message, "Invalid signature of %s message" % message.name)
                continue

            yield message

    @inlineCallbacks
    def unload_community(self):
        # Store all traders to the database
        for trader_id, sock_addr in self.mid_register.iteritems():
            self.market_database.add_trader_identity(trader_id, sock_addr[0], sock_addr[1])

        # Save the ticks to the database
        self.order_book.save_to_database()

        self.order_book.cancel_all_pending_tasks()
        yield super(MarketCommunity, self).unload_community()

    def get_dispersy_address(self):
        """
        Returns the address of the Dispersy instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.dispersy.lan_address if self.use_local_address else self.dispersy.wan_address

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

    def match(self, order):
        """
        Try to find a match for a specific order and send proposed trade messages if there is a match
        :param order: The order to match
        """
        if not self.matching_enabled:
            return

        matched_ticks = self.matching_engine.match(order.price, order.available_quantity, order.is_ask())

        # Create proposed trade messages and reserve quantity
        proposed_trades = []
        for matched_tick, quantity in matched_ticks:
            order.reserve_quantity_for_tick(matched_tick.order_id, quantity)
            proposed_trades.append(Trade.propose(
                self.order_book.message_repository.next_identity(),
                order.order_id,
                matched_tick.order_id,
                matched_tick.price,
                quantity,
                Timestamp.now()
            ))

        if proposed_trades:
            self.order_manager.order_repository.update(order)
        self.send_proposed_trade_messages(proposed_trades)

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

        self._logger.debug("Updating ip of trader %s to (%s, %s)", trader_id, ip[0], ip[1])
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

    # Ask
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

        # Search for matches
        self.match(order)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        tick.sign(self.my_member)
        assert isinstance(tick, Ask), type(tick)
        self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
        self.send_tick(tick)

        self._logger.debug("Ask created with price %s and quantity %s", price, quantity)

        return order

    def send_tick(self, tick):
        """
        Send a tick message

        :param tick: The message to send
        :type tick: Tick
        """
        assert isinstance(tick, (Ask, Bid)), type(tick)

        self._logger.debug("%s send with id: %s for order with id: %s", type(tick),
                           str(tick.message_id), str(tick.order_id))

        payload = tick.to_network()

        # Add ttl and the local wan address
        payload += (Ttl.default(),) + self.get_dispersy_address()

        meta = self.get_meta_message(u"ask" if isinstance(tick, Ask) else u"bid")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def on_tick(self, messages):
        for message in messages:
            tick = Ask.from_network(message.payload) if message.name == u"ask" else Bid.from_network(message.payload)

            self._logger.debug("%s received from trader %s (price: %s, quantity: %s)", type(tick),
                               str(tick.order_id.trader_id), tick.price, tick.quantity)

            # Update the pubkey register with the current address
            self.update_ip(tick.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid
            timeout_method = self.on_ask_timeout if isinstance(tick, Ask) else self.on_bid_timeout

            if not self.order_book.tick_exists(tick.order_id) and tick.quantity > Quantity(0, tick.quantity.wallet_id):
                self._logger.debug("Inserting %s from %s (price: %s, quantity: %s)",
                                   tick, tick.order_id, tick.price, tick.quantity)
                insert_method(tick).addCallback(timeout_method)
                if self.tribler_session:
                    subject = NTFY_MARKET_ON_ASK if isinstance(tick, Ask) else NTFY_MARKET_ON_BID
                    self.tribler_session.notifier.notify(subject, NTFY_UPDATE, None, tick.to_dictionary())

                # Check for new matches against the orders of this node
                for order in self.order_manager.order_repository.find_all():
                    if order.is_ask() and order.is_valid():
                        self.match(order)
            elif self.order_book.tick_exists(tick.order_id) and \
                    self.order_book.get_tick(tick.order_id).tick.timestamp < tick.timestamp:
                # Update the tick with a newer one
                self.order_book.remove_tick(tick.order_id)
                if tick.quantity > Quantity(0, tick.quantity.wallet_id):
                    self._logger.debug("Updating %s from %s (price: %s, quantity: %s)",
                                       tick, tick.order_id, tick.price, tick.quantity)
                    insert_method(tick).addCallback(timeout_method)

            if tick.order_id not in self.relayed_ticks or self.relayed_ticks[tick.order_id] < tick.timestamp:
                self.relayed_ticks[tick.order_id] = tick.timestamp
                self.relay_message(message)

    def relay_message(self, message):
        # Check if message needs to be send on
        ttl = message.payload.ttl

        ttl.make_hop()  # Complete the hop from the previous node

        if ttl.is_alive():  # The ttl is still alive and can be forwarded
            self.dispersy.store_update_forward([message], True, True, True)

    # Bid
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

        # Search for matches
        self.match(order)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        tick.sign(self.my_member)
        assert isinstance(tick, Bid), type(tick)
        self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
        self.send_tick(tick)

        self._logger.debug("Bid created with price %s and quantity %s", price, quantity)

        return order

    def send_cancel_order(self, order):
        """
        Send a cancel-order message to the community
        """
        assert isinstance(order, Order), type(order)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"cancel-order")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=(message_id.trader_id, message_id.message_number, Timestamp.now(),
                     order.order_id.order_number, Ttl.default())
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_cancel_order(self, messages):
        for message in messages:
            order_id = OrderId(message.payload.trader_id, message.payload.order_number)
            if self.order_book.tick_exists(order_id):
                self.order_book.remove_tick(order_id)

            if str(order_id) not in self.relayed_cancels:
                self.relayed_cancels.append(str(order_id))

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    def send_offer_sync(self, target_candidate, tick):
        """
        Send an offer sync message

        :param target_candidate: The candidate to send this message to
        :type: target_candidate: WalkCandidate
        :param tick: The tick to send
        :type tick: Tick
        """
        assert isinstance(target_candidate, WalkCandidate), type(target_candidate)
        assert isinstance(tick, Tick), type(tick)

        self._logger.debug("Offer sync send with id: %s for order with id: %s",
                           str(tick.message_id), str(tick.order_id))

        payload = tick.to_network()

        # Add ttl and the trader wan address
        trader_ip = self.lookup_ip(tick.order_id.trader_id)
        payload += (Ttl(1),) + trader_ip + (isinstance(tick, Ask),)

        meta = self.get_meta_message(u"offer-sync")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(target_candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

    def on_offer_sync(self, messages):
        for message in messages:
            if message.payload.is_ask:
                tick = Ask.from_network(message.payload)
                insert_method = self.order_book.insert_ask
                timeout_method = self.on_ask_timeout
            else:
                tick = Bid.from_network(message.payload)
                insert_method = self.order_book.insert_bid
                timeout_method = self.on_bid_timeout

            self.update_ip(tick.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not self.order_book.tick_exists(tick.order_id) or \
                    float(self.order_book.get_tick(tick.order_id).tick.timestamp) < float(tick.timestamp):
                insert_method(tick).addCallback(timeout_method)

                if self.tribler_session:
                    notify_subject = NTFY_MARKET_ON_ASK if message.payload.is_ask else NTFY_MARKET_ON_BID
                    self.tribler_session.notifier.notify(notify_subject, NTFY_UPDATE, None, tick.to_dictionary())

    def cancel_order(self, order_id):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and order.status == "open":
            self.order_manager.cancel_order(order_id)
            self.order_book.remove_tick(order_id)
            self.send_cancel_order(order)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        destination, payload = proposed_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, proposed_trade))

        # Add the local address to the payload
        payload += self.get_dispersy_address()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        self._logger.debug("Sending proposed trade with own order id %s and other order id %s to trader "
                           "%s (ip: %s, port: %s)", str(proposed_trade.order_id),
                           str(proposed_trade.recipient_order_id), destination, *self.lookup_ip(destination))

        meta = self.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

    def send_proposed_trade_messages(self, messages):
        return [self.send_proposed_trade(message) for message in messages]

    def check_trade_message(self, messages):
        for message in messages:
            my_order_id = OrderId(message.payload.recipient_trader_id, message.payload.recipient_order_number)

            allowed, _ = self._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            if str(my_order_id.trader_id) != str(self.mid):
                yield DropMessage(message, "%s not for this node" % message.name)
                continue

            if not self.order_manager.order_repository.find_by_id(my_order_id):
                yield DropMessage(message, "Order in %s does not exist" % message.name)
                continue

            if (message.name == 'declined-trade' or message.name == 'counter-trade') \
                    and not self.request_cache.get(u'proposed-trade', message.payload.proposal_id):
                yield DropMessage(message, "Unexpected %s message with proposal id %d" %
                                  (message.name, message.payload.proposal_id))
                continue

            yield message

    def get_outstanding_proposals(self, order_id, partner_order_id):
        return [(proposal_id, cache) for proposal_id, cache in self.request_cache._identifiers.iteritems()
                if isinstance(cache, ProposedTradeRequestCache)
                and cache.proposed_trade.order_id == order_id
                and cache.proposed_trade.recipient_order_id == partner_order_id]

    def on_proposed_trade(self, messages):
        for message in messages:
            proposed_trade = ProposedTrade.from_network(message.payload)

            self._logger.debug("Proposed trade received with id: %s", str(proposed_trade.message_id))

            # Update the known IP address of the sender of this proposed trade
            self.update_ip(proposed_trade.message_id.trader_id,
                           (message.payload.address.ip, message.payload.address.port))

            order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

            # We can have a race condition where an ask/bid is created simultaneously on two different nodes.
            # In this case, both nodes first send a proposed trade and then receive a proposed trade from the other
            # node. To counter this, we have the following check.
            outstanding_proposals = self.get_outstanding_proposals(order.order_id, proposed_trade.order_id)
            if not order.is_ask() and outstanding_proposals:
                # Discard current outstanding proposed trade and continue
                self._logger.info("Discarding current outstanding proposals for order %s", proposed_trade.order_id)
                for proposal_id, _ in outstanding_proposals:
                    request = self.request_cache.pop(u"proposed-trade", int(proposal_id.split(':')[1]))
                    order.release_quantity_for_tick(proposed_trade.order_id, request.proposed_trade.quantity)

            if order.is_valid() and order.available_quantity > Quantity(0, order.available_quantity.wallet_id) \
                    and proposed_trade.has_acceptable_price(order.is_ask(), order.price):
                self._logger.debug("Proposed trade received with id: %s for order with id: %s",
                                   str(proposed_trade.message_id), str(order.order_id))

                if order.available_quantity >= proposed_trade.quantity:  # Enough quantity left
                    order.reserve_quantity_for_tick(proposed_trade.order_id, proposed_trade.quantity)
                    self.order_manager.order_repository.update(order)
                    self.start_transaction(proposed_trade)
                else:  # Not all quantity can be traded
                    counter_quantity = order.available_quantity
                    order.reserve_quantity_for_tick(proposed_trade.order_id, counter_quantity)
                    self.order_manager.order_repository.update(order)

                    counter_trade = Trade.counter(self.order_book.message_repository.next_identity(),
                                                  counter_quantity, Timestamp.now(), proposed_trade)
                    self._logger.debug("Counter trade made with quantity: %s for proposed trade with id: %s",
                                       str(counter_trade.quantity), str(proposed_trade.message_id))
                    self.send_counter_trade(counter_trade)
            else:  # Order invalid send cancel
                declined_trade = Trade.decline(self.order_book.message_repository.next_identity(),
                                               Timestamp.now(), proposed_trade)
                self._logger.debug("Declined trade made with id: %s for proposed trade with id: %s "
                                   "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s)",
                                   str(declined_trade.message_id), str(proposed_trade.message_id),
                                   order.is_valid(), order.available_quantity, order.reserved_quantity,
                                   order.traded_quantity)
                self.send_declined_trade(declined_trade)

                # We declined the proposed trade, however, we might want to save it since the proposed trade might still
                # be relevant if one of our outstanding proposal trades is declined.
                for cache in self.request_cache._identifiers.itervalues():
                    if isinstance(cache, ProposedTradeRequestCache) and order.order_id == cache.proposed_trade.order_id:
                        # We have an outstanding propose trade for this order, save the incoming proposed trade
                        tup = (order.order_id, proposed_trade)
                        removal_task = deferLater(reactor, 10, self.pending_proposed_trades.remove, tup)\
                            .addErrback(lambda _: None)
                        self.register_task("pending_propose_%s_%s_timeout" %
                                           (proposed_trade.order_id, proposed_trade.recipient_order_id), removal_task)
                        self.pending_proposed_trades.append(tup)

    # Declined trade
    def send_declined_trade(self, declined_trade):
        assert isinstance(declined_trade, DeclinedTrade), type(declined_trade)
        destination, payload = declined_trade.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"declined-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_declined_trade(self, messages):
        for message in messages:
            declined_trade = DeclinedTrade.from_network(message.payload)

            request = self.request_cache.pop(u"proposed-trade", declined_trade.proposal_id)

            order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)
            order.release_quantity_for_tick(declined_trade.order_id, request.proposed_trade.quantity)
            self.order_manager.order_repository.update(order)

            # Just remove the tick with the order id of the other party and try to find a new match
            self._logger.debug("Received declined trade (proposal id: %d), trying to find a new match for this order",
                               declined_trade.proposal_id)
            self.order_book.remove_tick(declined_trade.order_id)

            # Do we have any pending propose trades for this order?
            pending_proposals = [proposed_trade for order_id, proposed_trade in self.pending_proposed_trades
                                 if order_id == order.order_id]
            if pending_proposals:
                self.pending_proposed_trades.remove((order.order_id, pending_proposals[0]))
                order.reserve_quantity_for_tick(pending_proposals[0].order_id, pending_proposals[0].quantity)
                proposed_trade = Trade.propose(self.order_book.message_repository.next_identity(),
                                               pending_proposals[0].recipient_order_id,
                                               pending_proposals[0].order_id,
                                               pending_proposals[0].price, pending_proposals[0].quantity,
                                               Timestamp.now())
                self.send_proposed_trade(proposed_trade)
            else:
                self.match(order)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        assert isinstance(counter_trade, CounterTrade), type(counter_trade)
        destination, payload = counter_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, counter_trade))

        # Add the local address to the payload
        payload += self.get_dispersy_address()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"counter-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_counter_trade(self, messages):
        for message in messages:
            counter_trade = CounterTrade.from_network(message.payload)

            request = self.request_cache.pop(u"proposed-trade", counter_trade.proposal_id)

            order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)
            if order.is_valid() and counter_trade.has_acceptable_price(order.is_ask(), order.price):  # Accept trade
                order.release_quantity_for_tick(counter_trade.order_id, request.proposed_trade.quantity)
                order.reserve_quantity_for_tick(counter_trade.order_id, counter_trade.quantity)
                self.order_manager.order_repository.update(order)
                self.start_transaction(counter_trade)
            else:
                declined_trade = Trade.decline(self.order_book.message_repository.next_identity(),
                                               Timestamp.now(), counter_trade)
                self._logger.debug("Declined trade made with id: %s for counter trade with id: %s",
                                   str(declined_trade.message_id), str(counter_trade.message_id))
                self.send_declined_trade(declined_trade)

    # Transactions
    def start_transaction(self, proposed_trade):
        order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

        if order:
            transaction = self.transaction_manager.create_from_proposed_trade(proposed_trade)
            start_transaction = StartTransaction(self.order_book.message_repository.next_identity(),
                                                 transaction.transaction_id, order.order_id,
                                                 proposed_trade.order_id, proposed_trade.proposal_id,
                                                 proposed_trade.price, proposed_trade.quantity, Timestamp.now())
            self.send_start_transaction(transaction, start_transaction)

    # Start transaction
    def send_start_transaction(self, transaction, start_transaction):
        assert isinstance(start_transaction, StartTransaction), type(start_transaction)
        payload = start_transaction.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)

        meta = self.get_meta_message(u"start-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def check_transaction_message(self, messages):
        for message in messages:
            transaction_id = TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number)

            allowed, _ = self._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            if message.name == 'start-transaction' and \
                    not self.request_cache.get(u'proposed-trade', message.payload.proposal_id):
                yield DropMessage(message, "Unexpected %s message with proposal id %d" %
                                  (message.name, message.payload.proposal_id))
                continue

            if message.name != 'start-transaction' and not self.transaction_manager.find_by_id(transaction_id):
                yield DropMessage(message, "Unknown transaction in %s message" % message.name)
                continue

            transaction = self.transaction_manager.find_by_id(transaction_id)
            if message.name not in ['start-transaction', 'end-transaction'] and transaction.is_payment_complete():
                yield DropMessage(message, "Transaction in %s message is already complete" % message.name)
                continue

            yield message

    def on_start_transaction(self, messages):
        for message in messages:
            start_transaction = StartTransaction.from_network(message.payload)

            self.request_cache.pop(u"proposed-trade", start_transaction.proposal_id)

            # The recipient_order_id in the start_transaction message is our own order
            order = self.order_manager.order_repository.find_by_id(start_transaction.recipient_order_id)

            if order:
                transaction = self.transaction_manager.create_from_start_transaction(start_transaction)
                incoming_address, outgoing_address = self.get_order_addresses(order)
                self.send_wallet_info(transaction, incoming_address, outgoing_address)

    def send_wallet_info(self, transaction, incoming_address, outgoing_address):
        assert isinstance(transaction, Transaction), type(transaction)

        # Update the transaction with the address information
        transaction.incoming_address = incoming_address
        transaction.outgoing_address = outgoing_address

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)

        self._logger.debug("Sending wallet info to trader %s (incoming address: %s, outgoing address: %s",
                           transaction.partner_order_id.trader_id, incoming_address, outgoing_address)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"wallet-info")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                incoming_address,
                outgoing_address,
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)
        transaction.sent_wallet_info = True
        self.transaction_manager.transaction_repository.update(transaction)

    def on_wallet_info(self, messages):
        for message in messages:
            transaction = self.transaction_manager.find_by_id(
                TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number))
            transaction.received_wallet_info = True

            transaction.partner_outgoing_address = message.payload.outgoing_address
            transaction.partner_incoming_address = message.payload.incoming_address

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
        # requires the wallet to know about transactions, the market community and Dispersy.
        if isinstance(wallet, TrustchainWallet):
            candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)
            member = self.dispersy.get_member(public_key=b64decode(str(transaction.partner_incoming_address)))
            candidate.associate(member)
            transfer_deferred = wallet.transfer(float(transfer_amount), candidate)
        else:
            transfer_deferred = wallet.transfer(float(transfer_amount), str(transaction.partner_incoming_address))

        def on_payment_error(failure):
            """
            When a payment fails, log the error and still send a payment message to inform the other party that the
            payment has failed.
            """
            self._logger.error("Payment of %f to %s failed: %s", transfer_amount,
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

        message_id = self.order_book.message_repository.next_identity()
        payment_message = self.transaction_manager.create_payment_message(
            message_id, payment_id, transaction, payment, success)
        self._logger.debug("Sending payment message with price %s and quantity %s (success? %s)",
                           payment_message.transferee_price, payment_message.transferee_quantity, success)

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_SENT, NTFY_UPDATE, None,
                                                 payment_message.to_dictionary())

        payload = payment_message.to_network()

        candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)
        meta = self.get_meta_message(u"payment")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_payment_message(self, messages):
        for message in messages:
            payment_message = Payment.from_network(message.payload)
            self._logger.debug("Received payment message with price %s and quantity %s",
                               payment_message.transferee_price, payment_message.transferee_quantity)
            transaction = self.transaction_manager.find_by_id(payment_message.transaction_id)
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)

            if not payment_message.success:
                transaction.add_payment(payment_message)
                self.transaction_manager.transaction_repository.update(transaction)
                self.abort_transaction(transaction)

                if self.tribler_session:
                    self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE,
                                                         None, payment_message.to_dictionary())

                continue

            if order.is_ask():
                wallet_id = payment_message.transferee_price.wallet_id
            else:
                wallet_id = payment_message.transferee_quantity.wallet_id

            wallet = self.wallets[wallet_id]
            transaction_deferred = wallet.monitor_transaction(str(payment_message.payment_id))
            transaction_deferred.addCallback(
                lambda _, pm=payment_message, tx=transaction: self.received_payment(pm, tx))

    def received_payment(self, payment, transaction):
        self._logger.debug("Received payment with id %s (price: %s, quantity: %s)",
                           payment.payment_id, payment.transferee_price, payment.transferee_quantity)
        transaction.add_payment(payment)
        self.transaction_manager.transaction_repository.update(transaction)

        if float(payment.transferee_quantity) > 0:  # Release some of the reserved quantity
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)
            order.add_trade(transaction.partner_order_id, payment.transferee_quantity)
            self.order_manager.order_repository.update(order)

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE, None,
                                                 payment.to_dictionary())

        if not transaction.is_payment_complete():
            self.send_payment(transaction)
        else:
            end_transaction_timestamp = Timestamp.now()
            self.send_end_transaction(transaction, end_transaction_timestamp)
            self.update_ticks(transaction, end_transaction_timestamp)

    # End transaction
    def send_end_transaction(self, transaction, timestamp):
        # Lookup the remote address of the peer with the pubkey
        self._logger.debug("Sending end transaction (quantity: %s)", transaction.total_quantity)
        candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"end-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                timestamp,
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)
        self.notify_transaction_complete(transaction)

        if self.tradechain_community:
            member = self.dispersy.get_member(mid=str(transaction.partner_order_id.trader_id).decode('hex'))
            candidate.associate(member)
            self.tradechain_community.add_discovered_candidate(candidate)

            quantity = transaction.total_quantity
            price = transaction.price
            transaction = {"txid": str(transaction.transaction_id),
                           "asset1_type": price.wallet_id, "asset1_amount": float(price),
                           "asset2_type": quantity.wallet_id, "asset2_amount": float(quantity)}
            self.tradechain_community.sign_block(candidate, candidate.get_member().public_key, transaction)

    def update_ticks(self, transaction, end_transaction_timestamp):
        """
        Update your tick in the order book according to a specific transaction.
        Afterwards, send the updated tick.
        """
        self._logger.debug("Updating own tick and sending it to other traders")
        self.order_book.trade_tick(transaction.order_id, transaction.partner_order_id,
                                   transaction.transferred_quantity, end_transaction_timestamp)
        if self.order_book.tick_exists(transaction.order_id):
            tick = self.order_book.get_tick(transaction.order_id).tick
            tick.update_timestamp()
            tick.sign(self.my_member)  # Tick content have changed, update the signature
            self.send_tick(tick)

            if tick.quantity == Quantity(0, tick.quantity.wallet_id):
                self.order_book.remove_tick(transaction.order_id)

        # Remove the tick of the counterparty if it's fulfilled
        if self.order_book.tick_exists(transaction.partner_order_id):
            tick = self.order_book.get_tick(transaction.partner_order_id)
            if tick.quantity == Quantity(0, tick.quantity.wallet_id):
                self.order_book.remove_tick(transaction.order_id)

    def abort_transaction(self, transaction):
        """
        Abort a specific transaction by releasing all reserved quantity for this order.
        """
        self._logger.error("Aborting transaction %s", transaction.transaction_id)
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)
        order.release_quantity_for_tick(transaction.partner_order_id,
                                        transaction.total_quantity - transaction.transferred_quantity)
        self.order_manager.order_repository.update(order)
        self.update_ticks(transaction, Timestamp.now())

    def on_end_transaction(self, messages):
        for message in messages:
            self._logger.debug("Finishing transaction %s", message.payload.transaction_number)
            transaction_id = TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number)
            transaction = self.transaction_manager.find_by_id(transaction_id)
            self.update_ticks(transaction, message.payload.timestamp)
            self.notify_transaction_complete(self.transaction_manager.find_by_id(transaction_id))

    def notify_transaction_complete(self, transaction):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None,
                                                 transaction.to_dictionary())

    def compute_reputation(self):
        """
        Compute the reputation of peers in the community
        """
        if self.tradechain_community:
            rep_manager = PagerankReputationManager(self.tradechain_community.persistence.get_all_blocks())
            self.reputation_dict = rep_manager.compute(self.my_member.public_key)
