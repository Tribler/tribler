import os


import logging
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.wallet.btc_wallet import BitcoinWallet
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.community.market.wallet.tc_wallet import TrustchainWallet
from Tribler.community.triblerchain.community import TriblerChainCommunity
from Tribler.community.tradechain.community import TradeChainCommunity
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.discovery.community import BOOTSTRAP_FILE_ENVNAME
from Tribler.dispersy.util import blocking_call_on_reactor_thread


logging.basicConfig(level=logging.DEBUG)


class MarketCommunityTests(MarketCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = MarketCommunityTests.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]


class TriblerChainCommunityTests(TriblerChainCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = TriblerChainCommunityTests.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]


class TradeChainCommunityTests(TradeChainCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    def __init__(self, *args, **kwargs):
        super(TradeChainCommunityTests, self).__init__(*args, **kwargs)
        self.expected_sig_response = None

    def wait_for_signature_response(self):
        response_deferred = Deferred()
        self.expected_sig_response = response_deferred
        return response_deferred

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = TradeChainCommunityTests.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]

    def received_half_block(self, messages):
        super(TradeChainCommunityTests, self).received_half_block(messages)

        if self.expected_sig_response:
            self.expected_sig_response.callback(None)
            self.expected_sig_response = None


class TestMarketBase(TestAsServer):

    def async_sleep(self, secs):
        d = Deferred()
        reactor.callLater(secs, d.callback, None)
        return d

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        """
        Setup various variables.
        """
        os.environ[BOOTSTRAP_FILE_ENVNAME] = os.path.join(TESTS_DATA_DIR, 'bootstrap_empty.txt')

        yield TestAsServer.setUp(self, autoload_discovery=autoload_discovery)

        self.sessions = []
        self.eccrypto = ECCrypto()
        ec = self.eccrypto.generate_key(u"curve25519")
        MarketCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')
        ec = self.eccrypto.generate_key(u"curve25519")
        TriblerChainCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')
        ec = self.eccrypto.generate_key(u"curve25519")
        TradeChainCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')

        market_member = self.generate_member(self.session)

        self.market_communities = {}
        mc_community = self.load_triblerchain_community_in_session(self.session)
        self.load_market_community_in_session(self.session, market_member, mc_community)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        for session in self.sessions:
            yield session.shutdown()

        yield TestAsServer.tearDown(self)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy_enabled(True)
        self.config.set_libtorrent_enabled(False)
        self.config.set_video_server_enabled(False)
        self.config.set_trustchain_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_market_community_enabled(False)

    def generate_member(self, session):
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        return dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

    @blocking_call_on_reactor_thread
    def load_market_community_in_session(self, session, market_member, mc_community):
        """
        Load the market community and tradechain community in a given session.
        """
        wallets = {'BTC': BitcoinWallet(os.path.join(session.config.get_state_dir(), 'wallet')),
                   'MC': TrustchainWallet(mc_community), 'DUM1': DummyWallet1(), 'DUM2': DummyWallet2()}
        wallets['MC'].check_negative_balance = False

        dispersy = session.get_dispersy_instance()

        # Load TradeChain
        tradechain_community = dispersy.define_auto_load(TradeChainCommunityTests,
                                                         market_member, load=True, kargs={})[0]

        # Load MarketCommunity
        market_kargs = {'tribler_session': session, 'tradechain_community': tradechain_community, 'wallets': wallets}
        self.market_communities[session] = dispersy.define_auto_load(
            MarketCommunityTests, market_member, kargs=market_kargs, load=True)[0]
        tradechain_community.market_community = self.market_communities[session]
        return self.market_communities[session]

    @blocking_call_on_reactor_thread
    def load_triblerchain_community_in_session(self, session):
        """
        Load a custom instance of the TriblerChain community in a given session.
        """
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        triblerchain_kwargs = {'tribler_session': session}
        return dispersy.define_auto_load(TriblerChainCommunityTests, dispersy_member,
                                         load=True, kargs=triblerchain_kwargs)[0]

    @inlineCallbacks
    def create_session(self, index):
        """
        Create a single session and load the tunnel community in the session of that proxy.
        """
        from Tribler.Core.Session import Session

        config = self.config.copy()
        config.set_state_dir(self.getStateDir(index))

        session = Session(config, ignore_singleton=True, autoload_discovery=False)
        yield session.start()
        self.sessions.append(session)

        market_member = self.generate_member(session)
        mc_community = self.load_triblerchain_community_in_session(session)
        self.load_market_community_in_session(session, market_member, mc_community)
        returnValue(session)
