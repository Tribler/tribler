import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout


class TestLibTorrentSettingsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestLibTorrentSettingsEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @trial_timeout(5)
    def test_get_settings_zero_hop(self):
        """
        Tests getting session settings for zero hop session.
        By default, there should always be a zero hop session so we should be able to get settings for
        zero hop session.
        """
        hop = 0

        def verify_settings(result):
            result_json = json.loads(result)
            settings_json = result_json['settings']
            self.assertEqual(result_json['hop'], hop)
            self.assertTrue("Tribler" in settings_json['user_agent'])
            self.assertEqual(settings_json['outgoing_port'], 0)
            self.assertEqual(settings_json['num_outgoing_ports'], 1)

        self.should_check_equality = False
        return self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200).addCallback(verify_settings)

    @trial_timeout(5)
    def test_get_settings_for_uninitialized_session(self):
        """
        Tests getting session for non initialized session.
        By default, anonymous sessions are not initialized so test is done for 1 hop session.
        """
        hop = 1

        def verify_settings(result):
            result_json = json.loads(result)
            self.assertEqual(result_json['hop'], hop)

            settings_json = result_json['settings']
            self.assertEqual(settings_json, {})

        self.should_check_equality = False
        return self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200).addCallback(verify_settings)

    @trial_timeout(5)
    def test_get_settings_for_one_session(self):
        """
        Tests getting session for initialized anonymous session.
        """
        hop = 1
        self.session.lm.ltmgr.get_session(hops=hop)

        def verify_settings(result):
            result_json = json.loads(result)
            settings_json = result_json['settings']
            self.assertEqual(result_json['hop'], hop)
            self.assertTrue("libtorrent" in settings_json['user_agent'])
            self.assertEqual(settings_json['outgoing_port'], 0)
            self.assertEqual(settings_json['num_outgoing_ports'], 1)

        self.should_check_equality = False
        return self.do_request('libtorrent/settings?hop=%d' % hop, expected_code=200).addCallback(verify_settings)


class TestLibTorrentSessionEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestLibTorrentSessionEndpoint, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @trial_timeout(5)
    def test_get_stats_zero_hop_session(self):
        """
        Tests getting session stats for zero hop session.
        By default, there should always be a zero hop session so we should be able to get stats for this session.
        """
        hop = 0
        # expected sample stats
        expected_stats = [u'dht.dht_peers', u'dht.dht_torrents', u'disk.num_jobs', u'net.recv_bytes', u'net.sent_bytes',
                          u'peer.perm_peers', u'peer.disconnected_peers', u'ses.num_seeding_torrents',
                          u'ses.num_incoming_choke']

        def verify_stats(result):
            result_json = json.loads(result)
            session_json = result_json['session']
            self.assertEqual(result_json['hop'], hop)
            self.assertTrue(set(expected_stats) < set(session_json.keys()))

        self.should_check_equality = False
        return self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200).addCallback(verify_stats)

    @trial_timeout(5)
    def test_get_stats_for_uninitialized_session(self):
        """
        Tests getting stats for non initialized session.
        By default, anonymous sessions are not initialized so test is done for 1 hop session expecting empty stats.
        """
        hop = 1

        def verify_stats(result):
            result_json = json.loads(result)
            self.assertEqual(result_json['hop'], hop)

            session_json = result_json['session']
            self.assertEqual(session_json, {})

        self.should_check_equality = False
        return self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200).addCallback(verify_stats)

    @trial_timeout(5)
    def test_get_stats_for_one_hop_session(self):
        """
        Tests getting stats for initialized anonymous session.
        """
        hop = 1
        self.session.lm.ltmgr.get_session(hops=hop)

        # expected sample stats
        expected_stats = [u'dht.dht_peers', u'dht.dht_torrents', u'disk.num_jobs', u'net.recv_bytes', u'net.sent_bytes',
                          u'peer.perm_peers', u'peer.disconnected_peers', u'ses.num_seeding_torrents',
                          u'ses.num_incoming_choke']

        def verify_stats(result):
            result_json = json.loads(result)
            session_json = result_json['session']
            self.assertEqual(result_json['hop'], hop)
            self.assertTrue(set(expected_stats) < set(session_json.keys()))

        self.should_check_equality = False
        return self.do_request('libtorrent/session?hop=%d' % hop, expected_code=200).addCallback(verify_stats)
