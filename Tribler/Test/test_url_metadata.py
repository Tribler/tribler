# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import socket
from traceback import print_exc

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import P2PURL_SCHEME,NTFY_TORRENTS,URL_MIME_TYPE
from Tribler.Core.MessageID import getMessageName,GET_METADATA,METADATA
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.CacheDB.CacheDBHandler import TorrentDBHandler

# TODO: use reimplementations
from Tribler.Core.APIImplementation.makeurl import p2purl_decode_base64url,p2purl_decode_nnumber,p2purl_decode_piecelength 


DEBUG=True

class TestURLMetadata(TestAsServer):
    """ 
    Testing download helping
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving MyLaunchMany time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: MyLaunchMany should have started up"

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        
    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der()) 

        # Create URL compat torrents and save in Torrent database.
        self.tdef1 = TorrentDef.load_from_url(P2PURL_SCHEME+'://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvcNAQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=15&a=RSA&b=AAIAAA')
        self.torrentfn1 = os.path.join(self.session.get_torrent_collecting_dir(),"live.torrent")
        self.tdef1.save(self.torrentfn1)

        self.tdef2 = TorrentDef.load_from_url(P2PURL_SCHEME+'://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg')
        self.torrentfn2 = os.path.join(self.session.get_torrent_collecting_dir(),"vod.torrent")
        self.tdef2.save(self.torrentfn2)

        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        extra_info = {'status':'good', 'filename':self.torrentfn1}
        self.torrent_db.addExternalTorrent(self.tdef1, source='',extra_info=extra_info)
        extra_info = {'status':'good', 'filename':self.torrentfn2}
        self.torrent_db.addExternalTorrent(self.tdef2, source='',extra_info=extra_info)
         
        
    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)

    #
    # Good GET_METADATA for url-compat torrent
    #
    def test_good_get_metadata_url(self):

        # 1. Establish overlay connection to Tribler
        s = OLConnection(self.my_keypair,'localhost',self.hisport)

        for tdef in [self.tdef1,self.tdef2]:
            msg = self.create_good_get_metadata(tdef.get_infohash())
            s.send(msg)
        
            try:
                s.b.s.settimeout(10.0)
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: Got reply",getMessageName(resp[0])
                self.assert_(resp[0] == METADATA)
                self.check_metadata(resp[1:],tdef)

            except socket.timeout:
                print >> sys.stderr,"test: Timeout, bad, peer didn't reply with METADATA message"
                self.assert_(False)

        s.close()

    def create_good_get_metadata(self,infohash):
        bd = bencode(infohash)
        return GET_METADATA+bd

    def check_metadata(self,bdata,tdef):
        data = bdecode(bdata)
        # selversion >= OLPROTO_VER_ELEVENTH:
        for key in ['torrent_hash','metatype','metadata','last_check_time','status','leecher','seeder']:
            self.assert_(key in data)
            
        self.assertEqual(data['metatype'],URL_MIME_TYPE)
        self.assertEqual(data['torrent_hash'],tdef.get_infohash())
            
        url = data['metadata']
        cidx = url.find(':')
        self.assert_(cidx != -1)
        scheme = url[0:cidx]
        if url[cidx+1] == '/':
            # hierarchical URL
            qidx = url.find('?')
            self.assert_(qidx != -1)
            tracker = "http"+url[cidx:qidx]
        else:
            # Not yet supported by TorrentDef
            tracker = None 
            qidx = cidx+1
            
        query = url[qidx+1:]
        kvs = query.split('&')
        pt = {}
        for kv in kvs:
            if not '=' in kv:
                k = 'n'
                v = kv
            else:
                (k,v) = kv.split('=')
                if k == 'l': #length
                    v = p2purl_decode_nnumber(v)
                elif k == 's': # piece size
                    v = p2purl_decode_piecelength(v)
                elif k == 'r': # root hash
                    v = p2purl_decode_base64url(v)
                elif k == 'k': # live key
                    v = p2purl_decode_base64url(v)
                elif k == 'a': # live auth method
                    pass
                elif k == 'b': # bitrate
                    v = p2purl_decode_nnumber(v)
            pt[k] = v
            
        # Compare:
        self.assertEqual(P2PURL_SCHEME,scheme)
        self.assertEqual(tdef.get_tracker(),tracker)
        self.assertEqual(tdef.get_name(),pt['n'])
        self.assertEqual(tdef.get_length(),pt['l'])
        self.assertEqual(tdef.get_piece_length(),pt['s'])
        if 'r' in pt:
            self.assertEqual(tdef.get_infohash(),pt['r'])
        else:
            self.assertEqual(tdef.get_live_pubkey(),pt['k'])
            self.assertEqual(tdef.get_live_authmethod(),pt['a'])
        self.assertEqual(tdef.get_bitrate(),pt['b'])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestURLMetadata))
    
    return suite

if __name__ == "__main__":
    unittest.main()
