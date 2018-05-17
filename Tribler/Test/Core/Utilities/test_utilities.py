from urllib import unquote_plus

from Tribler.Core.Utilities.utilities import parse_magnetlink, is_valid_url
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

    def test_valid_url(self):
        """ Test if the URL is valid """
        test_url = "http://anno nce.torrentsmd.com:8080/announce"
        self.assertFalse(is_valid_url(test_url), "%s is not a valid URL" % test_url)

        test_url2 = "http://announce.torrentsmd.com:8080/announce "
        self.assertTrue(is_valid_url(test_url2), "%s is a valid URL" % test_url2)

        test_url3 = "http://localhost:1920/announce"
        self.assertTrue(is_valid_url(test_url3))

        test_url4 = "udp://localhost:1264"
        self.assertTrue(is_valid_url(test_url4))
