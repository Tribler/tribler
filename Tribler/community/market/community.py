from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from conversion import MarketConversion
from core.matching_engine import MatchingEngine, PriceTimeStrategy
from core.message import TraderId
from core.message_repository import MemoryMessageRepository
from core.order import TickWasNotReserved
from core.order_manager import OrderManager
from core.order_repository import MemoryOrderRepository
from core.orderbook import OrderBook
from core.payment import BitcoinPayment, MultiChainPayment
from core.payment_provider import BitcoinPaymentProvider, MultiChainPaymentProvider, InsufficientFunds
from core.price import Price
from core.quantity import Quantity
from core.tick import Ask, Bid, Tick
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.trade import Trade, ProposedTrade, AcceptedTrade, DeclinedTrade, CounterTrade
from core.transaction import StartTransaction, TransactionId, Transaction
from core.transaction_manager import TransactionManager
from core.transaction_repository import MemoryTransactionRepository
from payload import OfferPayload, TradePayload, AcceptedTradePayload, DeclinedTradePayload, StartTransactionPayload, \
    MultiChainPaymentPayload, BitcoinPaymentPayload, TransactionPayload
from ttl import Ttl


class MarketCommunity(Community):
    """Community for selling and buying multichain coins"""

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
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059" \
                     "c773dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8db" \
                     "bb634906989395d366888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdf" \
                     "dabb434396d23945d1239f88de4935467424c7cc02b6579e45f63ee".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initialize(self, multi_chain_community=None):
        super(MarketCommunity, self).initialize()
        self._logger.info("Market community initialized")

        # The public key of this node
        self.pubkey = self.my_member.public_key.encode("HEX")
        self.pubkey_register = {}  # TODO: fix memory leak

        order_repository = MemoryOrderRepository(self.pubkey)
        message_repository = MemoryMessageRepository(self.pubkey)
        self.order_manager = OrderManager(order_repository)
        self.order_book = OrderBook(message_repository)
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))

        self.multi_chain_payment_provider = MultiChainPaymentProvider(multi_chain_community, self.pubkey)
        self.bitcoin_payment_provider = BitcoinPaymentProvider()
        transaction_repository = MemoryTransactionRepository(self.pubkey)
        self.transaction_manager = TransactionManager(transaction_repository)

        self.history = {}  # List for received messages TODO: fix memory leak

    def initiate_meta_messages(self):
        return super(MarketCommunity, self).initiate_meta_messages() + [
            Message(self, u"ask",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_message,
                    self.on_ask),
            Message(self, u"bid",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_message,
                    self.on_bid),
            Message(self, u"proposed-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_message,
                    self.on_proposed_trade),
            Message(self, u"accepted-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    AcceptedTradePayload(),
                    self.check_message,
                    self.on_accepted_trade),
            Message(self, u"declined-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    DeclinedTradePayload(),
                    self.check_message,
                    self.on_declined_trade),
            Message(self, u"counter-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_message,
                    self.on_counter_trade),
            Message(self, u"start-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    StartTransactionPayload(),
                    self.check_message,
                    self.on_start_transaction),
            Message(self, u"continue-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TransactionPayload(),
                    self.check_message,
                    self.on_continue_transaction),
            Message(self, u"multi-chain-payment",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    MultiChainPaymentPayload(),
                    self.check_message,
                    self.on_multi_chain_payment),
            Message(self, u"bitcoin-payment",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    BitcoinPaymentPayload(),
                    self.check_message,
                    self.on_bitcoin_payment),
            Message(self, u"end-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TransactionPayload(),
                    self.check_message,
                    self.on_end_transaction)
        ]

    def initiate_conversions(self):
        return [DefaultConversion(self), MarketConversion(self)]

    def check_message(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                yield message
            else:
                yield DelayMessageByProof(message)

    def check_history(self, message):
        """
        Check if the message is already in the history, meaning it has already been received before

        :param message: The message to check for
        :return: True if the message is new to this node, False otherwise
        :rtype: bool
        """
        if message.message_id in self.history:
            return False
        else:
            self.history[message.message_id] = True
            return True

    def lookup_ip(self, trader_id):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param trader_id: The public key of the node to send to
        :type trader_id: TraderId
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        assert isinstance(trader_id, TraderId), type(trader_id)
        return self.pubkey_register.get(trader_id)

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

        self.pubkey_register[trader_id] = ip

    def get_multichain_balance(self):
        """
        Return the current multichain balance from the payment provider

        :return: The quantity (1 mil is 100 bytes)
        :rtype: Quantity
        """
        return self.multi_chain_payment_provider.balance()

    # Ask
    def create_ask(self, price, quantity, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param quantity: The quantity of the order in MB (10^6)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        self._logger.debug("Ask created")

        # Convert values to value objects
        price = Price.from_float(price)
        quantity = Quantity.from_float(quantity)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_ask_order(price, quantity, timeout)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        assert isinstance(tick, Ask), type(tick)
        self.order_book.insert_ask(tick)
        self.send_ask_messages([tick])

        # Search for matches
        proposed_trades = self.matching_engine.match_order(order)
        self.send_proposed_trade_messages(proposed_trades)

        return order

    def send_ask(self, ask):
        """
        Send an ask message

        :param ask: The message to send
        :type ask: Ask
        """
        assert isinstance(ask, Ask), type(ask)

        self._logger.debug("Ask send with id: %s for order with id: %s", str(ask.message_id), str(ask.order_id))

        payload = ask.to_network()

        # Add ttl and the local wan address
        payload += (Ttl.default(), self.dispersy.wan_address[0], self.dispersy.wan_address[1])

        meta = self.get_meta_message(u"ask")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_ask_messages(self, messages):
        for message in messages:
            self.send_ask(message)

    def on_ask(self, messages):
        for message in messages:
            ask = Ask.from_network(message.payload)

            self._logger.debug("Ask received with id: %s for order with id: %s", str(ask.message_id), str(ask.order_id))

            # Update the pubkey register with the current address
            self.update_ip(ask.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not self.order_book.tick_exists(ask.order_id):  # Message has not been received before
                self.order_book.insert_ask(ask)

                # Check for new matches against the orders of this node
                for order in self.order_manager.order_repository.find_all():
                    if (not order.is_ask()) and order.is_valid():
                        proposed_trades = self.matching_engine.match_order(order)
                        self.send_proposed_trade_messages(proposed_trades)

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    # Bid
    def create_bid(self, price, quantity, timeout):
        """
        Create a bid order (buy order)

        :param price: The price for the order in btc
        :param quantity: The quantity of the order in MB (10^6)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        self._logger.debug("Bid created")

        # Convert values to value objects
        price = Price.from_float(price)
        quantity = Quantity.from_float(quantity)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_bid_order(price, quantity, timeout)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        assert isinstance(tick, Bid), type(tick)
        self.order_book.insert_bid(tick)
        self.send_bid_messages([tick])

        # Search for matches
        proposed_trades = self.matching_engine.match_order(order)
        self.send_proposed_trade_messages(proposed_trades)

        return order

    def send_bid(self, bid):
        """
        Send a bid message

        :param bid: The message to send
        :type bid: Bid
        """
        assert isinstance(bid, Bid), type(bid)

        self._logger.debug("Bid send with id: %s for order with id: %s", str(bid.message_id), str(bid.order_id))

        payload = bid.to_network()

        # Add ttl and the local wan address
        payload += (Ttl.default(), self.dispersy.wan_address[0], self.dispersy.wan_address[1])

        meta = self.get_meta_message(u"bid")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_bid_messages(self, messages):
        for message in messages:
            self.send_bid(message)

    def on_bid(self, messages):
        for message in messages:
            bid = Bid.from_network(message.payload)

            self._logger.debug("Bid received with id: %s for order with id: %s", str(bid.message_id), str(bid.order_id))

            # Update the pubkey register with the current address
            self.update_ip(bid.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not self.order_book.tick_exists(bid.order_id):  # Message has not been received before
                self.order_book.insert_bid(bid)

                # Check for new matches against the orders of this node
                for order in self.order_manager.order_repository.find_all():
                    if order.is_ask() and order.is_valid():
                        proposed_trades = self.matching_engine.match_order(order)
                        self.send_proposed_trade_messages(proposed_trades)

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        destination, payload = proposed_trade.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_proposed_trade_messages(self, messages):
        for message in messages:
            self.send_proposed_trade(message)

    def on_proposed_trade(self, messages):
        for message in messages:
            proposed_trade = ProposedTrade.from_network(message.payload)

            if str(proposed_trade.recipient_order_id.trader_id) == str(self.pubkey):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

                if order and order.is_valid() and order.available_quantity > Quantity(0):  # Order is valid
                    self._logger.debug("Proposed trade received with id: %s for order with id: %s",
                                       str(proposed_trade.message_id), str(order.order_id))

                    if order.available_quantity >= proposed_trade.quantity:  # Enough quantity left
                        self.accept_trade(order, proposed_trade)
                    else:  # Not enough quantity for trade
                        counter_trade = Trade.counter(self.order_book.message_repository.next_identity(),
                                                      order.available_quantity, Timestamp.now(), proposed_trade)
                        order.reserve_quantity_for_tick(proposed_trade.order_id, order.available_quantity)
                        self._logger.debug("Counter trade made with id: %s for proposed trade with id: %s",
                                           str(counter_trade.message_id), str(proposed_trade.message_id))
                        self.send_counter_trade(counter_trade)
                else:  # Order invalid send cancel
                    declined_trade = Trade.decline(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                                   proposed_trade)
                    self._logger.debug("Declined trade made with id: %s for proposed trade with id: %s",
                                       str(declined_trade.message_id), str(proposed_trade.message_id))
                    self.send_declined_trade(declined_trade)

    # Accepted trade
    def send_accepted_trade(self, accepted_trade):
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)
        destination, payload = accepted_trade.to_network()

        # Add ttl
        payload += (Ttl.default(),)

        meta = self.get_meta_message(u"accepted-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_accepted_trade_messages(self, messages):
        for message in messages:
            self.send_accepted_trade(message)

    def on_accepted_trade(self, messages):
        for message in messages:
            accepted_trade = AcceptedTrade.from_network(message.payload)

            if self.check_history(accepted_trade):  # The message is new to this node
                order = self.order_manager.order_repository.find_by_id(accepted_trade.recipient_order_id)

                if order:  # This is a trade with this node
                    try:
                        order.add_trade(accepted_trade)  # Remove quantity from order and store trade
                        self.order_book.trade_tick(accepted_trade)  # Remove ticks from order book
                    except TickWasNotReserved:  # Something went wrong
                        pass
                else:  # This is a trade between two other nodes
                    self.order_book.trade_tick(accepted_trade)  # Remove ticks from order book

                ttl = message.payload.ttl  # Check if message needs to be send on
                ttl.make_hop()  # Complete the hop from the previous node
                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

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

        self.dispersy.store_update_forward([message], True, True, True)

    def send_declined_trade_messages(self, messages):
        for message in messages:
            self.send_declined_trade(message)

    def on_declined_trade(self, messages):
        for message in messages:
            declined_trade = DeclinedTrade.from_network(message.payload)

            if str(declined_trade.recipient_order_id.trader_id) == str(self.pubkey):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)

                if order:
                    try:
                        order.release_quantity_for_tick(declined_trade.order_id)
                    except TickWasNotReserved:  # Nothing left to do
                        pass

    # Counter trade
    def send_counter_trade(self, counter_trade):
        assert isinstance(counter_trade, CounterTrade), type(counter_trade)
        destination, payload = counter_trade.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"counter-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_counter_trade_messages(self, messages):
        for message in messages:
            self.send_counter_trade(message)

    def on_counter_trade(self, messages):
        for message in messages:
            counter_trade = CounterTrade.from_network(message.payload)

            if str(counter_trade.recipient_order_id.trader_id) == str(self.pubkey):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)

                if order:
                    try:  # Accept trade
                        order.release_quantity_for_tick(counter_trade.order_id)
                        self.accept_trade(order, counter_trade)
                    except TickWasNotReserved:  # Send cancel
                        declined_trade = Trade.decline(self.order_book.message_repository.next_identity(),
                                                       Timestamp.now(), counter_trade)
                        self._logger.debug("Declined trade made with id: %s for counter trade with id: %s",
                                           str(declined_trade.message_id), str(counter_trade.message_id))
                        self.send_declined_trade(declined_trade)

    def accept_trade(self, order, proposed_trade):
        accepted_trade = Trade.accept(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                      proposed_trade)

        self._logger.debug("Accepted trade made with id: %s for proposed/counter trade with id: %s",
                           str(accepted_trade.message_id), str(proposed_trade.message_id))

        self.check_history(accepted_trade)  # Set the message received as true

        self.order_book.insert_trade(accepted_trade)
        order.add_trade(accepted_trade)  # Remove quantity from order and store trade
        self.order_book.trade_tick(accepted_trade)  # Remove ticks from order book

        self.send_accepted_trade(accepted_trade)
        self.start_transaction(accepted_trade)

    # Transactions
    def start_transaction(self, accepted_trade):
        order = self.order_manager.order_repository.find_by_id(accepted_trade.order_id)

        if order:
            transaction = self.transaction_manager.create_from_accepted_trade(accepted_trade)
            order.add_transaction(accepted_trade.message_id, transaction)

            start_transaction = StartTransaction(self.order_book.message_repository.next_identity(),
                                                 transaction.transaction_id, accepted_trade.recipient_order_id,
                                                 accepted_trade.message_id, Timestamp.now())
            self.send_start_transaction(transaction, start_transaction)

    # Start transaction
    def send_start_transaction(self, transaction, start_transaction):
        assert isinstance(start_transaction, StartTransaction), type(start_transaction)
        payload = start_transaction.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        meta = self.get_meta_message(u"start-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def on_start_transaction(self, messages):
        for message in messages:
            start_transaction = StartTransaction.from_network(message.payload)

            order = self.order_manager.order_repository.find_by_id(start_transaction.order_id)

            if order:
                transaction = self.transaction_manager.create_from_start_transaction(start_transaction, order.price,
                                                                                     order.total_quantity,
                                                                                     order.timeout)
                order.add_transaction(start_transaction.accepted_trade_message_id, transaction)

                if order.is_ask():  # Send multi chain payment
                    message_id = self.order_book.message_repository.next_identity()
                    multi_chain_payment = self.transaction_manager.create_multi_chain_payment(message_id, transaction)
                    self.send_multi_chain_payment(transaction, multi_chain_payment)
                else:  # Send continue transaction
                    self.send_continue_transaction(transaction)

    # Continue transaction
    def send_continue_transaction(self, transaction):
        assert isinstance(transaction, Transaction), type(transaction)

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"continue-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def on_continue_transaction(self, messages):
        for message in messages:
            transaction = self.transaction_manager.find_by_id(
                TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number))

            if transaction:  # Send multi chain payment
                message_id = self.order_book.message_repository.next_identity()
                multi_chain_payment = self.transaction_manager.create_multi_chain_payment(message_id, transaction)
                self.send_multi_chain_payment(transaction, multi_chain_payment)

    # Multi chain payment
    def send_multi_chain_payment(self, transaction, multi_chain_payment):
        assert isinstance(multi_chain_payment, MultiChainPayment), type(multi_chain_payment)
        payload = multi_chain_payment.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        try:
            self.multi_chain_payment_provider.transfer_multi_chain(candidate, multi_chain_payment.transferor_quantity)

            meta = self.get_meta_message(u"multi-chain-payment")
            message = meta.impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                destination=(candidate,),
                payload=payload
            )

            self.dispersy.store_update_forward([message], True, True, True)
        except InsufficientFunds:  # Not enough funds
            pass

    def on_multi_chain_payment(self, messages):
        for message in messages:
            multi_chain_payment = MultiChainPayment.from_network(message.payload)
            transaction = self.transaction_manager.find_by_id(multi_chain_payment.transaction_id)

            if transaction:
                transaction.add_payment(multi_chain_payment)
                self.transaction_manager.transaction_repository.update(transaction)

                message_id = self.order_book.message_repository.next_identity()
                bitcoin_payment = self.transaction_manager.create_bitcoin_payment(message_id, transaction,
                                                                                  multi_chain_payment)
                self.send_bitcoin_payment(transaction, bitcoin_payment)

    # Bitcoin payment
    def send_bitcoin_payment(self, transaction, bitcoin_payment):
        assert isinstance(bitcoin_payment, BitcoinPayment), type(bitcoin_payment)
        payload = bitcoin_payment.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        try:
            self.bitcoin_payment_provider.transfer_bitcoin(bitcoin_payment.bitcoin_address, bitcoin_payment.price)

            meta = self.get_meta_message(u"bitcoin-payment")
            message = meta.impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                destination=(candidate,),
                payload=payload
            )

            self.dispersy.store_update_forward([message], True, True, True)
        except InsufficientFunds:  # not enough funds
            pass

    def on_bitcoin_payment(self, messages):
        for message in messages:
            bitcoin_payment = BitcoinPayment.from_network(message.payload)
            transaction = self.transaction_manager.find_by_id(bitcoin_payment.transaction_id)

            if transaction:
                transaction.add_payment(bitcoin_payment)
                self.transaction_manager.transaction_repository.update(transaction)

                if not transaction.is_payment_complete():
                    message_id = self.order_book.message_repository.next_identity()
                    multi_chain_payment = self.transaction_manager.create_multi_chain_payment(message_id, transaction)
                    self.send_multi_chain_payment(transaction, multi_chain_payment)
                else:
                    self.send_end_transaction(transaction)

    # End transaction
    def send_end_transaction(self, transaction):
        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

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
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def on_end_transaction(self, messages):
        for message in messages:
            pass
