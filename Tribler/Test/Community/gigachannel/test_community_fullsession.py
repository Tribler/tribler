from __future__ import absolute_import
import os

from pony.orm import db_session
from six.moves import xrange
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from Tribler.community.gigachannel.community import GigaChannelCommunity
from Tribler.Core.Session import Session
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.Test.test_as_server import TestAsServer


class TestGigaChannelCommunity(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        yield TestAsServer.setUp(self)

        self.config2 = self.localize_config(self.config, 1)
        self.session2 = Session(self.config2)
        self.session2.upgrader_enabled = False
        yield self.session2.start()

        self.sessions = [self.session, self.session2]

        self.test_class = GigaChannelCommunity
        self.test_class.master_peer = Peer(default_eccrypto.generate_key(u"curve25519"))

    def localize_config(self, config, nr=0):
        out = config.copy()
        out.set_state_dir(self.getStateDir(nr))
        out.set_default_destination_dir(self.getDestDir(nr))
        out.set_permid_keypair_filename(os.path.join(self.getStateDir(nr), "keypair_" + str(nr)))
        out.set_trustchain_keypair_filename(os.path.join(self.getStateDir(nr), "tc_keypair_" + str(nr)))
        return out

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy_enabled(False)
        self.config.set_ipv8_enabled(True)
        self.config.set_libtorrent_enabled(True)
        self.config.set_trustchain_enabled(False)
        self.config.set_resource_monitor_enabled(False)
        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())
        self.config.set_chant_enabled(True)
        self.config = self.localize_config(self.config)

    @inlineCallbacks
    def tearDown(self):
        yield self.session2.shutdown()
        yield TestAsServer.tearDown(self)

    def _create_channel(self):
        self.session.lm.mds.ChannelMetadata.create_channel('test' + ''.join(str(i) for i in range(100)), 'test')
        my_key = self.session.trustchain_keypair
        my_channel_id = my_key.pub().key_to_bin()
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)
            for ind in xrange(20):
                random_infohash = '\x00' * 20
                self.session.lm.mds.TorrentMetadata(title='test ind %d' % ind, tags='test',
                                                    size=1234, infohash=random_infohash)
            my_channel.commit_channel_torrent()
            torrent_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".torrent")
            self.session.lm.updated_my_channel(torrent_path)
        return my_channel_id

    def introduce_nodes(self):
        self.session.lm.gigachannel_community.walk_to(self.session2.lm.gigachannel_community.my_estimated_lan)
        return self.deliver_messages()

    @inlineCallbacks
    def test_fetch_channel(self):
        """
        Test if a fetch_next() call is answered with a channel.
        """
        # Peer 1 creates a channel and introduces itself to peer 2
        channel_id = self._create_channel()
        yield self.introduce_nodes()

        # Peer 1 sends its channel to peer 2
        peer2 = self.session2.lm.gigachannel_community.my_peer
        peer2.address = self.session2.lm.gigachannel_community.my_estimated_lan
        self.session.lm.gigachannel_community.send_random_to(peer2)
        yield self.deliver_messages()

        # Peer 2 acts upon the known channels
        self.session2.lm.gigachannel_community.fetch_next()
        yield self.deliver_messages()

        with db_session:
            channel_list1 = list(self.session.lm.mds.ChannelMetadata.select())
            channel_list2 = list(self.session2.lm.mds.ChannelMetadata.select())

        self.assertEqual(1, len(channel_list1))
        self.assertEqual(1, len(channel_list2))
        self.assertEqual(channel_id, str(channel_list1[0].public_key))
        self.assertEqual(channel_id, str(channel_list2[0].public_key))
        self.assertTrue(self.session.has_download(str(channel_list1[0].infohash)))
        self.assertTrue(self.session2.has_download(str(channel_list1[0].infohash)))

    @inlineCallbacks
    def deliver_messages(self, timeout=.1):
        """
        Allow peers to communicate.
        The strategy is as follows:
         1. Measure the amount of working threads in the threadpool
         2. After 10 milliseconds, check if we are down to 0 twice in a row
         3. If not, go back to handling calls (step 2) or return, if the timeout has been reached
        :param timeout: the maximum time to wait for messages to be delivered
        """
        rtime = 0
        probable_exit = False
        while rtime < timeout:
            yield self.sleep(.01)
            rtime += .01
            if len(reactor.getThreadPool().working) == 0:
                if probable_exit:
                    break
                probable_exit = True
            else:
                probable_exit = False

    @inlineCallbacks
    def sleep(self, time=.05):
        yield deferLater(reactor, time, lambda: None)
