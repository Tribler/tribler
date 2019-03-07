from __future__ import absolute_import

from Tribler.Core.Utilities.utilities import http_get, parse_magnetlink
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.messaging.deprecated.encoding import add_url_params


class TriblerCoreTestUtilities(TriblerCoreTest):

    def test_parse_magnetlink_valid(self):
        result = parse_magnetlink("magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1&xl=10826029&dn=mediawiki-1.15.1"
                                  ".tar.gz&xt=urn:tree:tiger:7N5OAMRNGMSSEUE3ORHOKWN4WWIQ5X4EBOOTLJY&xt=urn:btih:QHQXPY"
                                  "WMACKDWKP47RRVIV7VOURXFE5Q&tr=http%3A%2F%2Ftracker.example.org%2Fannounce.php%3Fuk"
                                  "%3D1111111111%26&as=http%3A%2F%2Fdownload.wikimedia.org%2Fmediawiki%2F1.15%2Fmediawi"
                                  "ki-1.15.1.tar.gz&xs=http%3A%2F%2Fcache.example.org%2FXRX2PEFXOOEJFRVUCX6HMZMKS5TWG4K"
                                  "5&xs=dchub://example.org")
        self.assertEqual(result, (u'mediawiki-1.15.1.tar.gz', '\x81\xe1w\xe2\xcc\x00\x94;)\xfc\xfccTW\xf5u#r\x93\xb0',
                                  ['http://tracker.example.org/announce.php?uk=1111111111&']))

    def test_parse_magnetlink_nomagnet(self):
        result = parse_magnetlink("http://")
        self.assertEqual(result, (None, None, []))

    def test_add_url_param_some_present(self):
        url = 'http://stackoverflow.com/test?answers=true'
        new_params = {'answers': False, 'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertEqual(result, 'http://stackoverflow.com/test?data=some&data=values&answers=false')

    def test_add_url_param_clean(self):
        url = 'http://stackoverflow.com/test'
        new_params = {'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertEqual(result, 'http://stackoverflow.com/test?data=some&data=values')

    @trial_timeout(10)
    def test_http_get_expired(self):
        uri = "https://expired.badssl.com"

        def cbResponse(_):
            self.fail("Error was expected.")

        def cbErrorResponse(response):
            self.assertIsNotNone(response)

        http_deferred = http_get(uri)
        http_deferred.addCallback(cbResponse)
        http_deferred.addErrback(cbErrorResponse)

        return http_deferred
