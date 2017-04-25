import binascii
import sys
from nose.tools import raises

from Tribler.Core.Utilities.unicode import bin2unicode, str2unicode, dunno2unicode
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestUnicode(TriblerCoreTest):

    def test_unicode_binary_1(self):
        data = "test"
        self.assertNotIsInstance(data, unicode)
        data = binascii.b2a_uu(data)
        data = bin2unicode(data)
        self.assertIsInstance(data, unicode)

    def test_unicode_binary_2(self):
        data = binascii.b2a_uu("test")
        data = bin2unicode(data, None)
        self.assertIsInstance(data, unicode)

    def test_unicode_binary_3(self):
        data = binascii.b2a_uu("test")
        data = bin2unicode(data, 'bla')
        self.assertIsInstance(data, unicode)

    @raises(Exception)
    def test_unicode_binary_4(self):
        bin2unicode({}, 'bla')

    @raises(Exception)
    def test_unicode_binary_5(self):
        bin2unicode({}, sys.getfilesystemencoding())

    def test_unicode_string_1(self):
        self.assertIsInstance(str2unicode("test"), unicode)

    def test_unicode_string_2(self):
        self.assertIsInstance(str2unicode('hi\xa0there'), unicode)

    def test_unicode_dunno_1(self):
        self.assertIsInstance(dunno2unicode("test"), unicode)

    def test_unicode_dunno_2(self):
        self.assertIsInstance(dunno2unicode(u"test"), unicode)

    def test_unicode_dunno_3(self):
        self.assertIsInstance(dunno2unicode({}), unicode)
