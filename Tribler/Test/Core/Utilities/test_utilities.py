from __future__ import absolute_import

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.web.server import Site
from twisted.web.util import Redirect

from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.utilities import http_get, is_channel_public_key, is_infohash, is_simple_match_query, \
    is_valid_url, parse_magnetlink
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.tools import trial_timeout


class TestMakeTorrent(AbstractServer):

    def __init__(self, *argv, **kwargs):
        super(TestMakeTorrent, self).__init__(*argv, **kwargs)
        self.http_server = None

    def setUpHttpRedirectServer(self, port, redirect_url):
        self.http_server = reactor.listenTCP(port, Site(Redirect(redirect_url)))

    @inlineCallbacks
    def tearDown(self):
        if self.http_server:
            yield maybeDeferred(self.http_server.stopListening)
        yield super(TestMakeTorrent, self).tearDown()

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

    @trial_timeout(5)
    def test_http_get_with_redirect(self):
        """
        Test if http_get is working properly if url redirects to a magnet link.
        """

        def on_callback(response):
            self.assertEqual(response, magnet_link)

        # Setup a redirect server which redirects to a magnet link
        magnet_link = "magnet:?xt=urn:btih:DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        port = get_random_port()

        self.setUpHttpRedirectServer(port, magnet_link)

        test_url = "http://localhost:%d" % port
        http_deferred = http_get(test_url).addCallback(on_callback)

        return http_deferred

    def test_simple_search_query(self):
        query = '"\xc1ubuntu"* AND "debian"*'
        self.assertTrue(is_simple_match_query(query))

        query2 = '"\xc1ubuntu"* OR "debian"*'
        self.assertFalse(is_simple_match_query(query2))

    def test_is_infohash(self):
        hex_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertTrue(is_infohash(hex_40))

        hex_not_40 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
        self.assertFalse(is_infohash(hex_not_40))

        not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertFalse(is_infohash(not_hex))

    def test_is_channel_public_key(self):
        hex_128 = "224b20c30b90d0fc7b2cf844f3d651de4481e21c7cdbbff258fa737d117d2c4ac7536de5cc93f4e9d5" \
                  "1012a1ae0c46e9a05505bd017f0ecb78d8eec4506e848a"
        self.assertTrue(is_channel_public_key(hex_128))

        hex_not_128 = "DC4B96CF85A85CEEDB8ADC4B96CF85"
        self.assertFalse(is_channel_public_key(hex_not_128))

        not_hex = "APPLE6CF85A85CEEDB8ADC4B96CF85A85CEEDB8A"
        self.assertFalse(is_channel_public_key(not_hex))
