import random
import time
from base64 import b64decode

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT, NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy
from Tribler.community.market.core import DeclineMatchReason, DeclinedTradeReason
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
    PaymentPayload, CancelOrderPayload, MatchPayload, AcceptMatchPayload, DeclineMatchPayload, \
    TransactionCompletedPayload, TransactionCompletedBCPayload
from Tribler.community.market.reputation.pagerank_manager import PagerankReputationManager
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
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
            self.community.send_decline_match_message(self.match_id, match_message.payload.matchmaker_trader_id,
                                                      DeclineMatchReason.OTHER)


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
        self.relayed_completed_transaction = {}
        self.order_manager = None
        self.order_book = None
        self.market_database = None
        self.matching_engine = None
        self.incoming_match_messages = {}  # Map of TraderId -> Message (we save all incoming matches)
        self.tribler_session = None
        self.tradechain_community = None
        self.wallets = None
        self.transaction_manager = None
        self.reputation_dict = {}
        self.use_local_address = False
        self.matching_enabled = True
        self.is_matchmaker = True
        self.message_repository = None
        self.use_incremental_payments = True
        self.validate_tick_signatures = True
        self.matchmakers = set()

    def initialize(self, tribler_session=None, tradechain_community=None, wallets=None,
                   use_database=True, is_matchmaker=True):
        super(MarketCommunity, self).initialize()

        self.mid = self.my_member.mid.encode('hex')
        self.is_matchmaker = is_matchmaker
        self.message_repository = MemoryMessageRepository(self.mid)
        self.market_database = MarketDB(self.dispersy.working_directory)

        if self.is_matchmaker:
            self.enable_matchmaker()

        for trader in self.market_database.get_traders():
            self.update_ip(TraderId(str(trader[0])), (str(trader[1]), trader[2]))

        if use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
            transaction_repository = DatabaseTransactionRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)
            transaction_repository = MemoryTransactionRepository(self.mid)

        self.order_manager = OrderManager(order_repository)
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
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_tick_message,
                    self.on_tick),
            Message(self, u"bid",
                    NoAuthentication(),
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
            Message(self, u"match",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    MatchPayload(),
                    self.check_message,
                    self.on_match_message),
            Message(self, u"accept-match",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    AcceptMatchPayload(),
                    self.check_message,
                    self.on_accept_match_message),
            Message(self, u"decline-match",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    DeclineMatchPayload(),
                    self.check_message,
                    self.on_decline_match_message),
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
                    self.on_end_transaction),
            Message(self, u"transaction-completed",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TransactionCompletedPayload(),
                    self.check_transaction_message,
                    self.on_transaction_completed_message),
            Message(self, u"transaction-completed-bc",
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    TransactionCompletedBCPayload(),
                    self.check_transaction_message,
                    self.on_transaction_completed_bc_message)
        ]

    def _initialize_meta_messages(self):
        super(MarketCommunity, self)._initialize_meta_messages()

        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution,
                      ori.distribution, ori.destination, MarketIntroPayload(), ori.check_callback, ori.handle_callback)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), MarketConversion(self)]

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(5.0, now=False)

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

    def dispersy_get_introduce_candidate(self, exclude_candidate=None):
        """
        Return a matchmaker with higher priority as introduce candidate.
        """
        if len(self.matchmakers) == 0:
            return super(MarketCommunity, self).dispersy_get_introduce_candidate(exclude_candidate)

        matchmaker = random.sample(self.matchmakers, 1)[0]
        self._logger.debug("Introducing other node to matchmaker %s:%d", *matchmaker)
        return self.get_candidate(matchmaker)

    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        orders_bloom_filter = None
        if self.is_matchmaker:
            order_ids = [str(order_id) for order_id in self.order_book.get_order_ids()]
            if len(order_ids) == 0:
                orders_bloom_filter = None
            else:
                orders_bloom_filter = BloomFilter(0.005, len(order_ids), prefix=' ')
                orders_bloom_filter.add_keys(order_ids)

        cache = self._request_cache.add(IntroductionRequestCache(self, destination))
        payload = (destination.sock_addr, self._dispersy.lan_address, self._dispersy.wan_address, True,
                   self._dispersy.connection_type, None, cache.number, self.is_matchmaker, orders_bloom_filter)

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
            if not self.is_matchmaker:
                continue

            if message.payload.is_matchmaker:
                self.matchmakers.add(message.candidate.sock_addr)

            orders_bloom_filter = message.payload.orders_bloom_filter
            for order_id in self.order_book.get_order_ids():
                if (not orders_bloom_filter or str(order_id) not in orders_bloom_filter) and \
                        message.payload.is_matchmaker:
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
        if self.is_matchmaker:
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

    def match(self, tick):
        """
        Try to find a match for a specific tick and send proposed trade messages if there is a match
        :param tick: The tick to find matches for
        """
        if not self.matching_enabled:
            return

        order_tick_entry = self.order_book.get_tick(tick.order_id)
        if tick.quantity - order_tick_entry.reserved_for_matching == Quantity(0, tick.quantity.wallet_id):
            self._logger.debug("Tick %s does not have any quantity to match!", tick.order_id)
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

        # Create the tick
        tick = Tick.from_order(order, self.message_repository.next_identity())
        tick.sign(self.my_member)
        assert isinstance(tick, Ask), type(tick)

        if self.is_matchmaker:
            # Search for matches
            self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
            self.match(tick)

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
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_tick(self, messages):
        for message in messages:
            tick = Ask.from_network(message.payload) if message.name == u"ask" else Bid.from_network(message.payload)

            self._logger.debug("%s received from trader %s (price: %s, quantity: %s)", type(tick),
                               str(tick.order_id.trader_id), tick.price, tick.quantity)

            # Update the mid register with the current address
            self.update_ip(tick.order_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if self.is_matchmaker:
                insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid
                timeout_method = self.on_ask_timeout if isinstance(tick, Ask) else self.on_bid_timeout

                if not self.order_book.tick_exists(tick.order_id) and \
                                tick.quantity > Quantity(0, tick.quantity.wallet_id):
                    self._logger.debug("Inserting %s from %s (price: %s, quantity: %s)",
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

            # Relay the tick regardless whether we are a matchmaker or not
            if tick.order_id not in self.relayed_ticks or self.relayed_ticks[tick.order_id] < tick.timestamp:
                self.relayed_ticks[tick.order_id] = tick.timestamp
                self.relay_message(message)

    def relay_message(self, message):
        # Check if message needs to be send on
        ttl = message.payload.ttl

        ttl.make_hop()  # Complete the hop from the previous node
        message.regenerate_packet()

        if ttl.is_alive():  # The ttl is still alive and can be forwarded
            self.dispersy.store_update_forward([message], True, False, True)

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

        # Create the tick
        tick = Tick.from_order(order, self.message_repository.next_identity())
        tick.sign(self.my_member)
        assert isinstance(tick, Bid), type(tick)

        if self.is_matchmaker:
            # Search for matches
            self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
            self.match(tick)

        self.send_tick(tick)

        self._logger.debug("Bid created with price %s and quantity %s", price, quantity)

        return order

    def send_cancel_order(self, order):
        """
        Send a cancel-order message to the community
        """
        assert isinstance(order, Order), type(order)

        message_id = self.message_repository.next_identity()

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
            if self.is_matchmaker and self.order_book.tick_exists(order_id):
                self.order_book.remove_tick(order_id)

            if str(order_id) not in self.relayed_cancels:
                self.relayed_cancels.append(str(order_id))

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node
                message.regenerate_packet()

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, False, True)

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
        if str(tick.message_id.trader_id) == self.mid:
            tick_address = self.get_dispersy_address()
        else:
            tick_address = self.lookup_ip(tick.message_id.trader_id)

        payload += (Ttl(1),) + tick_address + (isinstance(tick, Ask),)

        meta = self.get_meta_message(u"offer-sync")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(target_candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

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

        payload = tick.to_network()

        # Add ttl and the local wan address of the trader that created the tick
        if str(tick.message_id.trader_id) == self.mid:
            tick_address = self.get_dispersy_address()
        else:
            tick_address = self.lookup_ip(tick.message_id.trader_id)

        payload += (Ttl.default(),) + tick_address

        # Add recipient order number, matched quantity, trader ID of the matched person, our own trader ID and match ID
        my_id = TraderId(self.mid)
        payload += (recipient_order_id.order_number, matched_quantity, tick.message_id.trader_id, my_id, match_id)

        # Lookup the remote address of the peer with the pubkey
        if str(recipient_order_id.trader_id) == self.mid:
            address = self.get_dispersy_address()
        else:
            address = self.lookup_ip(recipient_order_id.trader_id)
        candidate = Candidate(address, False)

        self._logger.debug("Sending match message with order id %s and tick order id %s to trader "
                           "%s (ip: %s, port: %s)", str(recipient_order_id),
                           str(tick.order_id), recipient_order_id.trader_id, *address)

        meta = self.get_meta_message(u"match")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

    def on_match_message(self, messages):
        for message in messages:
            # We got a match, check whether we can respond to this match
            self.update_ip(message.payload.matchmaker_trader_id, message.candidate.sock_addr)
            self.update_ip(message.payload.trader_id, (message.payload.address.ip, message.payload.address.port))
            self.matchmakers.add(message.candidate.sock_addr)

            # Immediately send an introduction request to this matchmaker so it's verified
            walk_candidate = self.create_or_update_walkcandidate(message.candidate.sock_addr, ('0.0.0.0', 0),
                                                                 message.candidate.sock_addr, False, u'unknown')
            self.create_introduction_request(walk_candidate, self.dispersy_enable_bloom_filter_sync)

            order_id = OrderId(TraderId(self.mid), message.payload.recipient_order_number)
            other_order_id = OrderId(message.payload.trader_id, message.payload.order_number)
            order = self.order_manager.order_repository.find_by_id(order_id)

            # Store the message for later
            self.incoming_match_messages[message.payload.match_id] = message

            if order.status != "open" or order.available_quantity == Quantity(0, order.available_quantity.wallet_id):
                # Send a declined trade back
                self.send_decline_match_message(message.payload.match_id,
                                                message.payload.matchmaker_trader_id,
                                                DeclineMatchReason.ORDER_COMPLETED)
                continue

            propose_quantity = Quantity(min(float(order.available_quantity), float(message.payload.match_quantity)),
                                        order.available_quantity.wallet_id)

            # Reserve the quantity
            order.reserve_quantity_for_tick(other_order_id, propose_quantity)
            self.order_manager.order_repository.update(order)

            propose_trade = Trade.propose(
                self.message_repository.next_identity(),
                order.order_id,
                other_order_id,
                message.payload.price,
                propose_quantity,
                Timestamp.now()
            )
            self.send_proposed_trade(propose_trade, message.payload.match_id)

    def check_match_message(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            if not self.is_matchmaker:
                yield DropMessage(message, "Node is not a matchmaker")
                continue

            if message.payload.match_id not in self.matching_engine.matches:
                yield DropMessage(message, "Matching id %s not found" % message.payload.match_id)

            yield message

    def send_accept_match_message(self, match_id, matchmaker_trader_id, quantity):
        address = self.lookup_ip(matchmaker_trader_id)
        candidate = Candidate(address, False)

        self._logger.debug("Sending accept match message with match id %s to trader "
                           "%s (ip: %s, port: %s)", str(match_id), str(matchmaker_trader_id), *address)

        msg_id = self.message_repository.next_identity()
        payload = (msg_id.trader_id, msg_id.message_number, Timestamp.now(), match_id, quantity)

        meta = self.get_meta_message(u"accept-match")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

    def on_accept_match_message(self, messages):
        for message in messages:
            order_id, matched_order_id, reserved_quantity = self.matching_engine.matches[message.payload.match_id]
            self._logger.debug("Received accept-match message (%s vs %s), modifying quantities if necessary",
                               order_id, matched_order_id)
            tick_entry = self.order_book.get_tick(order_id)
            matched_tick_entry = self.order_book.get_tick(matched_order_id)

            # The ticks could already have been removed
            if tick_entry:
                tick_entry.release_for_matching(reserved_quantity)
                tick_entry.reserve_for_matching(message.payload.quantity)

            if matched_tick_entry:
                matched_tick_entry.release_for_matching(reserved_quantity)
                matched_tick_entry.reserve_for_matching(message.payload.quantity)

            del self.matching_engine.matches[message.payload.match_id]
            self.matching_engine.matching_strategy.used_match_ids.remove(message.payload.match_id)

    def send_decline_match_message(self, match_id, matchmaker_trader_id, decline_reason):
        del self.incoming_match_messages[match_id]
        address = self.lookup_ip(matchmaker_trader_id)
        candidate = Candidate(address, False)

        self._logger.debug("Sending decline match message with match id %s to trader "
                           "%s (ip: %s, port: %s)", str(match_id), str(matchmaker_trader_id), *address)

        msg_id = self.message_repository.next_identity()
        payload = (msg_id.trader_id, msg_id.message_number, Timestamp.now(), match_id, decline_reason)

        meta = self.get_meta_message(u"decline-match")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

    def on_decline_match_message(self, messages):
        for message in messages:
            order_id, matched_order_id, quantity = self.matching_engine.matches[message.payload.match_id]
            self._logger.debug("Received decline-match message for tick %s matched with %s", order_id, matched_order_id)
            tick_entry = self.order_book.get_tick(order_id)
            matched_tick_entry = self.order_book.get_tick(matched_order_id)
            tick_entry.release_for_matching(quantity)

            if matched_tick_entry:
                matched_tick_entry.release_for_matching(quantity)
                tick_entry.block_for_matching(matched_tick_entry.order_id)
                matched_tick_entry.block_for_matching(tick_entry.order_id)

            del self.matching_engine.matches[message.payload.match_id]
            self.matching_engine.matching_strategy.used_match_ids.remove(message.payload.match_id)

            if matched_tick_entry and message.payload.decline_reason == DeclineMatchReason.OTHER_ORDER_COMPLETED:
                self.order_book.remove_tick(matched_tick_entry.order_id)
                self.order_book.completed_orders.append(matched_tick_entry.order_id)

            if message.payload.decline_reason == DeclineMatchReason.ORDER_COMPLETED:
                self.order_book.remove_tick(tick_entry.order_id)
                self.order_book.completed_orders.append(tick_entry.order_id)
            else:
                # Search for a new match
                self.match(tick_entry.tick)

    def on_offer_sync(self, messages):
        for message in messages:
            if not self.is_matchmaker:
                continue

            if message.payload.is_ask:
                tick = Ask.from_network(message.payload)
                insert_method = self.order_book.insert_ask
                timeout_method = self.on_ask_timeout
            else:
                tick = Bid.from_network(message.payload)
                insert_method = self.order_book.insert_bid
                timeout_method = self.on_bid_timeout

            self.update_ip(tick.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not self.order_book.tick_exists(tick.order_id):
                insert_method(tick).addCallback(timeout_method)

                if self.tribler_session:
                    notify_subject = NTFY_MARKET_ON_ASK if message.payload.is_ask else NTFY_MARKET_ON_BID
                    self.tribler_session.notifier.notify(notify_subject, NTFY_UPDATE, None, tick.to_dictionary())

            if self.order_book.tick_exists(tick.order_id):
                self.match(tick)

    def cancel_order(self, order_id):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and order.status == "open":
            self.order_manager.cancel_order(order_id)
            self.send_cancel_order(order)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade, match_id):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        assert isinstance(match_id, str), type(match_id)
        destination, payload = proposed_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, proposed_trade, match_id))

        # Add the local address to the payload
        payload += self.get_dispersy_address()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        self._logger.debug("Sending proposed trade with own order id %s and other order id %s to trader "
                           "%s, quantity: %s (ip: %s, port: %s)", str(proposed_trade.order_id),
                           str(proposed_trade.recipient_order_id), destination, proposed_trade.quantity,
                           *self.lookup_ip(destination))

        meta = self.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        return self.dispersy.store_update_forward([message], True, False, True)

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
                self._logger.debug("Declined trade made with id: %s for proposed trade with id: %s "
                                   "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s)",
                                   str(declined_trade.message_id), str(proposed_trade.message_id),
                                   order.is_valid(), order.available_quantity, order.reserved_quantity,
                                   order.traded_quantity)
                self.send_declined_trade(declined_trade)
            else:
                self._logger.debug("Proposed trade received with id: %s for order with id: %s",
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
                    self._logger.debug("Counter trade made with quantity: %s for proposed trade with id: %s",
                                       str(counter_trade.quantity), str(proposed_trade.message_id))
                    self.send_counter_trade(counter_trade)

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

            # Let the matchmaker know that we don't have a match
            match_message = self.incoming_match_messages[request.match_id]
            match_decline_reason = DeclineMatchReason.OTHER
            if declined_trade.decline_reason == DeclinedTradeReason.ORDER_COMPLETED:
                match_decline_reason = DeclineMatchReason.OTHER_ORDER_COMPLETED

            self.send_decline_match_message(request.match_id, match_message.payload.matchmaker_trader_id,
                                            match_decline_reason)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        assert isinstance(counter_trade, CounterTrade), type(counter_trade)
        destination, payload = counter_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, counter_trade, ''))

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
                self._logger.debug("Declined trade made with id: %s for counter trade with id: %s",
                                   str(declined_trade.message_id), str(counter_trade.message_id))
                self.send_declined_trade(declined_trade)
            else:
                order.release_quantity_for_tick(counter_trade.order_id, request.proposed_trade.quantity)
                order.reserve_quantity_for_tick(counter_trade.order_id, counter_trade.quantity)
                self.order_manager.order_repository.update(order)
                self.start_transaction(counter_trade, request.match_id)

                # Let the matchmaker know that we have a match
                match_message = self.incoming_match_messages[request.match_id]
                self.send_accept_match_message(request.match_id, match_message.payload.matchmaker_trader_id,
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

            if message.name != 'transaction-completed-bc' and not self._timeline.check(message)[0]:
                yield DelayMessageByProof(message)
                continue

            if message.name == 'start-transaction' and \
                    not self.request_cache.get(u'proposed-trade', message.payload.proposal_id):
                yield DropMessage(message, "Unexpected %s message with proposal id %d" %
                                  (message.name, message.payload.proposal_id))
                continue

            if message.name != 'start-transaction' and message.name != 'transaction-completed' \
                    and message.name != 'transaction-completed-bc' \
                    and not self.transaction_manager.find_by_id(transaction_id):
                yield DropMessage(message, "Unknown transaction in %s message" % message.name)
                continue

            transaction = self.transaction_manager.find_by_id(transaction_id)
            if message.name not in ['start-transaction', 'end-transaction', 'transaction-completed',
                                    'transaction-completed-bc'] and transaction.is_payment_complete():
                yield DropMessage(message, "Transaction in %s message is already complete" % message.name)
                continue

            yield message

    def on_start_transaction(self, messages):
        for message in messages:
            start_transaction = StartTransaction.from_network(message.payload)

            request = self.request_cache.pop(u"proposed-trade", start_transaction.proposal_id)

            # The recipient_order_id in the start_transaction message is our own order
            order = self.order_manager.order_repository.find_by_id(start_transaction.recipient_order_id)

            if order:
                # Let the matchmaker know that we have a match
                match_message = self.incoming_match_messages[request.match_id]
                self.send_accept_match_message(request.match_id, match_message.payload.matchmaker_trader_id,
                                               start_transaction.quantity)

                transaction = self.transaction_manager.create_from_start_transaction(start_transaction,
                                                                                     request.match_id)
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

        message_id = self.message_repository.next_identity()

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

        message_id = self.message_repository.next_identity()
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
            self.send_transaction_completed(transaction)

    # End transaction
    def send_end_transaction(self, transaction, timestamp):
        # Lookup the remote address of the peer with the pubkey
        self._logger.debug("Sending end transaction (quantity: %s)", transaction.total_quantity)
        candidate = Candidate(self.lookup_ip(transaction.partner_order_id.trader_id), False)

        message_id = self.message_repository.next_identity()

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

    def abort_transaction(self, transaction):
        """
        Abort a specific transaction by releasing all reserved quantity for this order.
        """
        self._logger.error("Aborting transaction %s", transaction.transaction_id)
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)
        order.release_quantity_for_tick(transaction.partner_order_id,
                                        transaction.total_quantity - transaction.transferred_quantity)
        self.order_manager.order_repository.update(order)
        self.send_transaction_completed(transaction)

    def on_end_transaction(self, messages):
        for message in messages:
            self._logger.debug("Finishing transaction %s", message.payload.transaction_number)
            transaction_id = TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number)
            transaction = self.transaction_manager.find_by_id(transaction_id)
            self.notify_transaction_complete(self.transaction_manager.find_by_id(transaction_id))
            self.send_transaction_completed(transaction)

    def notify_transaction_complete(self, transaction):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None,
                                                 transaction.to_dictionary())

    def send_transaction_completed(self, transaction):
        if not transaction.match_id or transaction.match_id not in self.incoming_match_messages:
            # We did not receive this match from a matchmaker. Still, if we are a matchmaker, we can update our
            # local orderbook with the new knowledge of this transaction.
            if self.is_matchmaker:
                self.order_book.trade_tick(transaction.order_id, transaction.partner_order_id,
                                           transaction.transferred_quantity, unreserve=False)

            return

        self._logger.debug("Sending transaction completed (match id: %s)", transaction.match_id)

        # Lookup the remote address of the peer with the pubkey
        match_message = self.incoming_match_messages[transaction.match_id]
        del self.incoming_match_messages[transaction.match_id]
        candidate = Candidate(self.lookup_ip(match_message.payload.matchmaker_trader_id), False)

        message_id = self.message_repository.next_identity()

        meta = self.get_meta_message(u"transaction-completed")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                transaction.order_id.trader_id,
                transaction.order_id.order_number,
                transaction.partner_order_id.trader_id,
                transaction.partner_order_id.order_number,
                transaction.match_id,
                transaction.transferred_quantity,
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_transaction_completed_message(self, messages):
        for message in messages:
            self._logger.debug("Received transaction-completed message")
            if not self.is_matchmaker:
                continue

            # Update ticks in order book, release the reserved quantity and find a new match
            order_id = OrderId(message.payload.trader_id, message.payload.order_number)
            recipient_order_id = OrderId(message.payload.recipient_trader_id, message.payload.recipient_order_number)
            self.order_book.trade_tick(order_id, recipient_order_id, message.payload.quantity)

            self.send_transaction_completed_bc(message)

            tick_entry_sender = self.order_book.get_tick(order_id)
            if tick_entry_sender:
                self.match(tick_entry_sender.tick)

    def send_transaction_completed_bc(self, completed_message):
        self._logger.debug("Sending transaction completed bc (match id: %s)", completed_message.payload.match_id)

        message_id = self.message_repository.next_identity()

        meta = self.get_meta_message(u"transaction-completed-bc")
        message = meta.impl(
            distribution=(self.claim_global_time(),),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                completed_message.payload.transaction_trader_id,
                completed_message.payload.transaction_number,
                completed_message.payload.order_trader_id,
                completed_message.payload.order_number,
                completed_message.payload.recipient_trader_id,
                completed_message.payload.recipient_order_number,
                completed_message.payload.match_id,
                completed_message.payload.quantity,
                Timestamp.now(),
                Ttl.default()
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_transaction_completed_bc_message(self, messages):
        for message in messages:
            self._logger.debug("Received transaction-completed-bc message")
            if not self.is_matchmaker:
                continue

            # Update ticks in order book, release the reserved quantity
            order_id = OrderId(message.payload.trader_id, message.payload.order_number)
            recipient_order_id = OrderId(message.payload.recipient_trader_id, message.payload.recipient_order_number)
            self.order_book.trade_tick(order_id, recipient_order_id, message.payload.quantity, unreserve=False)

            transaction_id = TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number)
            if transaction_id not in self.relayed_completed_transaction:
                self.relayed_completed_transaction[transaction_id] = True
                self.relay_message(message)

    def compute_reputation(self):
        """
        Compute the reputation of peers in the community
        """
        if self.tradechain_community:
            rep_manager = PagerankReputationManager(self.tradechain_community.persistence.get_all_blocks())
            self.reputation_dict = rep_manager.compute(self.my_member.public_key)
