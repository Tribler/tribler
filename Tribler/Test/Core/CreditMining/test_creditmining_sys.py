# coding=utf-8
"""
Module of Credit mining function testing

Written by Ardhi Putra Pratama H
"""
import binascii
import os
import shutil
from unittest import skip

from twisted.internet import defer
from twisted.web.server import Site
from twisted.web.static import File

from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.twisted_thread import deferred, reactor
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_UPDATE, NTFY_CHANNELCAST
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent
from Tribler.Policies.BoostingManager import BoostingManager, BoostingSettings
from Tribler.Test.Core.CreditMining.mock_creditmining import MockLtTorrent, ResourceFailClass
from Tribler.Test.common import TORRENT_FILE, TORRENT_FILE_INFOHASH
from Tribler.Test.test_as_server import TestAsServer, TESTS_DATA_DIR
from Tribler.Test.util import prepare_xml_rss
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


@skip("Disabled credit mining tests until they are stable again")
class TestBoostingManagerSys(TestAsServer):
    """
    base class to test base credit mining function
    """

    def setUp(self, autoload_discovery=True):
        super(TestBoostingManagerSys, self).setUp()

        self.set_boosting_settings()

        self.session.lm.ltmgr.get_session().find_torrent = lambda _: MockLtTorrent()

        self.boosting_manager = BoostingManager(self.session, self.bsettings)

        self.session.lm.boosting_manager = self.boosting_manager

    def set_boosting_settings(self):
        """
        set settings in credit mining
        """
        self.bsettings = BoostingSettings(self.session)
        self.bsettings.credit_mining_path = os.path.join(self.session_base_dir, "credit_mining")
        self.bsettings.load_config = False
        self.bsettings.check_dependencies = False
        self.bsettings.min_connection_start = -1
        self.bsettings.min_channels_start = -1

        self.bsettings.max_torrents_active = 8
        self.bsettings.max_torrents_per_source = 5

        self.bsettings.tracker_interval = 5
        self.bsettings.initial_tracker_interval = 5
        self.bsettings.logging_interval = 30
        self.bsettings.initial_logging_interval = 3

    def setUpPreSession(self):
        super(TestBoostingManagerSys, self).setUpPreSession()

        self.config.set_torrent_checking(True)
        self.config.set_megacache(True)
        self.config.set_dispersy(True)
        self.config.set_torrent_store(True)
        self.config.set_enable_torrent_search(True)
        self.config.set_enable_channel_search(True)
        self.config.set_libtorrent(True)

    def tearDown(self):
        DefaultDownloadStartupConfig.delInstance()
        self.boosting_manager.shutdown()

        super(TestBoostingManagerSys, self).tearDown()

    def check_torrents(self, src, defer_param=None, target=1):
        """
        function to check if a torrent is already added to the source

        In this function,
        """
        if defer_param is None:
            defer_param = defer.Deferred()

        src_obj = self.boosting_manager.get_source_object(src)
        if len(src_obj.torrents) < target:
            reactor.callLater(1, self.check_torrents, src, defer_param, target=target)
        else:
            # notify torrent (emulate scraping)
            self.boosting_manager.scrape_trackers()

            def _get_tor_dummy(_, keys=123, include_mypref=True):
                """
                function to emulate get_torrent in torrent_db
                """
                return {'C.torrent_id': 93, 'category': u'Compressed', 'torrent_id': 41,
                        'infohash': src_obj.torrents.keys()[0], 'length': 1150844928, 'last_tracker_check': 10001,
                        'myDownloadHistory': False, 'name': u'ubuntu-15.04-desktop-amd64.iso',
                        'num_leechers': 999, 'num_seeders': 123, 'status': u'unknown', 'tracker_check_retries': 0}
            self.boosting_manager.torrent_db.getTorrent = _get_tor_dummy
            self.session.notifier.notify(NTFY_TORRENTS, NTFY_UPDATE, src_obj.torrents.keys()[0])

            # log it
            self.boosting_manager.log_statistics()

            defer_param.callback(src)
        return defer_param

    def check_source(self, src, defer_param=None, ready=True):
        """
        function to check if a source is ready initializing
        """
        if defer_param is None:
            defer_param = defer.Deferred()

        src_obj = self.boosting_manager.get_source_object(src)

        if not ready:
            defer_param.callback(src)
        elif not src_obj or not src_obj.ready:
            reactor.callLater(1, self.check_source, src, defer_param)
        else:
            defer_param.callback(src)

        return defer_param


