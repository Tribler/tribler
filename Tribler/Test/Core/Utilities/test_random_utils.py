from Tribler.Core.Utilities.random_utils import random_string, random_unicode, random_infohash
from Tribler.Test.test_as_server import BaseTestCase


class TestRandomUtils(BaseTestCase):

    def test_random_string(self):
        test_string = random_string()
        self.assertIsNotNone(test_string)
        self.assertEqual(len(test_string), 6)

        text_length = 16
        test_string2 = random_string(size=text_length)
        self.assertEqual(len(test_string2), text_length)

    def test_random_unicode(self):
        test_unicode = random_unicode()
        self.assertIsNotNone(test_unicode)
        self.assertTrue(isinstance(test_unicode, unicode))
        self.assertEqual(len(test_unicode), 6)

        text_length = 16
        test_unicode2 = random_unicode(length=text_length)
        self.assertTrue(isinstance(test_unicode, unicode))
        self.assertEqual(len(test_unicode2), text_length)

    def test_infohash(self):
        test_infohash = random_infohash()
        self.assertIsNotNone(test_infohash)
        self.assertTrue(isinstance(test_infohash, str))
        self.assertEqual(len(test_infohash), 20)
