# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: we download from Tribler
#

import unittest
import os
import sys
import time
import socket
from binascii import b2a_hex
from sha import sha
from traceback import print_exc
from types import DictType, StringType, IntType, ListType
from M2Crypto import Rand

from Tribler.Test.test_as_server import TestAsServer
from btconn import BTConnection
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.Utilities.bitfield import Bitfield
from Tribler.Core.MessageID import REQUEST, UNCHOKE, HAVE, INTERESTED, \
    NOT_INTERESTED, EXTEND, BITFIELD, HASHPIECE, getMessageName
from Tribler.Core.Merkle.merkle import MerkleTree

DEBUG = True


def toint(s):
    return long(b2a_hex(s), 16)


def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) +
            chr((i >> 8) & 0xFF) + chr(i & 0xFF))


class TestMerkleMessage(TestAsServer):

    """
    Testing Merkle hashpiece messages for both:
    * Merkle BEP style
    * old Tribler <= 4.5.2 that did not use the Extention protocol (BEP 10).

    See BitTornado/BT1/Connecter.py
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >> sys.stderr, "test: Giving Session time to startup"
        time.sleep(5)
        print >> sys.stderr, "test: Session should have started up"

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        self.config.set_megacache(False)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        # Let Tribler start downloading an non-functioning torrent, so
        # we can talk to a normal download engine.
        self.tdef = TorrentDef()
        self.sourcefn = os.path.join(os.getcwd(), "API", "video2.wmv")
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_create_merkle_torrent(True)
        self.tdef.set_tracker("http://127.0.0.1:12/announce")
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        self.tdef.save(self.torrentfn)

        dscfg = self.setUpDownloadConfig()

        self.session.start_download(self.tdef, dscfg)

        self.infohash = self.tdef.get_infohash()
        self.mylistenport = 4810

        self.numpieces = (self.tdef.get_length() + self.tdef.get_piece_length() - 1) / self.tdef.get_piece_length()
        b = Bitfield(self.numpieces)
        for i in range(self.numpieces):
            b[i] = True
        self.assert_(b.complete())
        self.seederbitfieldstr = b.tostring()

        # piece_hashes = ['\x01\x02\x03\x04\x05\x06\x07\x08\x07\x06\x05\x04\x03\x02\x01\x00\x01\x02\x03\x04' ] * npieces
        # Construct Merkle tree
        tdef2 = TorrentDef()
        tdef2.add_content(self.sourcefn)
        tdef2.set_create_merkle_torrent(False)
        tdef2.set_tracker("http://127.0.0.1:12/announce")
        tdef2.set_piece_length(self.tdef.get_piece_length())
        tdef2.finalize()
        metainfo = tdef2.get_metainfo()

        piecesstr = metainfo['info']['pieces']
        print >> sys.stderr, "test: pieces has len", len(piecesstr)
        piece_hashes = []
        for i in range(0, len(piecesstr), 20):
            hash = piecesstr[i:i + 20]
            print >> sys.stderr, "test: piece", i / 20, "hash", repr(hash)
            piece_hashes.append(hash)

        print >> sys.stderr, "test: Putting", len(
            piece_hashes), "into MerkleTree, size", self.tdef.get_piece_length(), tdef2.get_piece_length()

        self.tree = MerkleTree(self.tdef.get_piece_length(), self.tdef.get_length(), None, piece_hashes)

        f = open(self.sourcefn, "rb")
        piece1 = f.read(2 ** 18)
        piece2 = f.read(2 ** 18)
        print >> sys.stderr, "read piece1", len(piece1)
        print >> sys.stderr, "read piece2", len(piece2)
        f.close()
        hash1 = sha(piece1).digest()
        hash2 = sha(piece2).digest()
        print >> sys.stderr, "hash piece1", repr(hash1)
        print >> sys.stderr, "hash piece2", repr(hash2)
        f2 = open("piece1.bin", "wb")
        f2.write(piece2)
        f2.close()

    def setUpDownloadConfig(self):
        dscfg = DownloadStartupConfig()
        print >> sys.stderr, "test: Downloading to", self.config_path
        dscfg.set_dest_dir(self.config_path)
        dscfg.set_breakup_seed_bitfield(False)

        return dscfg

    def tearDown(self):
        TestAsServer.tearDown(self)
        try:
            os.remove('piece1.bin')
        except:
            pass

    def singtest_good_hashpiece_bepstyle(self):
        self.subtest_good_hashpiece(False)

    def singtest_good_hashpiece_oldstyle(self):
        self.subtest_good_hashpiece(True)

    def singtest_good_request_bepstyle(self):
        # Let Session download file first
        self.subtest_good_hashpiece(False)
        # Now connect as different peer and download
        print >> sys.stderr, "\n\ntest: test_good_request: STARTING"
        self._test_good_request()

    def singtest_bad_hashpiece_bepstyle(self):
        self.subtest_bad_hashpiece(False)

    def singtest_bad_hashpiece_oldstyle(self):
        self.subtest_bad_hashpiece(True)

    #
    # Good hashpiece message
    #
    def subtest_good_hashpiece(self, oldstyle):
        print >> sys.stderr, "test: Testing good hashpiece, oldstyle", oldstyle
        if oldstyle:
            self._test_good(self.create_good_hashpiece, oldstyle,
                            self.create_good_tribler_extend_hs, infohash=self.infohash)
        else:
            options = '\x00\x00\x00\x00\x00\x10\x00\x00'
            self._test_good(self.create_good_hashpiece, oldstyle,
                            self.create_good_nontribler_extend_hs, options=options, infohash=self.infohash)

    def _test_good(self, msg_gen_func, oldstyle, extend_hs_gen_func, options=None, infohash=None):
        if options is None and infohash is None:
            s = BTConnection('localhost', self.hisport)
        elif options is None:
            s = BTConnection('localhost', self.hisport, user_infohash=infohash)
        elif infohash is None:
            s = BTConnection('localhost', self.hisport, user_option_pattern=options)
        else:
            s = BTConnection('localhost', self.hisport, user_option_pattern=options, user_infohash=infohash)
        print >> sys.stderr, "test: test_good: Create EXTEND HS"
        msg = extend_hs_gen_func()
        print >> sys.stderr, "test: test_good: Sending EXTEND HS", repr(msg)
        s.send(msg)
        print >> sys.stderr, "test: test_good: Waiting for BT HS"
        s.read_handshake_medium_rare()

        # Tribler should send an EXTEND message back
        try:
            print >> sys.stderr, "test: Waiting for reply"
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >> sys.stderr, "test: Got reply", getMessageName(resp[0])
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])

            # 1. Pretend we're seeder: send BITFIELD and UNCHOKE
            msg = BITFIELD + self.seederbitfieldstr
            s.send(msg)
            msg = UNCHOKE
            s.send(msg)
            print >> sys.stderr, "test: Pretend we are seeder"
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >> sys.stderr, "test: Got reply2", getMessageName(resp[0])
                self.assert_(resp[0] == REQUEST or resp[0] == INTERESTED or resp[
                             0] == UNCHOKE or resp[0] == HAVE or resp[0] == NOT_INTERESTED)
                if resp[0] == REQUEST:
                    chunkid = self.check_request(resp)

                    # 2. Reply to REQUEST with HASHPIECE (oldstyle) or Tr_hashpiece
                    msg = msg_gen_func(oldstyle, chunkid)
                    s.send(msg)
                elif resp[0] == NOT_INTERESTED:
                    break

            # s.close()
        except socket.timeout:
            print >> sys.stderr, "test: Timeout, bad, peer didn't reply in time"
            self.assert_(False)

        destfn = os.path.join(self.config_path, "video2.wmv")
        sf = open(self.sourcefn, "rb")
        df = open(destfn, "rb")
        n = self.tdef.get_piece_length()
        while True:
            sdata = sf.read(n)
            if len(sdata) == 0:
                break
            ddata = df.read(n)
            self.assert_(sdata == ddata)

        time.sleep(3)
        s.close()

    def create_good_nontribler_extend_hs(self):
        """ Merkle BEP style """
        d = {}
        d['m'] = {'Tr_hashpiece': 250}
        d['p'] = self.mylistenport
        d['v'] = 'TestSweet 1.2.3.4'
        bd = bencode(d)
        return EXTEND + chr(0) + bd

    def create_good_tribler_extend_hs(self):
        """ old Tribler style """
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM': 253}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 3.5.1'
        bd = bencode(d)
        return EXTEND + chr(0) + bd

    def check_tribler_extend_hs(self, data):
        self.assert_(data[0] == chr(0))
        d = bdecode(data[1:])
        self.assert_(isinstance(d, DictType))
        self.assert_('m' in d.keys())
        m = d['m']
        self.assert_(isinstance(m, DictType))
        self.assert_('Tr_hashpiece' in m.keys())
        val = m['Tr_hashpiece']
        self.assert_(isinstance(val, IntType))
        self.assert_(val == 250)

    def check_request(self, data):
        index = toint(data[1:5])
        begin = toint(data[5:9])
        length = toint(data[9:])
        return (index, begin, length)

    def create_good_hashpiece(self, oldstyle, chunkid):
        index, begin, length = chunkid
        if begin == 0:
            ohlist = self.tree.get_hashes_for_piece(index)
        else:
            ohlist = []

        chunk = self.read_chunk(index, begin, length)
        bohlist = bencode(ohlist)

        print >> sys.stderr, "test: create_good_hashpiece:", index, begin, length, "==len", len(chunk)

        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        if oldstyle:
            msg = HASHPIECE + payload
        else:
            # Offical: use the msg ID he defined in his handshake
            msg = EXTEND + HASHPIECE + payload
        return msg

    def read_chunk(self, index, begin, length):
        offset = index * self.tdef.get_piece_length() + begin
        f = open(self.sourcefn, "rb")
        f.seek(offset)
        chunk = f.read(length)
        f.close()
        return chunk

    #
    # Test whether Tribler sends good Tr_hashpiece on our requests
    #
    def _test_good_request(self):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        myid = Rand.rand_bytes(20)

        s = BTConnection('localhost', self.hisport, user_option_pattern=options, user_infohash=self.infohash, myid=myid)
        msg = self.create_good_nontribler_extend_hs()
        s.send(msg)
        s.read_handshake_medium_rare()

        # Tribler should send an EXTEND message back
        try:
            print >> sys.stderr, "test: Waiting for reply"
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >> sys.stderr, "test: Got reply", getMessageName(resp[0])
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])

            # 1. Pretend we're leecher: send INTERESTED
            msg = INTERESTED
            s.send(msg)
            print >> sys.stderr, "test: Pretend we are leecher"
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >> sys.stderr, "test: Got reply2", getMessageName(resp[0])
                if resp[0] == EXTEND:
                    print >> sys.stderr, "test: Got EXTEND type", getMessageName(resp[1])
                self.assert_(resp[0] == UNCHOKE or resp[0] == BITFIELD or resp[0] == EXTEND or resp[0] == HAVE)
                if resp[0] == UNCHOKE:
                    # 2. Reply with REQUESTs
                    for index in range(0, self.numpieces):
                        plen = self.get_piece_length(index)

                        for begin in range(0, plen, 2 ** 14):
                            length = self.get_chunk_length(index, begin)
                            print >> sys.stderr, "RETRIEVE", index, begin, length
                            chunkid = (index, begin, length)
                            msg = self.create_request(chunkid)
                            s.send(msg)

                    # s.send(NOT_INTERESTED)

                elif resp[0] == EXTEND and resp[1] == HASHPIECE:
                    done = self.check_hashpiece(resp)
                    if done:
                        break
                elif resp[0] == BITFIELD:
                    self.check_bitfield(resp)

            # s.close()
        except socket.timeout:
            print >> sys.stderr, "test: Timeout, bad, peer didn't reply in time"
            self.assert_(False)

        time.sleep(3)
        s.close()

    def get_piece_length(self, index):
        if index == (self.numpieces - 1):
            plen = self.tdef.get_length() % self.tdef.get_piece_length()
        else:
            plen = self.tdef.get_piece_length()
        return plen

    def get_chunk_length(self, index, begin):
        plen = self.get_piece_length(index)
        length = 2 ** 14
        if index == (self.numpieces - 1):
            if (begin + 2 ** 14) > plen:
                length = plen - begin
        return length

    def create_request(self, chunkid):
        index, begin, length = chunkid
        return REQUEST + tobinary(index) + tobinary(begin) + tobinary(length)

    def check_hashpiece(self, resp):
        """ Merkle BEP style """
        print >> sys.stderr, "test: good_request: check_hashpiece"
        self.assert_(resp[0] == EXTEND)
        self.assert_(resp[1] == HASHPIECE)
        index = toint(resp[2:2 + 4])
        begin = toint(resp[6:6 + 4])
        ohlen = toint(resp[10:10 + 4])
        print >> sys.stderr, "test: good_request: check_hashpiece", index, begin, ohlen
        bohlist = resp[14:14 + ohlen]
        hisohlist = bdecode(bohlist)
        hischunk = resp[14 + ohlen:]

        if begin == 0:
            self.assert_(isinstance(hisohlist, ListType))
            for oh in hisohlist:
                self.assert_(isinstance(oh, ListType))
                self.assert_(len(oh) == 2)
                self.assert_(isinstance(oh[0], IntType))
                self.assert_(isinstance(oh[1], StringType))

            hisohlist.sort()
            print >> sys.stderr, "test: good_request: check_hashpiece", repr(hisohlist)
            myohlist = self.tree.get_hashes_for_piece(index)
            myohlist.sort()

            self.assert_(len(hisohlist) == len(myohlist))
            for i in range(0, len(hisohlist)):
                hisoh = hisohlist[i]
                myoh = myohlist[i]
                self.assert_(hisoh == myoh)
        else:
            self.assert_(len(hisohlist) == 0)

        mylength = self.get_chunk_length(index, begin)
        mychunk = self.read_chunk(index, begin, mylength)

        self.assert_(hischunk == mychunk)

        return index == self.numpieces - 1 and mylength != 2 ** 14

    def check_bitfield(self, data):
        self.assert_(data[0] == BITFIELD)
        bitmap = data[1:]
        self.assert_(len(bitmap) == 1)
        # Must have set_breakup_seed_bitfield() set to False
        self.assert_(bitmap == '\xc0')

    #
    # Bad EXTEND handshake message
    #
    def subtest_bad_hashpiece(self, oldstyle):
        if not oldstyle:
            # Test becomes equivalent to BT keep alive message (len 0, payload '')
            self._test_bad(self.create_empty, oldstyle)
        self._test_bad(self.create_ext_id_not_byte, oldstyle)
        self._test_bad(self.create_not_hashpiece, oldstyle)
        self._test_bad(self.create_not_index, oldstyle)
        self._test_bad(self.create_not_begin, oldstyle)
        self._test_bad(self.create_not_len_bohlist, oldstyle)
        self._test_bad(self.create_ohlist_not_bdecodable, oldstyle)
        self._test_bad(self.create_ohlist_wrong_no_hashes, oldstyle)
        self._test_bad(self.create_ohlist_wrong_no_root_hash, oldstyle)
        self._test_bad(self.create_ohlist_wrong_bad_offset, oldstyle)
        self._test_bad(self.create_ohlist_wrong_bad_hash, oldstyle)
        # TODO: need working peer kicking for that
        # self._test_bad(self.create_bad_chunk,oldstyle)

    #
    # Main test code for bad EXTEND handshake messages
    #
    def _test_bad(self, msg_gen_func, oldstyle):
        print >> sys.stderr, "test: test_BAD: Create EXTEND HS", repr(msg_gen_func), oldstyle
        if oldstyle:
            options = None
            exthsmsg = self.create_good_tribler_extend_hs()
        else:
            options = '\x00\x00\x00\x00\x00\x10\x00\x00'
            exthsmsg = self.create_good_nontribler_extend_hs()

        s = BTConnection('localhost', self.hisport, user_option_pattern=options, user_infohash=self.infohash)
        s.send(exthsmsg)
        s.read_handshake_medium_rare()

        # Tribler should send an EXTEND message back
        try:
            print >> sys.stderr, "test: Waiting for reply"
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            print >> sys.stderr, "test: Got reply", getMessageName(resp[0])
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])

            # 1. Pretend we're seeder: send BITFIELD and UNCHOKE
            msg = BITFIELD + self.seederbitfieldstr
            s.send(msg)
            msg = UNCHOKE
            s.send(msg)
            print >> sys.stderr, "test: Pretend we are seeder"
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >> sys.stderr, "test: Got reply 2", getMessageName(resp[0])
                self.assert_(resp[0] == REQUEST or resp[0] == INTERESTED or resp[
                             0] == UNCHOKE or resp[0] == HAVE or resp[0] == NOT_INTERESTED)
                if resp[0] == REQUEST:
                    chunkid = self.check_request(resp)

                    # 2. Reply to REQUEST with *bad* HASHPIECE
                    msg = msg_gen_func(chunkid)
                    if oldstyle:
                        if len(msg) == 1:
                            msg = ''
                        else:
                            msg = msg[1:]  # Strip EXTEND byte
                    s.send(msg)
                    break

            # s.close()
        except socket.timeout:
            print >> sys.stderr, "test: Timeout, bad, peer didn't reply in time"
            self.assert_(False)

        time.sleep(3)
        # Should have closed the connection
        try:
            s.send(UNCHOKE)
            self.assert_(False)
        except:
            print_exc()

        s.close()

    #
    # Bad message creators (all create Merkle BEP style, I strip first byte
    # later for oldstyle
    #
    def create_empty(self, chunkid):
        return EXTEND

    def create_ext_id_not_byte(self, chunkid):
        return EXTEND + 'Hallo kijkbuiskinderen'

    def create_not_hashpiece(self, chunkid):
        index, begin, length = chunkid
        ohlist = []
        bohlist = bencode(ohlist)
        chunk = self.read_chunk(index, begin, length)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + chr(231) + payload

    def create_not_index(self, chunkid):
        payload = 'bla'
        return EXTEND + HASHPIECE + payload

    def create_not_begin(self, chunkid):
        index, begin, length = chunkid
        payload = tobinary(index) + 'bla'
        return EXTEND + HASHPIECE + payload

    def create_not_len_bohlist(self, chunkid):
        index, begin, length = chunkid
        payload = tobinary(index) + tobinary(begin) + 'bla'
        return EXTEND + HASHPIECE + payload

    def create_ohlist_not_bdecodable(self, chunkid):
        index, begin, length = chunkid
        bohlist = 'bla'
        chunk = '*' * (2 ** 14)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload

    def create_ohlist_wrong_no_hashes(self, chunkid):
        index, begin, length = chunkid
        ohlist = [(0, '#' * 20), (1, '$' * 20)]  # should contain 3 for file2.wmv: own, sibling and root
        bohlist = bencode(ohlist)
        chunk = '*' * (2 ** 14)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload

    def create_ohlist_wrong_no_root_hash(self, chunkid):
        index, begin, length = chunkid
        ohlist = self.tree.get_hashes_for_piece(index)
        newohlist = []
        # Remove root hash
        for oh in ohlist:
            if oh[0] != 0:
                newohlist.append(oh)
        ohlist = newohlist
        bohlist = bencode(ohlist)
        chunk = self.read_chunk(index, begin, length)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload

    def create_ohlist_wrong_bad_offset(self, chunkid):
        index, begin, length = chunkid
        ohlist = self.tree.get_hashes_for_piece(index)
        ohlist[1][0] = 481
        bohlist = bencode(ohlist)
        chunk = self.read_chunk(index, begin, length)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload

    def create_ohlist_wrong_bad_hash(self, chunkid):
        index, begin, length = chunkid
        ohlist = self.tree.get_hashes_for_piece(index)
        ohlist[1][1] = '$' * 20
        bohlist = bencode(ohlist)
        chunk = self.read_chunk(index, begin, length)
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload

    def create_bad_chunk(self, chunkid):
        index, begin, length = chunkid
        ohlist = self.tree.get_hashes_for_piece(index)
        bohlist = bencode(ohlist)
        chunk = '*' * length
        payload = tobinary(index) + tobinary(begin) + tobinary(len(bohlist)) + bohlist + chunk
        return EXTEND + HASHPIECE + payload


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_merkle_msg.py <method name>"
    else:
        suite.addTest(TestMerkleMessage(sys.argv[1]))

    return suite


def main():
    unittest.main(defaultTest='test_suite', argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
