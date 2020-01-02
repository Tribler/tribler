from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.tools import timeout


class TestLibTorrentSettingsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestLibTorrentSettingsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @timeout(5)
    async def test_get_settings_zero_hop(self):
        """
        Tests getting session settings for zero hop session.
        By default, there should always be a zero hop session so we should be able to get settings for
        zero hop session.
        """
        hop = 0
        response_dict = await self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200)
        settings_dict = response_dict['settings']
        self.assertEqual(response_dict['hop'], hop)
        self.assertTrue("Tribler" in settings_dict['user_agent'])
        self.assertEqual(settings_dict['outgoing_port'], 0)
        self.assertEqual(settings_dict['num_outgoing_ports'], 1)

    @timeout(5)
    async def test_get_settings_for_uninitialized_session(self):
        """
        Tests getting session for non initialized session.
        By default, anonymous sessions with hops > 1 are not initialized so test is done for
        a 2 hop session expecting empty stats.
        """
        hop = 2
        response_dict = await self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200)
        self.assertEqual(response_dict['hop'], hop)
        self.assertEqual(response_dict['settings'], {})

    @timeout(5)
    async def test_get_settings_for_one_session(self):
        """
        Tests getting session for initialized anonymous session.
        """
        hop = 1
        self.session.ltmgr.get_session(hops=hop)
        response_dict = await self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200)
        settings_dict = response_dict['settings']
        self.assertEqual(response_dict['hop'], hop)
        self.assertTrue("libtorrent" in settings_dict['user_agent'] or settings_dict['user_agent'] == '')
        self.assertEqual(settings_dict['outgoing_port'], 0)
        self.assertEqual(settings_dict['num_outgoing_ports'], 1)


class TestLibTorrentSessionEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestLibTorrentSessionEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @timeout(5)
    async def test_get_stats_zero_hop_session(self):
        """
        Tests getting session stats for zero hop session.
        By default, there should always be a zero hop session so we should be able to get stats for this session.
        """
        hop = 0
        # expected sample stats
        expected_stats = [u'dht.dht_peers', u'dht.dht_torrents', u'disk.num_jobs', u'net.recv_bytes', u'net.sent_bytes',
                          u'peer.perm_peers', u'peer.disconnected_peers', u'ses.num_seeding_torrents',
                          u'ses.num_incoming_choke']

        response_dict = await self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200)
        self.assertEqual(response_dict['hop'], hop)
        self.assertTrue(set(expected_stats) < set(response_dict['session'].keys()))

    @timeout(5)
    async def test_get_stats_for_uninitialized_session(self):
        """
        Tests getting stats for non initialized session.
        By default, anonymous sessions with hops > 1 are not initialized so test is done for
        a 2 hop session expecting empty stats.
        """
        hop = 2

        response_dict = await self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200)
        self.assertEqual(response_dict['hop'], hop)
        self.assertEqual(response_dict['session'], {})

    @timeout(5)
    async def test_get_stats_for_one_hop_session(self):
        """
        Tests getting stats for initialized anonymous session.
        """
        hop = 1
        self.session.ltmgr.get_session(hops=hop)

        # expected sample stats
        expected_stats = [u'dht.dht_peers', u'dht.dht_torrents', u'disk.num_jobs', u'net.recv_bytes', u'net.sent_bytes',
                          u'peer.perm_peers', u'peer.disconnected_peers', u'ses.num_seeding_torrents',
                          u'ses.num_incoming_choke']

        response_dict = await self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200)
        self.assertEqual(response_dict['hop'], hop)
        self.assertTrue(set(expected_stats) < set(response_dict['session'].keys()))