@skip("Disabled credit mining tests until they are stable again")
class TestBoostingManagerSysRSS(TestBoostingManagerSys):
    """
    testing class for RSS (dummy) source
    """

    def setUp(self, autoload_discovery=True):
        super(TestBoostingManagerSysRSS, self).setUp()

        files_path, self.file_server_port = prepare_xml_rss(self.session_base_dir, 'test_rss_cm.xml')

        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        self.setUpFileServer(self.file_server_port, self.session_base_dir)

        self.rss_error_deferred = defer.Deferred()
        # now the rss should be at :
        # http://localhost:port/test_rss_cm.xml
        # which resides in sessiondir/http_torrent_files

    def set_boosting_settings(self):
        super(TestBoostingManagerSysRSS, self).set_boosting_settings()
        self.bsettings.auto_start_source = False

    def setUpFileServer(self, port, path):
        resource = File(path)
        resource.putChild("err503", ResourceFailClass())
        factory = Site(resource)
        self._logger.debug("Listen to port %s, factory %s", port, factory)
        self.file_server = reactor.listenTCP(port, factory)

    @deferred(timeout=15)
    def test_rss(self):
        """
        test rss source
        """
        url = 'http://localhost:%s/test_rss_cm.xml' % self.file_server_port
        self.boosting_manager.add_source(url)

        rss_obj = self.boosting_manager.get_source_object(url)
        rss_obj.start()

        d = self.check_source(url)
        d.addCallback(self.check_torrents, target=1)
        return d

    def _on_error_rss(self, dummy_1, dummy_2):
        """
        dummy errback when RSS source produces an error
        """
        self.rss_error_deferred.callback(True)

    @deferred(timeout=8)
    def test_rss_unexist(self):
        """
        Testing an unexisting RSS feed
        """
        url = 'http://localhost:%s/nothingness' % self.file_server_port
        self.boosting_manager.add_source(url)

        rss_obj = self.boosting_manager.get_source_object(url)
        rss_obj._on_error_rss = self._on_error_rss
        rss_obj.start()

        defer_err_rss = self.check_source(url, ready=False)
        defer_err_rss.chainDeferred(self.rss_error_deferred)
        return defer_err_rss

    @deferred(timeout=8)
    def test_rss_unavailable(self):
        """
        Testing an unavailable RSS feed
        """
        url = 'http://localhost:%s/err503' % self.file_server_port
        self.boosting_manager.add_source(url)

        rss_obj = self.boosting_manager.get_source_object(url)
        rss_obj._on_error_rss = self._on_error_rss
        rss_obj.start()

        defer_err_rss = self.check_source(url, ready=False)
        defer_err_rss.chainDeferred(self.rss_error_deferred)
        return defer_err_rss


@skip("Disabled credit mining tests until they are stable again")
class TestBoostingManagerSysDir(TestBoostingManagerSys):
    """
    testing class for directory source
    """

    @deferred(timeout=10)
    def test_dir(self):
        """
        test directory filled with .torrents
        """
        self.boosting_manager.add_source(TESTS_DATA_DIR)
        len_source = len(self.boosting_manager.boosting_sources)

        # deliberately try to add the same source
        self.boosting_manager.add_source(TESTS_DATA_DIR)
        self.assertEqual(len(self.boosting_manager.boosting_sources), len_source, "identical source added")

        dir_obj = self.boosting_manager.get_source_object(TESTS_DATA_DIR)
        self.assertTrue(dir_obj.ready, "Not Ready")

        d = self.check_torrents(TESTS_DATA_DIR, target=2)
        d.addCallback(lambda _: True)
        return d

    @deferred(timeout=10)
    def test_dir_archive_example(self):
        """
        test archive mode. Use diretory because easier to fetch torrent
        """
        self.boosting_manager.add_source(TESTS_DATA_DIR)
        self.boosting_manager.set_archive(TESTS_DATA_DIR, True)

        dir_obj = self.boosting_manager.get_source_object(TESTS_DATA_DIR)
        self.assertTrue(dir_obj.ready, "Not Ready")

        def check_archive(_):
            """
            function to check whether two of the torrents is in archive mode (with preload)
            """
            for infohash in list(self.boosting_manager.torrents):
                torrent = self.boosting_manager.torrents[infohash]
                self.assertIsNotNone(torrent.get('preload'))

        d = self.check_torrents(TESTS_DATA_DIR, target=2)
        d.addCallback(check_archive)
        return d


