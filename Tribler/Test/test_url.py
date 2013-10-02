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
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

from Tribler.Core.API import *

DEBUG = False

class TestP2PURLs(AbstractServer):
    """
    Testing P2P URLs version 0
    """

    def test_url_syntax(self):
        """
        URL syntax parsing
        tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvcNAQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=15&a=RSA&b=AAIAAA
        tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg
        """
        badurllist = []

        badurllist += [("ribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "wrong scheme")]
        badurllist += [("tribe//127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "no colon after scheme")]
        # badurllist += [("tribe://127.1.0.10:6969/announce?trai ler.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "space not escaped")] # too strict
        # badurllist += [("tribe://localhost;10/?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "bad port spec")] # too strict
        badurllist += [("tribe://localhost:https/?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "port not int")]
        badurllist += [("tribe://localhost/trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "not query")]
        if sys.platform != "win32":
            badurllist += [("tribe://localhost?tr\xfeiler.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "char in name not URL escaped")]
        badurllist += [("tribe://localhost?Sjaak&", "query with empty key=value")]
        badurllist += [("tribe://localhost?trailer.mkv&r:TTgcifG0Ot7STCY2JL8SUOxROFo&l:AKK35A&s=15&b:AAFnGg", "key value not separated by =")]
        badurllist += [("tribe://localhost?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b:AAFnGg", "some key value not separated by =")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=", "query with malformed key value")]

        # IPv6 addresses
        badurllist += [("tribe://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "unclosed IPv6 literal address")]
        badurllist += [("tribe://FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "unopened IPv6 literal address")]
        badurllist += [("tribe://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "unclosed IPv6 literal address, no port")]
        badurllist += [("tribe://FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "unopened IPv6 literal address, no port")]

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
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15", "query with missing bitrate")]

        # live
        badurllist += [("tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvcNAQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=15&b=AAIAAA", "query with missing live auth method")]

        self.run_badurllist(badurllist)

    def test_encoding(self):
        badurllist = []
        badurllist += [("tribe://localhost?Sjaak&r=\xd3]\xb7\xe3\x9e\xbb\xf3\xdd5\xdb~9\xeb\xbf=\xd3]\xb7\xe3\x9e&l=AKK35A&s=15&b=AAFnGg", "query with non-BASE64URL encoded root hash")]
        badurllist += [("tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7ST!Y2JL8SUOxROFo&l=AKK35A&s=15&b=AAFnGg", "query with invalid BASE64URL encoded root hash, contains !")]
        badurllist += [("tribe://127.1.0.10:6969/announce?trailer.mkv&r=TTgcifG0Ot7STCY2JL8SUOxROFo=&l=AKK35A&s=15&b=AAFnGg", "query with invalid BASE64URL encoded root hash, contains = padding")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=1234&s=15&b=AAFnGg", "query with non-encoded length")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=1234&b=AAFnGg", "query with non-encoded piece size")]
        badurllist += [("tribe://localhost?Sjaak&r=TTgcifG0Ot7STCY2JL8SUOxROFo&l=AKK35A&s=15&b=1234", "query with non-encoded bitrate")]

        # live
        badurllist += [("tribe://127.2.3.42:7764/announce?SjaakCam.mpegts&k=MHowDQYJKoZIhvc!AQEBBQADaQAwZgJhAN0Khlp5ZhWC7VfLynCkKts71b8h8tZXH87PkDtJUTJaX_SS1Cddxkv63PRmKOvtAHhkTLSsWOZbSeHkOlPIq_FGg2aDLDJ05g3lQ-8mSmo05ff4SLqNUTShWO2CR2TPhQIBAw&l=HCAAAA&s=15&a=RSA&b=AAIAAA", "query with invalid BASE64URL encoded live public key, contains !")]

        self.run_badurllist(badurllist)

    def run_badurllist(self, badurllist):
        for url, problem in badurllist:
            try:
                tdef = TorrentDef.load_from_url(url)
                self.assert_(False, 'Should not have accepted URL: "%s", %s ' % (url, problem))
            except AssertionError, e:
                raise e
            except:
                logger.debug("", exc_info=True)

    def test_create_vod(self):
        paramlist = []
        paramlist += [('Sjaak', 134349, 2 ** 15, "4:01")]
        paramlist += [('Sjaak', 1343490, 2 ** 15, "1:04:01")]  # long duration
        paramlist += [('Sjaak Harry', 134349, 2 ** 15, "4:01")]  # space in name
        paramlist += [(u'Serg\u00e9Harr\u014c', 134349, 2 ** 15, "4:01")]  # Unicode name
        paramlist += [(u'\u4f60\u597d', 134349, 2 ** 15, "4:01")]  # Unicode name, Ni Hao ;o)

        self.run_paramlist_vod(paramlist, "http://127.0.0.1/announce")
        # self.run_paramlist_vod(paramlist,"http://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]/announce")

    def run_paramlist_vod(self, paramlist, tracker):
        tmpdirname = self.getStateDir()

        for name, leng, piecesize, duration in paramlist:
            # Niels: creating utf8 torrents seems to cause problems when removing them on windows?
            tmpfilename = os.path.join(tmpdirname, name)

            content = '*' * leng
            f = open(tmpfilename, "wb")
            f.write(content)
            f.close()

            tdef = TorrentDef()
            tdef.add_content(tmpfilename, playtime=duration)
            tdef.set_tracker(tracker)
            tdef.set_piece_length(piecesize)
            tdef.set_create_merkle_torrent(True)
            # Arno, 2009-10-02: Explicitly set encoding to UTF-8. Default on
            # Win32 is 'mbcs'. Python cannot properly encode this,
            # u'\u4f60\u597d.ts' becomes '??.ts' (literally, ? = char(63))
            #
            tdef.set_encoding('UTF-8')
            tdef.set_url_compat(True)
            tdef.finalize()
            logger.debug("URL %s", tdef.get_url())

            tdef2 = TorrentDef.load_from_url(tdef.get_url())

            if isinstance(name, unicode):
                utf8name = name.encode("UTF-8")
            else:
                utf8name = name

            # logger.debug("ORIG NAME %s", `utf8name`)
            # logger.debug("TDEF NAME %s", `tdef2.get_name()`)

            self.assertEqual(tdef2.get_name(), utf8name)
            self.assertEqual(tdef2.get_length(), leng)
            self.assertEqual(tdef2.get_piece_length(), piecesize)
            tbitrate = tdef2.get_bitrate()
            s = dur2s(duration)
            ebitrate = leng / s
            self.assertEqual(tbitrate, ebitrate)

# TODO: Remove this and use the utility function instead.
def dur2s(dur):
    """ [hh]mm:ss -> seconds """
    elems = dur.split(":")
    s = 0
    for i in range(0, len(elems)):
        num = int(elems[i])
        t = num * int(pow(60.0, len(elems) - i - 1))
        s += t
    return s
