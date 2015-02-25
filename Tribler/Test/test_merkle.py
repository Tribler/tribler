# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest

from tempfile import mkstemp
import os
from types import StringType, DictType
from math import ceil, log
from traceback import print_exc
import sha

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Merkle.merkle import MerkleTree, get_tree_height, create_tree, get_hashes_for_piece
from Tribler.Core.Utilities.bencode import bdecode


DEBUG = False


class TestMerkleHashes(unittest.TestCase):

    """
    Testing Simple Merkle Hashes extension version 0, in particular:
    * The algorithmic part
    * The .torrent file part
    See test_merkle_msg.py for protocol testing.
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_hashes_for_piece(self):
        """
            test MerkleTree.get_hashes_for_piece() method
        """
        self._test_123pieces_tree_get_hashes()
        self._test_8piece_tree_uncle_calc()

    def _test_123pieces_tree_get_hashes(self):
        for n in range(1, 64):
            piece_size = 2 ** n
            self._test_1piece_tree_get_hashes(piece_size, piece_size)
            for add in [1, piece_size - 1]:
                self._test_1piece_tree_get_hashes(piece_size, add)
                self._test_2piece_tree_get_hashes(piece_size, add)
                self._test_3piece_tree_get_hashes(piece_size, add)

    def _test_1piece_tree_get_hashes(self, piece_size, length_add):
        """ testing get_hashes_for_piece on tree with 1 piece """
        msg = "1piece_get_hashes(" + str(piece_size) + "," + str(length_add) + ") failed"
        npieces = 1
        total_length = length_add

        piece_hashes = ['\x01\x02\x03\x04\x05\x06\x07\x08\x07\x06\x05\x04\x03\x02\x01\x00\x01\x02\x03\x04'] * npieces
        tree = MerkleTree(piece_size, total_length, None, piece_hashes)
        for p in range(npieces):
            ohlist = tree.get_hashes_for_piece(p)
            self.assert_(len(ohlist) == 1, msg)
            self.assert_(ohlist[0][0] == 0, msg)
            self.assertEquals(ohlist[0][1], piece_hashes[0], msg)

    def _test_2piece_tree_get_hashes(self, piece_size, length_add):
        """testing get_hashes_for_piece on tree with 2 pieces """
        msg = "2piece_get_hashes(" + str(piece_size) + "," + str(length_add) + ") failed"
        npieces = 2
        total_length = piece_size + length_add

        piece_hashes = ['\x01\x02\x03\x04\x05\x06\x07\x08\x07\x06\x05\x04\x03\x02\x01\x00\x01\x02\x03\x04'] * npieces
        tree = MerkleTree(piece_size, total_length, None, piece_hashes)
        for p in range(npieces):
            ohlist = tree.get_hashes_for_piece(p)
            self.assert_(len(ohlist) == 3)
            ohlist.sort()
            self.assert_(ohlist[0][0] == 0, msg)
            self.assert_(ohlist[1][0] == 1, msg)
            self.assert_(ohlist[2][0] == 2, msg)
            self.assertDigestEquals(ohlist[1][1] + ohlist[2][1], ohlist[0][1], msg)

    def _test_3piece_tree_get_hashes(self, piece_size, length_add):
        """ testing get_hashes_for_piece on tree with 3 pieces """
        msg = "3piece_get_hashes(" + str(piece_size) + "," + str(length_add) + ") failed"
        npieces = 3
        total_length = 2 * piece_size + length_add

        piece_hashes = ['\x01\x02\x03\x04\x05\x06\x07\x08\x07\x06\x05\x04\x03\x02\x01\x00\x01\x02\x03\x04'] * npieces
        tree = MerkleTree(piece_size, total_length, None, piece_hashes)
        for p in range(npieces):
            ohlist = tree.get_hashes_for_piece(p)
            self.assert_(len(ohlist) == 4, msg)
            ohlist.sort()
            if p == 0 or p == 1:
                self.assert_(ohlist[0][0] == 0, msg)
                self.assert_(ohlist[1][0] == 2, msg)
                self.assert_(ohlist[2][0] == 3, msg)
                self.assert_(ohlist[3][0] == 4, msg)
                digest34 = self.calc_digest(ohlist[2][1] + ohlist[3][1])
                self.assertDigestEquals(digest34 + ohlist[1][1], ohlist[0][1], msg)
            else:
                self.assert_(ohlist[0][0] == 0, msg)
                self.assert_(ohlist[1][0] == 1, msg)
                self.assert_(ohlist[2][0] == 5, msg)
                self.assert_(ohlist[3][0] == 6, msg)
                digest56 = self.calc_digest(ohlist[2][1] + ohlist[3][1])
                self.assertDigestEquals(ohlist[1][1] + digest56, ohlist[0][1], msg)

    def assertDigestEquals(self, data, digest, msg=None):
        self.assertEquals(self.calc_digest(data), digest, msg)

    def calc_digest(self, data):
        digester = sha.new(data)
        return digester.digest()

    def _test_8piece_tree_uncle_calc(self):
        npieces = 8
        hashlist = self.get_indices_for_piece(0, npieces)
        assert hashlist == [7, 8, 4, 2, 0]

        hashlist = self.get_indices_for_piece(1, npieces)
        assert hashlist == [8, 7, 4, 2, 0]

        hashlist = self.get_indices_for_piece(2, npieces)
        assert hashlist == [9, 10, 3, 2, 0]

        hashlist = self.get_indices_for_piece(3, npieces)
        assert hashlist == [10, 9, 3, 2, 0]

        hashlist = self.get_indices_for_piece(4, npieces)
        assert hashlist == [11, 12, 6, 1, 0]

        hashlist = self.get_indices_for_piece(5, npieces)
        assert hashlist == [12, 11, 6, 1, 0]

        hashlist = self.get_indices_for_piece(6, npieces)
        assert hashlist == [13, 14, 5, 1, 0]

        hashlist = self.get_indices_for_piece(7, npieces)
        assert hashlist == [14, 13, 5, 1, 0]

    def get_indices_for_piece(self, index, npieces):
        height = get_tree_height(npieces)
        tree = create_tree(height)
        ohlist = get_hashes_for_piece(tree, height, index)
        list = []
        for oh in ohlist:
            list.append(oh[0])
        return list

    def test_check_hashes_update_hash_admin(self):
        """
            test MerkleTree.check_hashes() and update_hash_admin() methods
        """
        for n in range(1, 64):
            piece_size = 2 ** n
            for add in [1, piece_size - 1]:
                self._test_3piece_tree_check_hashes_update_hash_admin(piece_size, add)

    def _test_3piece_tree_check_hashes_update_hash_admin(self, piece_size, length_add):
        """ testing check_hashes and update_hash_admin tree with 3 pieces """
        msg = "3piece_check_hashes(" + str(piece_size) + "," + str(length_add) + ") failed"
        npieces = 3
        total_length = 2 * piece_size + length_add

        piece_hashes = ['\x01\x02\x03\x04\x05\x06\x07\x08\x07\x06\x05\x04\x03\x02\x01\x00\x01\x02\x03\x04'] * npieces
        fulltree = MerkleTree(piece_size, total_length, None, piece_hashes)
        root_hash = fulltree.get_root_hash()
        emptytree = MerkleTree(piece_size, total_length, root_hash, None)
        empty_piece_hashes = [0] * npieces

        for p in range(npieces):
            ohlist = fulltree.get_hashes_for_piece(p)
            self.assert_(emptytree.check_hashes(ohlist), msg)

        for p in range(npieces):
            ohlist = fulltree.get_hashes_for_piece(p)
            self.assert_(emptytree.check_hashes(ohlist), msg)
            emptytree.update_hash_admin(ohlist, empty_piece_hashes)

        for p in range(npieces):
            self.assert_(piece_hashes[p] == empty_piece_hashes[p], msg)

    @unittest.skip
    def test_merkle_torrent(self):
        """
            test the creation of Merkle torrent files via TorrentMaker/btmakemetafile.py
        """
        piece_size = 2 ** 18
        for file_size in [1, piece_size - 1, piece_size, piece_size + 1, 2 * piece_size, (2 * piece_size) + 1]:
            self.create_merkle_torrent(file_size, piece_size)

    def create_merkle_torrent(self, file_size, piece_size):
        try:
            # 1. create file
            [handle, datafilename] = mkstemp()
            os.close(handle)
            block = "".zfill(file_size)
            fp = open(datafilename, "wb")
            fp.write(block)
            fp.close()
            torrentfilename = datafilename + '.tribe'

            # 2. Set torrent args
            tdef = TorrentDef()
            tdef.set_tracker("http://localhost:6969/announce")
            tdef.set_piece_length(int(log(piece_size, 2)))

            # 3. create Merkle torrent
            # make_meta_file(datafilename,url,params,flag,dummy_progress,1,dummy_filecallback)
            tdef.add_content(datafilename)
            tdef.finalize()
            tdef.save(torrentfilename)

            # 4. read Merkle torrent
            fp = open(torrentfilename, "rb")
            data = fp.read(10000)
            fp.close()

            # 5. test Merkle torrent
            # basic tests
            dict = bdecode(data)
            self.assert_(isinstance(dict, DictType))
            self.assert_('info' in dict)
            info = dict['info']
            self.assert_(isinstance(info, DictType))
            self.assert_('pieces' not in info)
            self.assert_('root hash' in info)
            roothash = info['root hash']
            self.assert_(isinstance(roothash, StringType))
            self.assert_(len(roothash) == 20)

            # create hash tree
            hashes = self.read_and_calc_hashes(datafilename, piece_size)
            npieces = len(hashes)
            if DEBUG:
                print "npieces is", npieces
            height = log(npieces, 2) + 1
            if height > int(height):
                height += 1
            height = int(height)
            if DEBUG:
                print "height is", height

            starto = (2 ** (height - 1)) - 1

            if DEBUG:
                print "starto is", starto
            tree = [0] * ((2 ** height) - 1)
            if DEBUG:
                print "len tree is", len(tree)
            # put hashes in tree
            for i in range(len(hashes)):
                o = starto + i
                tree[o] = hashes[i]

            # fill unused
            nplaces = (2 ** height) - (2 ** (height - 1))
            xso = starto + npieces
            xeo = starto + nplaces
            for o in range(xso, xeo):
                tree[o] = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

            # calc higher level ones
            if height > 1:
                for o in range(len(tree) - starto - 2, -1, -1):
                    co = self.get_child_offset(o, height)
                    if DEBUG:
                        print "offset is", o, "co is", co
                    data = tree[co] + tree[co + 1]
                    digest = self.calc_digest(data)
                    tree[o] = digest
            self.assert_(tree[0], roothash)
        except Exception as e:
            print_exc()
        # finally:
        #    os.remove(datafilename)
        #    os.remove(torrentfilename)

    def read_and_calc_hashes(self, filename, piece_size):
        hashes = []
        fp = open(filename, "rb")
        while True:
            block = fp.read(piece_size)
            if len(block) == 0:
                break
            digest = self.calc_digest(block)
            hashes.append(digest)
            if len(block) != piece_size:
                break
        fp.close()
        return hashes

    def get_child_offset(self, offset, height):
        if DEBUG:
            print "get_child(", offset, ",", height, ")"
        if offset == 0:
            level = 1
        else:
            level = log(offset, 2)
            if level == int(level):
                level += 1
            else:
                level = ceil(level)
            level = int(level)
        starto = (2 ** (level - 1)) - 1
        diffo = offset - starto
        diffo *= 2
        cstarto = (2 ** level) - 1
        return cstarto + diffo


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestMerkleHashes))

    return suite

if __name__ == "__main__":
    unittest.main()
