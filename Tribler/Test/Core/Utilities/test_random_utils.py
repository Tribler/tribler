from __future__ import absolute_import

import six

from Tribler.Core.Utilities.random_utils import random_infohash, random_string, random_utf8_string
from Tribler.Test.test_as_server import BaseTestCase


class TestRandomUtils(BaseTestCase):

    def test_random_string(self):
        test_string = random_string()
        self.assertIsNotNone(test_string)
        self.assertEqual(len(test_string), 6)

        text_length = 16
        test_string2 = random_string(size=text_length)
        self.assertEqual(len(test_string2), text_length)

    def test_random_utf8_string(self):
        test_string = random_utf8_string()
        self.assertIsNotNone(test_string)
        self.assertTrue(isinstance(test_string, six.text_type))
        self.assertEqual(len(test_string), 6)

        text_length = 16
        test_string2 = random_utf8_string(length=text_length)
        self.assertTrue(isinstance(test_string, six.text_type))
        self.assertEqual(len(test_string2), text_length)

    def test_infohash(self):
        test_infohash = random_infohash()
        self.assertIsNotNone(test_infohash)
        self.assertTrue(isinstance(test_infohash, six.binary_type))
        self.assertEqual(len(test_infohash), 20)
