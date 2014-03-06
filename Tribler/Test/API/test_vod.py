# Written by Arno Bakker
# see LICENSE.txt for license information
from threading import currentThread
from unittest import skip

from Tribler.Core.API import *
from Tribler.Video.VideoServer import VideoServer
from Tribler.Test.test_as_server import TestAsServer


def state_callback(d, ds):
    print >> sys.stderr, "main: Stats", dlstatus_strings[ds.get_status()], ds.get_progress(), "%", ds.get_error()
    if ds.get_vod_prebuffering_progress() == 1.0:
        vod_ready_callback(d)

def vod_ready_callback(d):
    print >> sys.stderr, "main: VOD ready callback called", currentThread().getName(), "###########################################################"

    """
    f = open("video.avi","wb")
    while True:
        data = stream.read()
        print >>sys.stderr,"main: VOD ready callback: reading",type(data)
        print >>sys.stderr,"main: VOD ready callback: reading",len(data)
        if len(data) == 0:
            break
        f.write(data)
    f.close()
    stream.close()
    """

    videoserv = VideoServer.getInstance()
    # videoserv.set_inputstream('video/mpeg', params["stream"], None)


class TestVod(TestAsServer):

    def setUp(self):
        TestAsServer.setUp(self)

        self.port = 6789
        self.serv = VideoServer.getInstance(self.port, self.session)
        self.serv.start()

    def tearDown(self):
        self.serv.stop()
        VideoServer.delInstance()

        TestAsServer.tearDown(self)

    @skip("Broken")
    def test_vod(self):
        if sys.platform == 'win32':
            tdef = TorrentDef.load('bla.torrent')
        else:
            tdef = TorrentDef.load('/tmp/bla.torrent')

        # dcfg.set_saveas('/arno')
        dcfg = DownloadStartupConfig.get_copy_of_default()

        # dcfg.set_selected_files('MATRIX-XP_engl_L.avi') # play this video
        # dcfg.set_selected_files('field-trip-west-siberia.avi')
        d = self.session.start_download(tdef, dcfg)
        d.set_state_callback(state_callback, True)
        # d.set_max_upload(100)

        time.sleep(10)

        """
        d.stop()
        print "After stop"
        time.sleep(5)
        d.restart()
        """
        time.sleep(2500)
