from pony import orm
from pony.orm import db_session
import os
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue, succeed
from twisted.internet.task import deferLater
from Tribler.Test.twisted_thread import reactor
import time

from Tribler.community.chant.testtools import LoadGspFromDisk
from Tribler.community.chant.MDPackXDR import REGULAR_TORRENT
from Tribler.community.chant.chant import *
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.chant.orm import start_orm, db
from Tribler.Core.simpledefs import NTFY_TORRENT, NTFY_FINISHED
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.pyipv8.ipv8.test.util import twisted_wrapper

class TestChant(TestAsServer):

    def setUpPreSession(self):
        super(TestChant, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_megacache_enabled(True)
        self.config.get

    def setUp(self):
        super(TestChant, self).setUp()
        self.testdir = self.session.config.get_state_dir()
        self.channels_dir = os.path.abspath(os.path.join(self.testdir, "channels"))
        db_filename = os.path.abspath(os.path.join(self.testdir, "chant.db"))
        start_orm(db_filename, create_db=True)

    def on_torrent_finished(self, subject, changetype, objectID, *args):
        chan_title, = args
        chan_dir = os.path.abspath(os.path.join(self.channels_dir, chan_title))
        process_channel_dir(chan_dir)
        self.dl_finished.callback(None)

    def DownloadChannel(self, channel):
        infohash = str(channel.infohash)
        title = channel.title
        self.session.add_observer(self.on_torrent_finished, NTFY_TORRENT, [NTFY_FINISHED], object_id=infohash)

        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.channels_dir)
        tdef = TorrentDefNoMetainfo(infohash=infohash, name=title)
        return self.session.start_download_from_tdef(tdef, dcfg)

    @twisted_wrapper(30)
    def TestDownload(self):
        self.dl_finished = Deferred()
        with db_session:
            chan = LoadGspFromDisk(os.path.abspath('./chant/channel.serialized'))
            download = self.DownloadChannel(chan)
            chanver = chan.version
        handle = yield download.get_handle()
        a = handle.connect_peer(('127.0.0.1',7000), 0x01)
        yield self.dl_finished
        
        with db_session:
            md_list = orm.select(g for g in MetadataGossip)[:]
            self.assertEqual(len(md_list), chanver+1)
        yield succeed(None)

