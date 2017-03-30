from Tribler.Core.Utilities.maketorrent import offset_to_piece
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestMiscUtils(TriblerCoreTest):

    def test_offset_to_piece(self):
        self.assertEqual(offset_to_piece(42, 2), 21)
        self.assertEqual(offset_to_piece(42, 18), 3)
        self.assertEqual(offset_to_piece(71, 11), 7)
        self.assertEqual(offset_to_piece(42, 18, endpoint=False), 2)
