from urllib import unquote_plus

from Tribler.Core.Utilities.utilities import parse_magnetlink, unicode_quoter, quote_plus_unicode
from Tribler.Test.test_as_server import BaseTestCase


class TestMakeTorrent(BaseTestCase):

    def test_parse_magnetlink_lowercase(self):
        """
        Test if a lowercase magnet link can be parsed
        """
        _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:apctqfwnowubxzoidazgaj2ba6fs6juc')

        self.assertEqual(hashed, "\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82")

    def test_parse_magnetlink_uppercase(self):
        """
        Test if a lowercase magnet link can be parsed
        """
        _, hashed, _ = parse_magnetlink('magnet:?xt=urn:btih:APCTQFWNOWUBXZOIDAZGAJ2BA6FS6JUC')

        self.assertEqual(hashed, "\x03\xc58\x16\xcdu\xa8\x1b\xe5\xc8\x182`'A\x07\x8b/&\x82")

    def test_quoter_char(self):
        """
        Test if an ASCII character is quoted correctly
        """
        char = u'A'

        encoded = unicode_quoter(char)

        self.assertEqual(char, unquote_plus(encoded))

    def test_quoter_unichar(self):
        """
        Test if a unicode character is quoted correctly
        """
        char = u'\u9b54'

        encoded = unicode_quoter(char)

        self.assertEqual(char, unquote_plus(encoded))

    def test_quoter_reserved(self):
        """
        Test if a URI reserved character is quoted correctly
        """
        char = u'+'

        encoded = unicode_quoter(char)

        self.assertNotEqual(char, encoded)
        self.assertEqual(char, unquote_plus(encoded))

    def test_quote_plus_unicode_char(self):
        """
        Test if a ASCII characters are quoted correctly
        """
        s = u'Ab09'

        encoded = quote_plus_unicode(s)

        self.assertEqual(s, unquote_plus(encoded))

    def test_quote_plus_unicode_unichar(self):
        """
        Test if unicode characters are quoted correctly
        """
        s = u'\u9b54\u11b3\uaf92\u1111'

        encoded = quote_plus_unicode(s)

        self.assertEqual(s, unquote_plus(encoded))

    def test_quote_plus_unicode_reserved(self):
        """
        Test if a URI reserved characters are quoted correctly
        """
        s = u'+ &'

        encoded = quote_plus_unicode(s)

        self.assertNotEqual(s, encoded)
        self.assertEqual(s, unquote_plus(encoded))

    def test_quote_plus_unicode_compound(self):
        """
        Test if a jumble of unicode, reserved and normal chars are quoted correctly
        """
        s = u'\u9b54\u11b3+ A5&\uaf92\u1111'

        encoded = quote_plus_unicode(s)

        self.assertNotEqual(s, encoded)
        self.assertEqual(s, unquote_plus(encoded))
