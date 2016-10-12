from Tribler.Core.APIImplementation.miscutils import offset2piece
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestMiscUtils(TriblerCoreTest):

    def test_offset2piece(self):
        self.assertEqual(offset2piece(42, 2), 21)
        self.assertEqual(offset2piece(42, 18), 3)
        self.assertEqual(offset2piece(71, 11), 7)
        self.assertEqual(offset2piece(42, 18, endpoint=False), 2)
