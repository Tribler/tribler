from nose.tools import raises

from Tribler.Core.Utilities.tracker_utils import parse_tracker_url, get_uniformed_tracker_url, \
    MalformedTrackerURLException

from Tribler.Test.Core.base_test import TriblerCoreTest


class TestGetUniformedTrackerUrl(TriblerCoreTest):
    """
    Tests for the get_uniformed_tracker_url method.
    """

    def test_uniform_scheme_correct_udp(self):
        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:80")
        self.assertEqual(result, u'udp://tracker.openbittorrent.com:80')

    def test_uniform_scheme_correct_http(self):
        result = get_uniformed_tracker_url("http://torrent.ubuntu.com:6969/announce")
        self.assertEqual(result, u'http://torrent.ubuntu.com:6969/announce')

    def test_uniform_scheme_correct_http_training_slash(self):
        result = get_uniformed_tracker_url("http://torrent.ubuntu.com:6969/announce/")
        self.assertEqual(result, u'http://torrent.ubuntu.com:6969/announce')

    def test_uniform_scheme_unknown(self):
        result = get_uniformed_tracker_url("unknown://tracker.openbittorrent.com/announce")
        self.assertIsNone(result)

    def test_uniform_http_no_path(self):
        result = get_uniformed_tracker_url("http://tracker.openbittorrent.com")
        self.assertIsNone(result)

    def test_uniform_udp_no_port(self):
        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com")
        self.assertIsNone(result)

    def test_uniform_udp_remove_path(self):
        result = get_uniformed_tracker_url("udp://tracker.openbittorrent.com:6969/announce")
        self.assertEqual(result, u'udp://tracker.openbittorrent.com:6969')

    def test_uniform_http_no_path_nbsp(self):
        result = get_uniformed_tracker_url("http://google.nl\xa0")
        self.assertFalse(result)

    def test_uniform_http_default_port(self):
        result = get_uniformed_tracker_url("http://torrent.ubuntu.com/announce")
        self.assertEqual(result, u'http://torrent.ubuntu.com/announce')

    def test_uniform_http_default_port_given(self):
        result = get_uniformed_tracker_url("http://torrent.ubuntu.com:80/announce")
        self.assertEqual(result, u'http://torrent.ubuntu.com/announce')


class TestParseTrackerUrl(TriblerCoreTest):
    """
    Tests for the parse_tracker_url method.
    """

    def test_parse_scheme_correct_udp(self):
        result = parse_tracker_url("udp://tracker.openbittorrent.com:80")
        self.assertEqual(result, (u'udp', (u'tracker.openbittorrent.com', 80), u''))

    def test_parse_scheme_correct_http(self):
        result = parse_tracker_url("http://torrent.ubuntu.com:6969/announce")
        self.assertEqual(result, (u'http', (u'torrent.ubuntu.com', 6969), u'/announce'))

    @raises(MalformedTrackerURLException)
    def test_parse_scheme_unknown(self):
        parse_tracker_url("unknown://ipv6.torrent.ubuntu.com:6969/announce")

    @raises(MalformedTrackerURLException)
    def test_parse_scheme(self):
        parse_tracker_url("http://torrent.ubuntu.com:80")

    @raises(MalformedTrackerURLException)
    def test_parse_http_no_announce_path(self):
        parse_tracker_url("unknown://ipv6.torrent.ubuntu.com:6969")

    @raises(MalformedTrackerURLException)
    def test_parse_udp_no_port(self):
        parse_tracker_url("udp://tracker.openbittorrent.com")

    def test_parse_http_no_port(self):
        result = parse_tracker_url("http://tracker.openbittorrent.com/announce")
        self.assertEqual(result, (u'http', (u'tracker.openbittorrent.com', 80), u'/announce'))

    def test_parse_http_non_standard_port(self):
        result = parse_tracker_url("http://ipv6.torrent.ubuntu.com:6969/announce")
        self.assertEqual(result, (u'http', (u'ipv6.torrent.ubuntu.com', 6969), u'/announce'))
