from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from core.message_repository import MemoryMessageRepository
from core.order_repository import MemoryOrderRepository
from core.price import Price
from core.quantity import Quantity
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.trade import Trade, ProposedTrade, AcceptedTrade, DeclinedTrade
from .conversion import MarketConversion
from .core.matching_engine import MatchingEngine, PriceTimeStrategy
from .core.orderbook import OrderBook
from .core.portfolio import Portfolio
from .core.tick import Ask, Bid
from .payload import AskPayload, BidPayload, ProposedTradePayload, AcceptedTradePayload, DeclinedTradePayload


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

    def initialize(self):
        super(MarketCommunity, self).initialize()
        self._logger.info("Market community initialized")

        # The public key of this node
        self.pubkey = self.my_member.mid.encode("HEX")
        self.pubkey_register = {}

        order_repository = MemoryOrderRepository(self.pubkey)
        message_repository = MemoryMessageRepository(self.pubkey)
        self.portfolio = Portfolio(order_repository)
        self.order_book = OrderBook(message_repository)
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))

    def initiate_meta_messages(self):
        return super(MarketCommunity, self).initiate_meta_messages() + [
            Message(self, u"ask",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    AskPayload(),
                    self.check_message,
                    self.on_ask),
            Message(self, u"bid",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    BidPayload(),
                    self.check_message,
                    self.on_bid),
            Message(self, u"proposed-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ProposedTradePayload(),
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
                    self.on_declined_trade)
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

    def check_ttl(self, message):
        """
        Check if the message has a ttl that is still alive and if so send the message on

        :param message: The message for which the ttl needs to be checked
        """
        message.payload.ttl -= 1  # Reduce the ttl by 1

        if message.payload.ttl > 0:  # Check if the message still has time to live
            self.dispersy.store_update_forward([message], True, True, True)

    def lookup_ip(self, pubkey):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param pubkey: The public key of the node to send to
        :type pubkey: str
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        assert isinstance(pubkey, str), type(pubkey)
        return self.pubkey_register.get(pubkey)

    def update_ip(self, pubkey, ip):
        """
        Update the public key to ip mapping

        :param pubkey: The public key of the node
        :param ip: The ip and port of the node
        :type pubkey: str
        :type ip: tuple
        """
        assert isinstance(pubkey, str), type(pubkey)
        assert isinstance(ip, tuple), type(ip)
        assert isinstance(ip[0], str)
        assert isinstance(ip[1], int)

        self.pubkey_register[pubkey] = ip

    # Ask
    def create_ask(self, price, quantity, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        """
        self._logger.debug("Ask created")

        price = Price.from_float(price)
        quantity = Quantity.from_float(quantity)
        timeout = Timeout(timeout)
        timestamp = Timestamp.now()

        tick = self.order_book.create_ask(price, quantity, timeout, timestamp)
        self.send_ask_messages([tick])

        order = self.portfolio.create_ask_order(price, quantity, timeout)
        proposed_trades = self.matching_engine.match_order(order)

        self.send_proposed_trade_messages(proposed_trades)

    def send_ask(self, ask):
        """
        Send an ask message

        :param ask: The message to send
        :type ask: Ask
        """
        assert isinstance(ask, Ask), type(ask)

        self._logger.debug("Ask send with id: " + str(ask.message_id))

        destination, payload = ask.to_network()

        payload += (2,)  # Add ttl of 2

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

            self._logger.debug("Ask received with id: " + str(ask.message_id))

            self.update_ip(str(ask.message_id.trader_id), (message.payload.ip, message.payload.port))

            if not self.order_book.tick_exists(ask.message_id):  # Message has not been received before
                self.order_book.insert_ask(ask)

                for order in self.portfolio.order_repository.find_all():
                    if not order.is_ask():
                        proposed_trades = self.matching_engine.match_order(order)
                        self.send_proposed_trade_messages(proposed_trades)

                self.check_ttl(message)

    # Bid
    def create_bid(self, price, quantity, timeout):
        """
        Create a bid order (buy order)

        :param price: The price for the order
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type quantity: float
        :type timeout: float
        """
        self._logger.debug("Bid created")

        price = Price.from_float(price)
        quantity = Quantity.from_float(quantity)
        timeout = Timeout(timeout)
        timestamp = Timestamp.now()

        tick = self.order_book.create_bid(price, quantity, timeout, timestamp)
        self.send_bid_messages([tick])

        order = self.portfolio.create_bid_order(price, quantity, timeout)
        proposed_trades = self.matching_engine.match_order(order)

        self.send_proposed_trade_messages(proposed_trades)

    def send_bid(self, bid):
        """
        Send a bid message

        :param bid: The message to send
        :type bid: Bid
        """
        assert isinstance(bid, Bid), type(bid)

        self._logger.debug("Bid send with id: " + str(bid.message_id))

        destination, payload = bid.to_network()

        payload += (2,)  # Add ttl of 2

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

            self._logger.debug("Bid received with id: " + str(bid.message_id))

            self.update_ip(str(bid.message_id.trader_id), (message.payload.ip, message.payload.port))

            if not self.order_book.tick_exists(bid.message_id):  # Message has not been received before
                self.order_book.insert_bid(bid)

                for order in self.portfolio.order_repository.find_all():
                    if order.is_ask():
                        proposed_trades = self.matching_engine.match_order(order)
                        self.send_proposed_trade_messages(proposed_trades)

                self.check_ttl(message)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        destination, payload = proposed_trade.to_network()

        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=candidate,
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_proposed_trade_messages(self, messages):
        for message in messages:
            self.send_proposed_trade(message)

    def on_proposed_trade(self, messages):
        for message in messages:
            proposed_trade = ProposedTrade.from_network(message.payload)

            if str(proposed_trade.recipient_message_id.trader_id) == str(self.my_member.mid.encode("HEX")):
                # Check if tick is still valid (send confirm and add to orderbook) : (send cancel)
                if self.order_book.tick_exists(proposed_trade.recipient_message_id):
                    accepted_trade = Trade.accept(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                                  proposed_trade)
                    self.order_book.insert_trade(accepted_trade)
                    self.order_book.remove_tick(proposed_trade.recipient_message_id)
                    self.order_book.remove_tick(proposed_trade.sender_message_id)
                    self.send_accepted_trade(accepted_trade)
                else:
                    declined_trade = Trade.decline(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                                   proposed_trade)
                    self.send_declined_trade(declined_trade)

    # Accepted trade
    def send_accepted_trade(self, accepted_trade):
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)
        destination, payload = accepted_trade.to_network()

        payload += (2,)  # Add ttl of 2

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

            self.order_book.remove_tick(accepted_trade.sender_message_id)
            self.order_book.remove_tick(accepted_trade.recipient_message_id)

            # Check if tick is our own and delete is from the portfolio

            self.check_ttl(message)

    # Declined trade
    def send_declined_trade(self, declined_trade):
        assert isinstance(declined_trade, DeclinedTrade), type(declined_trade)
        destination, payload = declined_trade.to_network()

        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"declined-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=candidate,
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_declined_trade_messages(self, messages):
        for message in messages:
            self.send_declined_trade(message)

    def on_declined_trade(self, messages):
        for message in messages:
            declined_trade = DeclinedTrade.from_network(message.payload)

            if declined_trade.is_quick():
                self.order_book.remove_tick(declined_trade.recipient_message_id)
                # match again
            else:
                self.order_book.remove_tick(declined_trade.recipient_message_id)
