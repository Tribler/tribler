import random
from base64 import b64decode

from twisted.internet.defer import inlineCallbacks, succeed, Deferred
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT, NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market.conversion import MarketConversion
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
from Tribler.community.market.payload import TradePayload, DeclinedTradePayload,\
    StartTransactionPayload, WalletInfoPayload, PaymentPayload, MatchPayload, AcceptMatchPayload, DeclineMatchPayload, \
    InfoPayload, OrderStatusRequestPayload, OrderStatusResponsePayload
from Tribler.community.market.reputation.pagerank_manager import PagerankReputationManager
from Tribler.community.market.tradechain.block import TradeChainBlock
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.community.trustchain.community import TrustChainCommunity, HALF_BLOCK_BROADCAST, BLOCK_PAIR, \
    BLOCK_PAIR_BROADCAST
from Tribler.community.trustchain.community import TrustChainConversion
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.requestcache import NumberCache, RandomNumberCache
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


class OrderStatusRequestCache(RandomNumberCache):

    def __init__(self, community, request_deferred):
        super(OrderStatusRequestCache, self).__init__(community.request_cache, u"order-status-request")
        self.request_deferred = request_deferred

    def on_timeout(self):
        self._logger.warning("No response in time from remote peer when requesting order status")


class MarketCommunity(TrustChainCommunity):
    """
    Community for general asset trading.
    """
    BLOCK_CLASS = TradeChainBlock
    DB_CLASS = MarketDB
    DB_NAME = 'market'

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
        self.matchmakers = set()
        self.pending_matchmaker_deferreds = []

    def initialize(self, tribler_session=None, tradechain_community=None, wallets=None,
                   use_database=True, is_matchmaker=True):
        super(MarketCommunity, self).initialize()

        self.mid = self.my_member.mid.encode('hex')
        self.is_matchmaker = is_matchmaker
        self.message_repository = MemoryMessageRepository(self.mid)
        self.market_database = self.persistence

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
            Message(self, u"info",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    InfoPayload(),
                    self.check_message,
                    self.on_info),
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
            Message(self, u"order-status-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    OrderStatusRequestPayload(),
                    self.check_message,
                    self.on_order_status_request),
            Message(self, u"order-status-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    OrderStatusResponsePayload(),
                    self.check_message,
                    self.on_order_status_response),
        ]

    def initiate_conversions(self):
        return [DefaultConversion(self), TrustChainConversion(self), MarketConversion(self)]

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(5.0, now=False)

    def should_sign(self, message):
        """
        Check whether we should sign the incoming block.
        """
        tx = message.payload.block.transaction
        if tx["type"] == "tick" or tx["type"] == "cancel_order":
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

    def on_introduction_request(self, messages, extra_payload=None):
        super(MarketCommunity, self).on_introduction_request(messages, extra_payload=extra_payload)

        for message in messages:
            self.send_info(message.candidate)

    def on_introduction_response(self, messages):
        super(MarketCommunity, self).on_introduction_response(messages)

        for message in messages:
            self.send_info(message.candidate)

    def check_message(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                self._logger.debug("Allowing message %s", message)
                yield message
            else:
                self._logger.debug("Delaying message %s", message)
                yield DelayMessageByProof(message)

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

    def match_order_ids(self, order_ids):
        """
        Attempt to match the ticks with the provided order ids
        :param ticks: A list of ticks to match
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
        Process a TradeChain block containing a tick
        :param block: The TradeChain block containing the tick
        """
        tick = Ask.from_block(block) if block.transaction["tick"]["is_ask"] else Bid.from_block(block)
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

    def send_info(self, candidate):
        """
        Send an info message to the target candidate.
        """
        message_id = self.message_repository.next_identity()

        meta = self.get_meta_message(u"info")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(message_id.trader_id, message_id.message_number, Timestamp.now(), self.is_matchmaker)
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_info(self, messages):
        for message in messages:
            if message.payload.is_matchmaker:
                self.add_matchmaker(message.candidate.sock_addr)

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
        tick = Tick.from_order(order)
        assert isinstance(tick, Ask), type(tick)

        if self.is_matchmaker:
            # Search for matches
            self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
            self.match(tick)

        self.create_new_tick_block(tick).addCallback(self.send_block)

        self._logger.debug("Ask created with price %s and quantity %s", price, quantity)

        return order

    def received_half_block(self, messages):
        super(MarketCommunity, self).received_half_block(messages)

        for message in messages:
            block = message.payload.block
            if message.name != HALF_BLOCK_BROADCAST and block.transaction["type"] == "tx_done":
                # If we have signed an incoming tx_done block, notify the matchmaker about this
                transaction_id = TransactionId(TraderId(block.transaction["tx"]["trader_id"]),
                                               TransactionNumber(block.transaction["tx"]["transaction_number"]))
                transaction = self.transaction_manager.find_by_id(transaction_id)
                if transaction and self.market_database.get_linked(block):
                    self.send_transaction_completed(transaction, block)

            if block.transaction["type"] == "tick":
                self.process_tick_block(block)
            elif block.transaction["type"] == "tx_init":
                self.process_tx_init_block(block)
            elif block.transaction["type"] == "tx_done":
                self.process_tx_done_block(block)
            elif block.transaction["type"] == "cancel_order":
                self.process_cancel_order_block(block)

    def received_block_pair(self, messages):
        super(MarketCommunity, self).received_block_pair(messages)

        for message in messages:
            block1 = message.payload.block1
            block2 = message.payload.block2
            if block1.transaction["type"] == "tx_done" and block2.transaction["type"] == "tx_done" and \
                            message.name == BLOCK_PAIR:
                self.on_transaction_completed_message(block1, block2)
            elif block1.transaction["type"] == "tx_done" and block2.transaction["type"] == "tx_done" and \
                            message.name == BLOCK_PAIR_BROADCAST:
                self.on_transaction_completed_bc_message(block1, block2)

    def add_matchmaker(self, matchmaker):
        """
        Add a matchmaker to the set of known matchmakers. Also check whether there are pending deferreds.
        """
        self.matchmakers.add(matchmaker)

        for matchmaker_deferred in self.pending_matchmaker_deferreds:
            matchmaker_deferred.callback(self.get_candidate(random.sample(self.matchmakers, 1)[0], False))
            del matchmaker_deferred

    def get_random_matchmaker(self):
        """
        Get a random matchmaker. If there is no matchmaker available, wait until there's one.
        :return: A Deferred that fires with a matchmaker.
        """
        if len(self.matchmakers) > 0:
            return succeed(self.get_candidate(random.sample(self.matchmakers, 1)[0], False))

        matchmaker_deferred = Deferred()
        self.pending_matchmaker_deferreds.append(matchmaker_deferred)
        return matchmaker_deferred

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
            tx_dict["tick"]['address'], tx_dict["tick"]['port'] = self.get_dispersy_address()
            new_block = self.sign_block(matchmaker, matchmaker.get_member().public_key, tx_dict)

            block_id = "%s.%s" % (new_block.public_key.encode('hex'), new_block.sequence_number)
            return self.wait_for_signature_response(block_id).addCallback(lambda _: new_block)

        return self.get_random_matchmaker().addCallback(create_send_block)

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
            new_block = self.sign_block(matchmaker, matchmaker.get_member().public_key, tx_dict)

            block_id = "%s.%s" % (new_block.public_key.encode('hex'), new_block.sequence_number)
            return self.wait_for_signature_response(block_id).addCallback(lambda _: new_block)

        return self.get_random_matchmaker().addCallback(create_send_block)

    def create_new_tx_init_block(self, candidate, ask_order_dict, bid_order_dict, transaction):
        """
        Create a block on TradeChain defining initiation of a transaction.

        :param: candidate: The candidate to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param transaction: The transaction that will be initiated
        :type candidate: Candidate
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
        new_block = self.sign_block(candidate, candidate.get_member().public_key, tx_dict)

        block_id = "%s.%s" % (new_block.public_key.encode('hex'), new_block.sequence_number)
        return self.wait_for_signature_response(block_id).addCallback(lambda _: new_block)

    def create_new_tx_payment_block(self, candidate, payment):
        """
        Create a block on TradeChain defining payment during a transaction.

        :param: candidate: The candidate to send the block to
        :param transaction: The transaction involving the payment
        :param payment: The payment to record
        :type candidate: Candidate
        :type transaction: Transaction
        :type payment: Payment
        :return: A deferred that fires when the transaction counterparty has signed and returned the block.
        :rtype: Deferred
        """
        tx_dict = {
            "type": "tx_payment",
            "payment": payment.to_dictionary()
        }
        new_block = self.sign_block(candidate, candidate.get_member().public_key, tx_dict)

        block_id = "%s.%s" % (new_block.public_key.encode('hex'), new_block.sequence_number)
        return self.wait_for_signature_response(block_id).addCallback(lambda _: new_block)

    def create_new_tx_done_block(self, candidate, ask_order_dict, bid_order_dict, transaction):
        """
        Create a block on TradeChain defining completion of a transaction.

        :param: candidate: The candidate to send the block to
        :param: ask_order_dict: A dictionary containing the status of the ask order
        :param: bid_order_dict: A dictionary containing the status of the bid order
        :param transaction: The transaction that has been completed
        :type candidate: Candidate
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
        new_block = self.sign_block(candidate, candidate.get_member().public_key, tx_dict)

        block_id = "%s.%s" % (new_block.public_key.encode('hex'), new_block.sequence_number)
        return self.wait_for_signature_response(block_id).addCallback(lambda _: new_block)

    def on_tick(self, tick, address):
        """
        Process an incoming tick.
        :param tick: the received tick to process
        :param address: tuple of (ip_address, port) defining the internet address of the creator of the tick
        """
        self._logger.debug("%s received from trader %s (price: %s, quantity: %s)", type(tick),
                           str(tick.order_id.trader_id), tick.price, tick.quantity)

        # Update the mid register with the current address
        self.update_ip(tick.order_id.trader_id, address)

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
        tick = Tick.from_order(order)
        assert isinstance(tick, Bid), type(tick)

        if self.is_matchmaker:
            # Search for matches
            self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
            self.match(tick)

        self.create_new_tick_block(tick).addCallback(self.send_block)

        self._logger.debug("Bid created with price %s and quantity %s", price, quantity)

        return order

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
            tick_address = self.get_dispersy_address()
        else:
            tick_address = self.lookup_ip(tick.order_id.trader_id)

        payload += tick_address

        # Add recipient order number, matched quantity, trader ID of the matched person, our own trader ID and match ID
        my_id = TraderId(self.mid)
        payload += (recipient_order_id.order_number, matched_quantity, tick.order_id.trader_id, my_id, match_id)

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
            self.add_matchmaker(message.candidate.sock_addr)

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

            del self.matching_engine.matches[message.payload.match_id]
            self.matching_engine.matching_strategy.used_match_ids.remove(message.payload.match_id)

            if matched_tick_entry and message.payload.decline_reason == DeclineMatchReason.OTHER_ORDER_COMPLETED:
                self.order_book.remove_tick(matched_tick_entry.order_id)
                self.order_book.completed_orders.append(matched_tick_entry.order_id)

            if message.payload.decline_reason == DeclineMatchReason.ORDER_COMPLETED and tick_entry:
                self.order_book.remove_tick(tick_entry.order_id)
                self.order_book.completed_orders.append(tick_entry.order_id)
            elif tick_entry:
                # Search for a new match
                self.match(tick_entry.tick)

    def cancel_order(self, order_id):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and order.status == "open":
            self.order_manager.cancel_order(order_id)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

            return self.create_new_cancel_order_block(order).addCallback(self.send_block)

        return succeed(None)

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

            if message.name != 'start-transaction' and message.name != 'transaction-completed-bc' \
                    and not self.transaction_manager.find_by_id(transaction_id):
                yield DropMessage(message, "Unknown transaction in %s message" % message.name)
                continue

            transaction = self.transaction_manager.find_by_id(transaction_id)
            if message.name not in ['start-transaction', 'transaction-completed-bc'] and \
                    transaction.is_payment_complete():
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

                def build_tx_init_block(other_order_dict):
                    my_order_dict = order.to_status_dictionary()
                    my_order_dict["ip"], my_order_dict["port"] = self.get_dispersy_address()

                    if order.is_ask():
                        ask_order_dict = my_order_dict
                        bid_order_dict = other_order_dict
                    else:
                        ask_order_dict = other_order_dict
                        bid_order_dict = my_order_dict

                    # Create a tx_init block to capture that we are going to initiate a transaction
                    self.create_new_tx_init_block(message.candidate, ask_order_dict, bid_order_dict, transaction).\
                        addCallback(lambda _: self.send_wallet_info(transaction, incoming_address, outgoing_address))

                self.send_order_status_request(start_transaction.order_id).addCallback(build_tx_init_block)

    def send_order_status_request(self, order_id):
        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(order_id.trader_id), False)

        self._logger.debug("Sending order status request to trader %s (number: %d)",
                           order_id.trader_id, order_id.order_number)

        request_deferred = Deferred()
        cache = self._request_cache.add(OrderStatusRequestCache(self, request_deferred))

        message_id = self.message_repository.next_identity()
        meta = self.get_meta_message(u"order-status-request")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                Timestamp.now(),
                order_id.trader_id,
                order_id.order_number,
                cache.number
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)

        return request_deferred

    def on_order_status_request(self, messages):
        for message in messages:
            queried_order_id = OrderId(message.payload.order_trader_id, message.payload.order_number)
            order = self.order_manager.order_repository.find_by_id(queried_order_id)

            message_id = self.message_repository.next_identity()
            meta = self.get_meta_message(u"order-status-response")
            new_message = meta.impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                destination=(message.candidate,),
                payload=order.to_network(message_id) + self.get_dispersy_address() + (message.payload.identifier,)
            )

            self.dispersy.store_update_forward([new_message], True, False, True)

    def on_order_status_response(self, messages):
        for message in messages:
            request = self.request_cache.pop(u"order-status-request", message.payload.identifier)

            # Convert the order status to a dictionary that is saved on TradeChain
            order_dict = {
                "trader_id": str(message.payload.trader_id),
                "order_number": int(message.payload.order_number),
                "price": float(message.payload.price),
                "price_type": message.payload.price.wallet_id,
                "quantity": float(message.payload.quantity),
                "quantity_type": message.payload.quantity.wallet_id,
                "traded_quantity": float(message.payload.traded_quantity),
                "timeout": float(message.payload.timeout),
                "timestamp": float(message.payload.timestamp),
                "ip": message.payload.address.ip,
                "port": message.payload.address.port
            }

            request.request_deferred.callback(order_dict)

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
                lambda _, cd=message.candidate, pm=payment_message, tx=transaction: self.received_payment(cd, pm, tx))

    def received_payment(self, candidate, payment, transaction):
        self._logger.debug("Received payment with id %s (price: %s, quantity: %s)",
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
            self.notify_transaction_complete(transaction)
            self.send_transaction_completed(transaction, block)

        def build_tx_done_block(other_order_dict):
            my_order_dict = order.to_status_dictionary()
            my_order_dict["ip"], my_order_dict["port"] = self.get_dispersy_address()

            if order.is_ask():
                ask_order_dict = my_order_dict
                bid_order_dict = other_order_dict
            else:
                ask_order_dict = other_order_dict
                bid_order_dict = my_order_dict

            self.create_new_tx_done_block(candidate, ask_order_dict, bid_order_dict, transaction)\
                .addCallback(on_tx_done_signed)

        # Record this payment on TradeChain
        def on_payment_recorded(block):
            if not transaction.is_payment_complete():
                self.send_payment(transaction)
            else:
                self.send_order_status_request(transaction.partner_order_id).addCallback(build_tx_done_block)

        self.create_new_tx_payment_block(candidate, payment).addCallback(on_payment_recorded)

    def abort_transaction(self, transaction):
        """
        Abort a specific transaction by releasing all reserved quantity for this order.
        """
        self._logger.error("Aborting transaction %s", transaction.transaction_id)
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)
        order.release_quantity_for_tick(transaction.partner_order_id,
                                        transaction.total_quantity - transaction.transferred_quantity)
        self.order_manager.order_repository.update(order)

    def notify_transaction_complete(self, transaction):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None,
                                                 transaction.to_dictionary())

    def send_transaction_completed(self, transaction, block):
        """
        Let the matchmaker know that the transaction has been completed.
        :param transaction: The completed transaction.
        :param block: The block created by this peer defining the transaction.
        """
        if not transaction.match_id or transaction.match_id not in self.incoming_match_messages:
            return

        self._logger.debug("Sending transaction completed (match id: %s)", transaction.match_id)

        # Lookup the remote address of the peer with the pubkey
        match_message = self.incoming_match_messages[transaction.match_id]
        del self.incoming_match_messages[transaction.match_id]
        candidate = Candidate(self.lookup_ip(match_message.payload.matchmaker_trader_id), False)

        linked_block = self.market_database.get_linked(block)
        self.send_block_pair(block, linked_block, candidate)

    def on_transaction_completed_message(self, block1, block2):
        tx_dict = block1.transaction
        self._logger.debug("Received transaction-completed message")
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

    def on_transaction_completed_bc_message(self, block1, block2):
        tx_dict = block1.transaction
        self._logger.debug("Received transaction-completed-bc message")
        if not self.is_matchmaker:
            return

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
        rep_manager = PagerankReputationManager(self.tradechain_community.persistence.get_all_blocks())
        self.reputation_dict = rep_manager.compute(self.my_member.public_key)