@skip("Disabled credit mining tests until they are stable again")
class TestBoostingManagerSysChannel(TestBoostingManagerSys):
    """
    testing class for channel source
    """

    def __init__(self, *argv, **kwargs):
        super(TestBoostingManagerSysChannel, self).__init__(*argv, **kwargs)
        self.tdef = TorrentDef.load(TORRENT_FILE)
        self.channel_id = 0
        self.expected_votecast_cid = None
        self.expected_votecast_vote = None

    def setUp(self, autoload_discovery=True):
        super(TestBoostingManagerSysChannel, self).setUp()
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"

    def insert_channel_in_db(self, dispersy_cid, peer_id, name, description):
        return self.channel_db_handler.on_channel_from_dispersy(dispersy_cid, peer_id, name, description)

    def insert_torrents_into_channel(self, torrent_list):
        self.channel_db_handler.on_torrents_from_dispersy(torrent_list)

    def on_dispersy_create_votecast(self, cid, vote, _):
        """
        Check whether we have the expected parameters when this method is called.
        """
        self.assertEqual(cid, self.expected_votecast_cid)
        self.assertEqual(vote, self.expected_votecast_vote)
        self.create_votecast_called = True

    @blocking_call_on_reactor_thread
    def create_fake_allchannel_community(self):
        """
        This method creates a fake AllChannel community so we can check whether a request is made in the community
        when doing stuff with a channel.
        """
        self.session.lm.dispersy._database.open()
        fake_member = DummyMember(self.session.lm.dispersy, 1, "a" * 20)
        member = self.session.lm.dispersy.get_new_member(u"curve25519")
        fake_community = AllChannelCommunity(self.session.lm.dispersy, fake_member, member)
        fake_community.disp_create_votecast = self.on_dispersy_create_votecast
        self.session.lm.dispersy._communities = {"allchannel": fake_community}

    def set_boosting_settings(self):
        super(TestBoostingManagerSysChannel, self).set_boosting_settings()
        self.bsettings.swarm_interval = 1
        self.bsettings.initial_swarm_interval = 1
        self.bsettings.max_torrents_active = 1
        self.bsettings.max_torrents_per_source = 1

    def setUpPreSession(self):
        super(TestBoostingManagerSysChannel, self).setUpPreSession()

        # we use dummy dispersy here
        self.config.set_dispersy(False)

    @blocking_call_on_reactor_thread
    def create_torrents_in_channel(self, dispersy_cid_hex):
        """
        Helper function to insert 10 torrent into designated channel
        """
        for i in xrange(0, 10):
            self.insert_channel_in_db('rand%d' % i, 42 + i, 'Test channel %d' % i, 'Test description %d' % i)

        self.channel_id = self.insert_channel_in_db(dispersy_cid_hex.decode('hex'), 42,
                                                    'Simple Channel', 'Channel description')

        torrent_list = [[self.channel_id, 1, 1, TORRENT_FILE_INFOHASH, 1460000000, TORRENT_FILE,
                         self.tdef.get_files_as_unicode_with_length(), self.tdef.get_trackers_as_single_tuple()]]

        self.insert_torrents_into_channel(torrent_list)

    @deferred(timeout=20)
    def test_chn_lookup(self):
        """
        testing channel source.

        It includes finding and downloading actual torrent
        """
        self.session.get_dispersy = lambda: True
        self.session.lm.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        dispersy_cid_hex = "abcd" * 9 + "0012"
        dispersy_cid = binascii.unhexlify(dispersy_cid_hex)

        # create channel and insert torrent
        self.create_fake_allchannel_community()
        self.create_torrents_in_channel(dispersy_cid_hex)

        self.boosting_manager.add_source(dispersy_cid)
        chn_obj = self.boosting_manager.get_source_object(dispersy_cid)

        def _load(torrent, callback=None):
            if not isinstance(torrent, CollectedTorrent):
                torrent_id = 0
                if torrent.torrent_id <= 0:
                    torrent_id = self.session.lm.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

                torrent = CollectedTorrent(torrent, self.tdef)
            if callback is not None:
                callback(torrent)
            else:
                return torrent

        def check_torrents_channel(src, defer_param=None, target=1):
            """
            check if a torrent already in channel and ready to download
            """
            if defer_param is None:
                defer_param = defer.Deferred()

            src_obj = self.boosting_manager.get_source_object(src)
            success = True
            if not src_obj or len(src_obj.torrents) < target:
                success = False
                reactor.callLater(1, check_torrents_channel, src, defer_param, target=target)
            elif not self.boosting_manager.torrents.get(TORRENT_FILE_INFOHASH, None):
                success = False
                reactor.callLater(1, check_torrents_channel, src, defer_param, target=target)
            elif not self.boosting_manager.torrents[TORRENT_FILE_INFOHASH].get('download', None):
                success = False
                reactor.callLater(1, check_torrents_channel, src, defer_param, target=target)

            if success:
                self.boosting_manager.set_enable_mining(src, False, force_restart=True)
                if src_obj.community:
                    src_obj.community.cancel_all_pending_tasks()

                defer_param.callback(src)

            return defer_param

        chn_obj.torrent_mgr.load_torrent = _load

        d = self.check_source(dispersy_cid)
        d.addCallback(check_torrents_channel, target=1)
        return d

    @deferred(timeout=20)
    def test_chn_exist_lookup(self):
        """
        testing existing channel as a source.

        It also tests how boosting manager cope with unknown channel with retrying
        the lookup
        """
        self.session.get_dispersy = lambda: True
        self.session.lm.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        dispersy_cid_hex = "abcd" * 9 + "0012"
        dispersy_cid = binascii.unhexlify(dispersy_cid_hex)

        # create channel and insert torrent
        self.create_fake_allchannel_community()
        self.create_torrents_in_channel(dispersy_cid_hex)

        # channel is exist
        community = ChannelCommunity.init_community(self.session.lm.dispersy,
                                                    self.session.lm.dispersy.get_member(mid=dispersy_cid),
                                                    self.session.lm.dispersy._communities['allchannel']._my_member,
                                                    self.session)

        # make the id unknown so boosting manager can test repeating search
        id_tmp = community._channel_id
        community._channel_id = 0

        def _set_id_channel(channel_id):
            """
            set channel id manually (emulate finding)
            """
            community._channel_id = channel_id

        reactor.callLater(5, _set_id_channel, id_tmp)

        self.boosting_manager.add_source(dispersy_cid)
        chn_obj = self.boosting_manager.get_source_object(dispersy_cid)

        def _load(torrent, callback=None):
            if not isinstance(torrent, CollectedTorrent):
                torrent_id = 0
                if torrent.torrent_id <= 0:
                    torrent_id = self.session.lm.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

                torrent = CollectedTorrent(torrent, self.tdef)
            if callback is not None:
                callback(torrent)
            else:
                return torrent

        chn_obj.torrent_mgr.load_torrent = _load

        def clean_community(_):
            """
            cleanly exit the community we are in
            """
            if chn_obj.community:
                chn_obj.community.cancel_all_pending_tasks()

            chn_obj.kill_tasks()


        d = self.check_source(dispersy_cid)
        d.addCallback(clean_community)
        return d

    @deferred(timeout=20)
    def test_chn_max_torrents(self):
        """
        Test the restriction of max_torrents in a source.
        """
        self.session.get_dispersy = lambda: True
        self.session.lm.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        dispersy_cid_hex = "abcd" * 9 + "0012"
        dispersy_cid = binascii.unhexlify(dispersy_cid_hex)

        # create channel and insert torrent
        self.create_fake_allchannel_community()
        self.create_torrents_in_channel(dispersy_cid_hex)

        pioneer_file = os.path.join(TESTS_DATA_DIR, "Pioneer.One.S01E06.720p.x264-VODO.torrent")
        pioneer_tdef = TorrentDef.load(pioneer_file)
        pioneer_ihash = binascii.unhexlify("66ED7F30E3B30FA647ABAA19A36E7503AA071535")

        torrent_list = [[self.channel_id, 1, 1, pioneer_ihash, 1460000001, pioneer_file,
                         pioneer_tdef.get_files_as_unicode_with_length(), pioneer_tdef.get_trackers_as_single_tuple()]]
        self.insert_torrents_into_channel(torrent_list)

        self.boosting_manager.add_source(dispersy_cid)
        chn_obj = self.boosting_manager.get_source_object(dispersy_cid)
        chn_obj.max_torrents = 2
        chn_obj.torrent_mgr.load_torrent = lambda dummy_1, dummy_2: None

        def _load(torrent, callback=None):
            if not isinstance(torrent, CollectedTorrent):
                torrent_id = 0
                if torrent.torrent_id <= 0:
                    torrent_id = self.session.lm.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

                infohash_str = binascii.hexlify(torrent.infohash)
                torrent = CollectedTorrent(torrent, self.tdef if infohash_str.startswith("fc") else pioneer_tdef)
            if callback is not None:
                callback(torrent)
            else:
                return torrent

        def activate_mgr():
            """
            activate ltmgr and adjust max torrents to emulate overflow torrents
            """
            chn_obj.max_torrents = 1
            chn_obj.torrent_mgr.load_torrent = _load

        reactor.callLater(5, activate_mgr)

        def check_torrents_channel(src, defer_param=None):
            """
            check if a torrent already in channel and ready to download
            """
            if defer_param is None:
                defer_param = defer.Deferred()

            src_obj = self.boosting_manager.get_source_object(src)
            success = True
            if len(src_obj.unavail_torrent) == 0:
                self.assertLessEqual(len(src_obj.torrents), src_obj.max_torrents)
            else:
                success = False
                reactor.callLater(1, check_torrents_channel, src, defer_param)

            if success:
                src_obj.community.cancel_all_pending_tasks()
                src_obj.kill_tasks()
                defer_param.callback(src)

            return defer_param

        d = self.check_source(dispersy_cid)
        d.addCallback(check_torrents_channel)
        return d

    def tearDown(self):
        self.session.lm.dispersy._communities['allchannel'].cancel_all_pending_tasks()
        self.session.lm.dispersy.cancel_all_pending_tasks()
        self.session.lm.dispersy = None
        super(TestBoostingManagerSysChannel, self).tearDown()
