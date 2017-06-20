from Tribler.Core.Utilities.encoding import decode
from Tribler.Test.test_as_server import BaseTestCase


class TestMakeTorrent(BaseTestCase):

    def test_decode_unknown(self):
        """
        Test that a corrupt stream with a correct header throws a ValueError.

        Previously this was a KeyError, which was inconsistent with the rest of the class.
        """
        self.assertRaises(ValueError, decode, "a:")
