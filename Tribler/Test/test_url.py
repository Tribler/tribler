# Written by Arno Bakker
# see LICENSE.txt for license information
#
# * URL 2 TorrentDef
# 
#  - missing fields
#  - malformed fields
#    - bad syntax
#    - bad length
#
# * TorrentDef 2 URL
#  - Creates right URL from params
#
# Move to API dir?
#

import unittest
import sys
import os
import tempfile
import shutil
from traceback import print_exc

from Tribler.Core.API import *


DEBUG=False

class TestP2PURLs(unittest.TestCase):
    """ 
    Testing P2P URLs version 0    
    """
    
    def setUp(self):
        pass
        
    def tearDown(self):
        pass

    def test_url_syntax(self):
        """
        tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvcNAQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=gAA&a=RSA&b=AAIAAA
        tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg
        """

        badurllist = []
        badurllist += [("ribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "wrong scheme")]
        badurllist += [("tribe//127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "no colon after scheme")] 
        #badurllist += [("tribe://127.1.0.10:6969/announce?trai ler.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "space not escaped")] # too strict
        #badurllist += [("tribe://localhost;10/?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "bad port spec")] # too strict
        badurllist += [("tribe://localhost:https/?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "port not int")]
        badurllist += [("tribe://localhost/trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "not query")]
        badurllist += [("tribe://localhost?tr\xfeiler.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "char in name not URL escaped")]
        badurllist += [("tribe://localhost?Sjaak&", "query with empty key=value")]
        badurllist += [("tribe://localhost?trailer.mkv&r:TTgcifG0Ot7STCY2JL8SUOxROFo&l:AKK35A&s=gAA&b:AAFnGg", "key value not separated by =")]
        badurllist += [("tribe://localhost?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b:AAFnGg", "some key value not separated by =")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=", "query with malformed key value")]

        self.run_badurllist(badurllist)


    def test_missing(self):
        badurllist = []
        badurllist += [("tribe:/", "missing all fields")]
        badurllist += [("tribe://", "missing authority")]
        badurllist += [("tribe://localhost", "missing query fields")]
        badurllist += [("tribe://localhost?", "empty query")]
        badurllist += [("tribe://localhost?Sjaak", "query just name")]
        badurllist += [("tribe://localhost?n=Sjaak", "query just name")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo", "query with just valid root hash")] 
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A", "query with missing piece size+bitrate")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA", "query with missing bitrate")]

        # live
        badurllist += [("tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvcNAQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=gAA&b=AAIAAA", "query with missing live auth method")]

        
        self.run_badurllist(badurllist)

    def test_encoding(self):
        badurllist = []
        badurllist += [("tribe://localhost?Sjaak&r=\xd3]\xb7\xe3\x9e\xbb\xf3\xdd5\xdb~9\xeb\xbf=\xd3]\xb7\xe3\x9e&l=AKK35A&s=gAA&b=AAFnGg", "query with non-BASE64URL encoded root hash")]
        badurllist += [("tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7ST!Y2JL8SUOxROFo&l=AKK35A&s=gAA&b=AAFnGg", "query with invalid BASE64URL encoded root hash, contains !")]
        badurllist += [("tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo=&l=AKK35A&s=gAA&b=AAFnGg", "query with invalid BASE64URL encoded root hash, contains = padding")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=1234&s=gAA&b=AAFnGg", "query with non-encoded length")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=1234&b=AAFnGg", "query with non-encoded piece size")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=gAA&b=1234", "query with non-encoded bitrate")]

        # live
        badurllist += [("tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvc!AQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=gAA&a=RSA&b=AAIAAA", "query with invalid BASE64URL encoded live public key, contains !")]
        
        self.run_badurllist(badurllist)


    def run_badurllist(self,badurllist):
        
        #print >>sys.stderr,badurllist
        
        for url,problem in badurllist:
            try:
                print >>sys.stderr,"\n\nTest",problem
                tdef = TorrentDef.load_from_url(url)
                self.assert_(False,"Should not have accepted URL: "+problem)
            except AssertionError,e:
                raise e
            except:
                print_exc()
                self.assert_(True)
        
        
    def test_create_vod(self):
        
        paramlist = []
        paramlist += [('Sjaak',134349,2 ** 15, "4:01")]
        paramlist += [('Sjaak',1343490,2 ** 15, "1:04:01")] # long duration
        paramlist += [('Sjaak Harry',134349,2 ** 15, "4:01")] # space in name
        paramlist += [(u'Serg\u00e9Harr\u014c',134349,2 ** 15, "4:01")] # Unicode name
        paramlist += [(u'\u4f60\u597d',134349,2 ** 15, "4:01")] # Unicode name, Ni Hao ;o)
        
        self.run_paramlist_vod(paramlist)
        
    def run_paramlist_vod(self,paramlist):
        tmpdirname = tempfile.mkdtemp()
        
        for name,leng,piecesize,duration in paramlist:
            
            
            print >>sys.stderr,"\n\nTest",`name`
            tmpfilename = os.path.join(tmpdirname,name)
            
            content = '*' * leng
            f = open(tmpfilename,"wb")
            f.write(content)
            f.close()
            
            tdef = TorrentDef()
            tdef.add_content(tmpfilename,playtime=duration)
            tdef.set_tracker("http://127.0.0.1/announce")
            tdef.set_piece_length(piecesize)
            tdef.set_create_merkle_torrent(True)
            tdef.set_url_compat(True)
            tdef.finalize()
            print >>sys.stderr,"URL",tdef.get_url()
            
            tdef2 = TorrentDef.load_from_url(tdef.get_url())
            
            if isinstance(name,unicode):
                utf8name = name.encode("UTF-8")
            else:
                utf8name = name
            self.assertEqual(tdef2.get_name(),utf8name)
            self.assertEqual(tdef2.get_length(),leng)
            self.assertEqual(tdef2.get_piece_length(),piecesize)
            tbitrate = tdef2.get_bitrate()
            s = dur2s(duration)
            ebitrate = leng/s
            self.assertEqual(tbitrate,ebitrate)
                        
        shutil.rmtree(tmpdirname)
        

    def test_create_live(self):
        
        paramlist = []
        #paramlist += [('Sjaak.ts',2 ** 15, 2 ** 16, "1:00:00", None)]
        paramlist += [('Sjaak.ts',2 ** 15, 2 ** 16, "1:00:00", RSALiveSourceAuthConfig())]
        paramlist += [('Sjaak.ts',2 ** 16, 2 ** 20, "1:00:00", RSALiveSourceAuthConfig())] # high bitrate
        paramlist += [('Sjaak.ts',2 ** 15, 2 ** 16, "0:15", RSALiveSourceAuthConfig())] # small duration = window
        paramlist += [('Sjaak.ts',2 ** 15, 2 ** 16, "1:00:00", ECDSALiveSourceAuthConfig())] # ECDSA auth
        paramlist += [('Sjaak Harry.ts',2 ** 15, 2 ** 16, "1:00:00", RSALiveSourceAuthConfig())] # space in name
        paramlist += [(u'Serg\u00e9Harr\u014c.ts',2 ** 15, 2 ** 16, "1:00:00", RSALiveSourceAuthConfig())] # Unicode name
        paramlist += [(u'\u4f60\u597d.ts',2 ** 15, 2 ** 16, "1:00:00", RSALiveSourceAuthConfig())] # Unicode name, Ni Hao ;o)
        
        self.run_paramlist_live(paramlist)


    def run_paramlist_live(self,paramlist):
        tmpdirname = tempfile.mkdtemp()
        
        for name,piecesize,bitrate,duration,authcfg in paramlist:
            
            print >>sys.stderr,"\n\nTest",`name`
            
            tdef = TorrentDef()
            tdef.create_live(name,bitrate,playtime=duration,authconfig=authcfg)
            tdef.set_tracker("http://127.0.0.1/announce")
            tdef.set_piece_length(piecesize)
            tdef.set_url_compat(True)
            tdef.finalize()
            print >>sys.stderr,"URL",tdef.get_url()
            
            tdef2 = TorrentDef.load_from_url(tdef.get_url())
            
            if isinstance(name,unicode):
                utf8name = name.encode("UTF-8")
            else:
                utf8name = name
            self.assertEqual(tdef2.get_name(),utf8name)
            
            leng = dur2s(duration) * bitrate
            self.assertEqual(tdef2.get_length(),leng)
            self.assertEqual(tdef2.get_piece_length(),piecesize)
            self.assertEqual(tdef2.get_bitrate(),bitrate)
            
            self.assertEquals(tdef2.get_live_pubkey(),authcfg.get_pubkey())
                        
        shutil.rmtree(tmpdirname)



def dur2s(dur):
    """ [hh]mm:ss -> seconds """
    elems = dur.split(":")
    s = 0
    for i in range(0,len(elems)):
        num = int(elems[i])
        t = num * int(pow(60.0,len(elems)-i-1))
        s += t
    return s


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestP2PURLs))
    
    return suite

if __name__ == "__main__":
    unittest.main()
