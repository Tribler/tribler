from nose.tools import raises
from Tribler.Core.Utilities.tracker_utils import get_uniformed_tracker_url, parse_tracker_url
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestTrackerUtils(TriblerCoreTest):

    def test_get_uniformed_tracker_url(self):
        result = get_uniformed_tracker_url("http://tracker.openbittorrent.com:80/announce")
        self.assertEqual(result, "http://tracker.openbittorrent.com/announce")

        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:80/announce/")
        self.assertEqual(result, "udp://tracker.openbittorrent.com:80")

        result = get_uniformed_tracker_url("tcp://tracker.openbittorrent.com:80/announce/")
        self.assertFalse(result)

        result = get_uniformed_tracker_url("http://google.nl\xa0")
        self.assertFalse(result)

        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:80")
        self.assertEqual(result, "udp://tracker.openbittorrent.com:80")

        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com")
        self.assertFalse(result)

        result = get_uniformed_tracker_url("http://tracker.openbittorrent.com/test")
        self.assertEqual(result, "http://tracker.openbittorrent.com/test")

        result = get_uniformed_tracker_url("http://tracker.openbittorrent.com:abc/test")
        self.assertFalse(result)

        result = get_uniformed_tracker_url("http://tracker.openbittorrent.com:81/test")
        self.assertEqual(result, "http://tracker.openbittorrent.com:81/test")

    def test_parse_tracker_url(self):
        result = parse_tracker_url("http://tracker.openbittorrent.com:80/announce")
        self.assertEqual(result[0], "HTTP")
        self.assertEqual(result[2], "announce")

        result = parse_tracker_url("udp://tracker.openbittorrent.com:80/announce")
        self.assertEqual(result[0], "UDP")
        self.assertEqual(result[2], "announce")

        result = parse_tracker_url("udp://tracker.openbittorrent.com:80")
        self.assertEqual(result[0], "UDP")
        self.assertFalse(result[2])

        result = parse_tracker_url("http://tracker.openbittorrent.com/announce")
        self.assertEqual(result[0], "HTTP")
        self.assertEqual(result[2], "announce")

    @raises(RuntimeError)
    def test_parse_tracker_url_wrong_type_1(self):
        parse_tracker_url("abc://tracker.openbittorrent.com:80/announce")

    @raises(RuntimeError)
    def test_parse_tracker_url_wrong_type_2(self):
        parse_tracker_url("udp://tracker.openbittorrent.com/announce")

    @raises(RuntimeError)
    def test_parse_tracker_url_wrong_type_3(self):
        parse_tracker_url("http://tracker.openbittorrent.com:80")

    @raises(RuntimeError)
    def test_parse_tracker_url_wrong_type_4(self):
        parse_tracker_url("http://tracker.openbittorrent.com:abc/announce")

