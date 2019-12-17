from ipv8.messaging.deprecated.encoding import add_url_params

from Tribler.Core.Utilities.utilities import parse_magnetlink
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestUtilities(TriblerCoreTest):

    def test_parse_magnetlink_valid(self):
        result = parse_magnetlink("magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1&xl=10826029&dn=mediawiki-1.15.1"
                                  ".tar.gz&xt=urn:tree:tiger:7N5OAMRNGMSSEUE3ORHOKWN4WWIQ5X4EBOOTLJY&xt=urn:btih:QHQXPY"
                                  "WMACKDWKP47RRVIV7VOURXFE5Q&tr=http%3A%2F%2Ftracker.example.org%2Fannounce.php%3Fuk"
                                  "%3D1111111111%26&as=http%3A%2F%2Fdownload.wikimedia.org%2Fmediawiki%2F1.15%2Fmediawi"
                                  "ki-1.15.1.tar.gz&xs=http%3A%2F%2Fcache.example.org%2FXRX2PEFXOOEJFRVUCX6HMZMKS5TWG4K"
                                  "5&xs=dchub://example.org")
        self.assertEqual(result, ('mediawiki-1.15.1.tar.gz', b'\x81\xe1w\xe2\xcc\x00\x94;)\xfc\xfccTW\xf5u#r\x93\xb0',
                                  ['http://tracker.example.org/announce.php?uk=1111111111&']))

    def test_parse_magnetlink_nomagnet(self):
        result = parse_magnetlink("http://")
        self.assertEqual(result, (None, None, []))

    def test_add_url_param_some_present(self):
        url = 'http://stackoverflow.com/test?answers=true'
        new_params = {'answers': False, 'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertIn("data=values", result)
        self.assertIn("answers=false", result)

    def test_add_url_param_clean(self):
        url = 'http://stackoverflow.com/test'
        new_params = {'data': ['some', 'values']}
        result = add_url_params(url, new_params)
        self.assertIn("data=some", result)
        self.assertIn("data=values", result)
