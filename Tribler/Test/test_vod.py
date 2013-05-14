# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: we download from Tribler
#

import os
import sys
import time
from tempfile import mkstemp
from M2Crypto import Rand

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Core.simpledefs import *
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig

# Tribler.Core.Video.PiecePickerStreaming.TEST_VOD_OVERRIDE = True

DEBUG = True

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
        self.vodstarted = False

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
        dscfg.set_video_event_callback(self.sesscb_vod_event_callback)

        self.session.set_download_states_callback(self.states_callback)
        self.session.start_download(self.tdef, dscfg)

    def states_callback(self, dslist):
        ds = dslist[0]
        d = ds.get_download()
    #    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
        print >> sys.stderr, '%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
                (d.get_def().get_name(), \
                dlstatus_strings[ds.get_status()], \
                ds.get_progress() * 100, \
                ds.get_error(), \
                ds.get_current_speed(UPLOAD), \
                ds.get_current_speed(DOWNLOAD))

        return (1.0, [])

    def sesscb_vod_event_callback(self, d, event, params):
        if self.vodstarted:
            return
        self.vodstarted = True

        print >> sys.stderr, "Test: vod_event_callback", event, params
        if event == VODEVENT_START:
            stream = params['stream']

            # Read last piece
            lastpieceoff = ((self.contentlen - 1) / self.piecelen) * self.piecelen
            lastpiecesize = self.contentlen - lastpieceoff
            print >> sys.stderr, "Test: stream: lastpieceoff", lastpieceoff, lastpiecesize
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

    def stream_read(self, stream, off, size, blocksize):
        stream.seek(off)
        data = stream.read(blocksize)
        print >> sys.stderr, "Test: stream: Got data", len(data)
        self.assertEquals(len(data), size)
        self.assertEquals(data, self.content[off:off + size])


    def test_99(self):
        self.contentlen = 99
        self.piecelen = 10
        self.create_torrent()

        print >> sys.stderr, "Test: Letting network thread create Download, sleeping"
        time.sleep(5)

        dlist = self.session.get_downloads()
        d = dlist[0]
        vs = d.get_vod_info()['status']

        if vs:
            goodrange = ((0, 0), (9, 8))
            self.assertEqual(vs.movie_range, goodrange)
            self.assertEqual(vs.first_piecelen, 10)
            self.assertEqual(vs.last_piecelen, 9)
            self.assertEqual(vs.first_piece, 0)
            self.assertEqual(vs.last_piece, 9)
            self.assertEqual(vs.movie_numpieces, 10)

    def test_100(self):
        self.contentlen = 100
        self.piecelen = 10
        self.create_torrent()

        print >> sys.stderr, "Test: Letting network thread create Download, sleeping"
        time.sleep(5)

        dlist = self.session.get_downloads()
        d = dlist[0]
        vs = d.get_vod_info()['status']

        if vs:
            goodrange = ((0, 0), (9, 9))
            self.assertEqual(vs.movie_range, goodrange)
            self.assertEqual(vs.first_piecelen, 10)
            self.assertEqual(vs.last_piecelen, 10)
            self.assertEqual(vs.first_piece, 0)
            self.assertEqual(vs.last_piece, 9)
            self.assertEqual(vs.movie_numpieces, 10)

    def test_101(self):
        self.contentlen = 101
        self.piecelen = 10
        self.create_torrent()

        print >> sys.stderr, "Test: Letting network thread create Download, sleeping"
        time.sleep(5)

        dlist = self.session.get_downloads()
        d = dlist[0]
        vs = d.get_vod_info()['status']

        if vs:
            goodrange = ((0, 0), (10, 0))
            self.assertEqual(vs.movie_range, goodrange)
            self.assertEqual(vs.first_piecelen, 10)
            self.assertEqual(vs.last_piecelen, 1)
            self.assertEqual(vs.first_piece, 0)
            self.assertEqual(vs.last_piece, 10)
            self.assertEqual(vs.movie_numpieces, 11)
