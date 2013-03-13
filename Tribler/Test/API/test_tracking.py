# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import urllib
#from urllib2 import urlopen # urllib blocks on reading, HTTP/1.1 persist conn problem?
from traceback import print_exc
import urlparse

from Tribler.Core.BitTornado.zurllib import urlopen
from Tribler.Core.simpledefs import STATEDIR_ITRACKER_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.btconn import BTConnection
from Tribler.Core.MessageID import *

from Tribler.Core.API import *

DEBUG=True

class TestTracking(TestAsServer):
    """
    Testing seeding via new tribler API:
    """

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        self.config.set_megacache(False)
        self.config.set_internal_tracker(True)


    def test_all(self):
        self.subtest_add_remove_torrent()
        self.subtest_tlookup1()
        self.subtest_tlookup2()


    def subtest_add_remove_torrent(self):
        tdef = TorrentDef()
        sourcefn = os.path.join(os.getcwd(),"file.wmv")
        tdef.add_content(sourcefn)
        tdef.set_tracker(self.session.get_internal_tracker_url())
        tdef.finalize()

        torrentfn = os.path.join(self.session.get_state_dir(),"gen.torrent")
        tdef.save(torrentfn)
        infohash = tdef.get_infohash()
        hexinfohash = binascii.hexlify(infohash)

        self.session.add_to_internal_tracker(tdef)
        time.sleep(1)
        self.check_http_presence(hexinfohash,True)

        self.session.remove_from_internal_tracker(tdef)
        print >> sys.stderr,"test: Give network thread running tracker time to detect we removed the torrent file"
        time.sleep(2)

        self.check_http_presence(hexinfohash,False)
        self.check_disk_presence(hexinfohash,False)

    def check_http_presence(self,hexinfohash,present):
        print >> sys.stderr,"test: infohash is",hexinfohash
        url = 'http://127.0.0.1:'+str(self.session.get_listen_port())+'/'
        print >> sys.stderr,"test: tracker lives at",url
        f = urlopen(url)
        data = f.read()
        f.close()

        # WARNING: this test depends on the output of the tracker. If that
        # is changed, also change this.
        print >> sys.stderr,"test: tracker returned:",data
        if present:
            self.assert_(data.find(hexinfohash) != -1)
        else:
            self.assert_(data.find(hexinfohash) == -1)

    def check_disk_presence(self,hexinfohash,present):
        itrackerdir = os.path.join(self.session.get_state_dir(),STATEDIR_ITRACKER_DIR)
        for filename in os.listdir(itrackerdir):
            if filename.startswith(hexinfohash):
                if present:
                    self.assert_(True)
                else:
                    self.assert_(False)


    #
    # /tlookup?url
    #
    def subtest_tlookup1(self):
        httpseeds = []
        httpseeds.append('http://www.example.com/file.wmv')
        self._test_tlookup(httpseeds)

    def subtest_tlookup2(self):
        httpseeds = []
        httpseeds.append('http://www.example.com/file.wmv')
        httpseeds.append('http://icecast.freezer.com/file.wmv')
        self._test_tlookup(httpseeds)


    def _test_tlookup(self,httpseedlist):
        t = TorrentDef()
        fn = os.path.join(os.getcwd(),"file.wmv")
        t.add_content(fn)
        t.set_tracker(self.session.get_internal_tracker_url())
        t.set_urllist(httpseedlist)
        t.finalize()
        wantdata = bencode(t.get_metainfo())

        self.session.add_to_internal_tracker(t)
        #time.sleep(30)

        (scheme, netloc, path, pars, query, fragment) = urlparse.urlparse(self.session.get_internal_tracker_url())
        urlprefix = scheme+'://'+netloc+'/tlookup?'
        for httpseed in httpseedlist:
            quoted = urllib.quote(httpseed)
            url = urlprefix+quoted
            #url = "http://www.cs.vu.nl/~arno/index.html"
            print >>sys.stderr,"test: Asking tracker for",url
            # F*ing BitTornado/Python crap: using normal urlopen here results in
            # an infinitely hanging read (even if read(1024))
            conn = urlopen(url)
            gotdata = conn.read()
            print >>sys.stderr,"test: Tracker sent",len(gotdata)
            conn.close()
            self.assertEquals(wantdata,gotdata)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTracking))

    return suite

if __name__ == "__main__":
    unittest.main()
