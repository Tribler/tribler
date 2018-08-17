import os
from tempfile import mkstemp

from M2Crypto import Rand
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import VODFile
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings, UPLOAD, DOWNLOAD, DLMODE_VOD
from Tribler.Test.test_as_server import TestAsServer
from nose.twistedtools import deferred
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TestVideoOnDemand(TestAsServer):

    """
    Testing Merkle hashpiece messages for both:
    * Merkle BEP style
    * old Tribler <= 4.5.2 that did not use the Extention protocol (BEP 10).

    See BitTornado/BT1/Connecter.py
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield TestAsServer.setUp(self, autoload_discovery=autoload_discovery)
        self.content = None
        self.tdef = None
        self.test_deferred = Deferred()
        self.contentlen = None
        self.piecelen = 0

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent_enabled(True)

    def create_torrent(self):
        [srchandle, sourcefn] = mkstemp()
        self.content = Rand.rand_bytes(self.contentlen)
        os.write(srchandle, self.content)
        os.close(srchandle)

        self.tdef = TorrentDef()
        self.tdef.add_content(sourcefn)
        self.tdef.set_piece_length(self.piecelen)
        self.tdef.set_tracker("http://127.0.0.1:12/announce")
        self.tdef.finalize()

        torrentfn = os.path.join(self.session.config.get_state_dir(), "gen.torrent")
        self.tdef.save(torrentfn)

        dscfg = DownloadStartupConfig()
        destdir = os.path.dirname(sourcefn)
        dscfg.set_dest_dir(destdir)
        dscfg.set_mode(DLMODE_VOD)

        download = self.session.start_download_from_tdef(self.tdef, dscfg)
        download.set_state_callback(self.state_callback)

        self.session.set_download_states_callback(self.states_callback)

    def states_callback(self, dslist):
        ds = dslist[0]
        d = ds.get_download()
        self._logger.debug('%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s',
                           d.get_def().get_name(),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress() * 100,
                           ds.get_error(),
                           ds.get_current_speed(UPLOAD),
                           ds.get_current_speed(DOWNLOAD))

        return []

    def state_callback(self, ds):
        download = ds.get_download()
        if ds.get_vod_prebuffering_progress() == 1.0:

            self._logger.debug("Test: state_callback")

            stream = VODFile(open(download.get_content_dest(), 'rb'), download)

            # Read last piece
            lastpieceoff = ((self.contentlen - 1) / self.piecelen) * self.piecelen
            lastpiecesize = self.contentlen - lastpieceoff
            self._logger.debug("stream: lastpieceoff %s %s", lastpieceoff, lastpiecesize)
            self.stream_read(stream, lastpieceoff, lastpiecesize, self.piecelen)

            # Read second,3rd,4th byte, only
            secoff = 1
            secsize = 3
            blocksize = 3
            self.stream_read(stream, secoff, secsize, blocksize)

            # Read last byte
            lastoff = self.contentlen - 1
            lastsize = 1
            self.stream_read(stream, lastoff, lastsize, self.piecelen)

            self.test_deferred.callback(None)

            return 0
        return 1.0

    def stream_read(self, stream, off, size, blocksize):
        stream.seek(off)
        data = stream.read(blocksize)
        self._logger.debug("stream: Got data %s", len(data))
        self.assertEquals(len(data), size)
        self.assertEquals(data, self.content[off:off + size])

    @deferred(timeout=10)
    def test_99(self):
        self.contentlen = 99
        self.piecelen = 16
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        return self.test_deferred

    @deferred(timeout=10)
    def test_100(self):
        self.contentlen = 100
        self.piecelen = 16
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        return self.test_deferred

    @deferred(timeout=10)
    def test_101(self):
        self.contentlen = 101
        self.piecelen = 16
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        return self.test_deferred
