# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: we download from Tribler
#

import os
import sys
from tempfile import mkstemp
from M2Crypto import Rand
from threading import Event

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Core.simpledefs import dlstatus_strings, UPLOAD, DOWNLOAD, DLMODE_VOD
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import VODFile


class TestVideoOnDemand(TestAsServer):

    """
    Testing Merkle hashpiece messages for both:
    * Merkle BEP style
    * old Tribler <= 4.5.2 that did not use the Extention protocol (BEP 10).

    See BitTornado/BT1/Connecter.py
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent(True)

    def create_torrent(self):
        [srchandle, self.sourcefn] = mkstemp()
        self.content = Rand.rand_bytes(self.contentlen)
        os.write(srchandle, self.content)
        os.close(srchandle)

        self.tdef = TorrentDef()
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_piece_length(self.piecelen)
        self.tdef.set_tracker("http://127.0.0.1:12/announce")
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        self.tdef.save(self.torrentfn)

        dscfg = DownloadStartupConfig()
        destdir = os.path.dirname(self.sourcefn)
        dscfg.set_dest_dir(destdir)
        dscfg.set_mode(DLMODE_VOD)

        download = self.session.start_download(self.tdef, dscfg)
        download.set_state_callback(self.state_callback)

        self.session.set_download_states_callback(self.states_callback)

    def states_callback(self, dslist):
        ds = dslist[0]
        d = ds.get_download()
        self._logger.debug('%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s',
                           (d.get_def().get_name(),
                            dlstatus_strings[ds.get_status()],
                            ds.get_progress() * 100,
                            ds.get_error(),
                            ds.get_current_speed(UPLOAD),
                            ds.get_current_speed(DOWNLOAD)))

        return (1.0, [])

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

            self.event.set()

            return (0, False)
        return (1.0, False)

    def stream_read(self, stream, off, size, blocksize):
        stream.seek(off)
        data = stream.read(blocksize)
        self._logger.debug("stream: Got data %s", len(data))
        self.assertEquals(len(data), size)
        self.assertEquals(data, self.content[off:off + size])

    def test_99(self):
        self.event = Event()
        self.contentlen = 99
        self.piecelen = 10
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        assert self.event.wait(5)

    def test_100(self):
        self.event = Event()
        self.contentlen = 100
        self.piecelen = 10
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        assert self.event.wait(5)

    def test_101(self):
        self.event = Event()
        self.contentlen = 101
        self.piecelen = 10
        self.create_torrent()

        self._logger.debug("Letting network thread create Download, sleeping")
        assert self.event.wait(5)
