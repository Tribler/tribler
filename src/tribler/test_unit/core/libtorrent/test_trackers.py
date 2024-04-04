from ipv8.test.base import TestBase

from tribler.core.libtorrent.trackers import (
    MalformedTrackerURLException,
    add_url_params,
    get_uniformed_tracker_url,
    is_valid_url,
    parse_tracker_url,
)


class TestTrackers(TestBase):
    """
    Tests for the tracker-related functionality.
    """

    def test_get_uniformed_tracker_url_proper_udp(self) -> None:
        """
        Test if a proper UDP URL is not transformed.
        """
        url = "udp://tracker.example.com:80"

        self.assertEqual("udp://tracker.example.com:80", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_udp_no_port(self) -> None:
        """
        Test if a UDP URL without a port leads to a None value.
        """
        url = "udp://tracker.example.com"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_remove_path(self) -> None:
        """
        Test if a UDP URL with a path has its path removed.
        """
        url = "udp://tracker.example.com:80/announce"

        self.assertEqual("udp://tracker.example.com:80", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_trailing_zeros(self) -> None:
        """
        Test if a UDP URL with trailing zeros has the zeros removed.
        """
        url = "udp://tracker.example.com:80\x00"

        self.assertEqual("udp://tracker.example.com:80", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_trailing_other(self) -> None:
        """
        Test if a UDP URL with trailing garbage leads to a None value.
        """
        url = "udp://tracker.example.com:80\xFF"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_proper_http(self) -> None:
        """
        Test if a proper HTTP URL is not transformed.
        """
        url = "http://tracker.example.com:6969/announce"

        self.assertEqual("http://tracker.example.com:6969/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_http_trailing_fwdslash(self) -> None:
        """
        Test if a HTTP URL with a trailing forward slash has this postfix removed.
        """
        url = "http://tracker.example.com:6969/announce/"

        self.assertEqual("http://tracker.example.com:6969/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_http_no_path(self) -> None:
        """
        Test if a HTTP URL without a path leads to a None value.
        """
        url = "http://tracker.example.com"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_http_nbsp(self) -> None:
        """
        Test if a HTTP URL with a trailing non-breaking space.
        """
        url = "http://tracker.example.com\xa0"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_http_no_port(self) -> None:
        """
        Test if a HTTP URL without a port is not transformed.
        """
        url = "http://tracker.example.com/announce/"

        self.assertEqual("http://tracker.example.com/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_http_standard_port(self) -> None:
        """
        Test if a HTTP URL with the standard port has its port removed.
        """
        url = "http://tracker.example.com:80/announce/"

        self.assertEqual("http://tracker.example.com/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_bad_url(self) -> None:
        """
        Test if a HTTP URL bad URL encoding leads to a None value.
        """
        url = "http://tracker.example.com/?do=upload"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_truncated(self) -> None:
        """
        Test if a truncated HTTP URL leads to a None value.
        """
        url = "http://tracker.example.com/anno..."

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_https_no_port(self) -> None:
        """
        Test if a HTTPS URL without a port is not transformed.
        """
        url = "https://tracker.example.com/announce/"

        self.assertEqual("https://tracker.example.com/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_https_standard_port(self) -> None:
        """
        Test if a HTTPS URL with the standard port has its port removed.
        """
        url = "https://tracker.example.com:443/announce/"

        self.assertEqual("https://tracker.example.com/announce", get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_unknown_scheme(self) -> None:
        """
        Test if a URL with an unknown scheme leads to a None value.
        """
        url = "unknown://tracker.example.com/announce"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_corrupt_url(self) -> None:
        """
        Test if a URL with a corrupt URL leads to a None value.
        """
        url = "http://tracker.examp\xffle.com/announce"

        self.assertIsNone(get_uniformed_tracker_url(url))

    def test_get_uniformed_tracker_url_empty(self) -> None:
        """
        Test if an empty URL leads to a None value.
        """
        self.assertIsNone(get_uniformed_tracker_url(""))

    def test_parse_tracker_url_udp_with_port(self) -> None:
        """
        Test if tracker UDP URLs with a port are parsed correctly.
        """
        url = "udp://tracker.example.com:80"

        self.assertEqual(("udp", ("tracker.example.com", 80), ""), parse_tracker_url(url))

    def test_parse_tracker_url_http_with_port(self) -> None:
        """
        Test if tracker HTTP URLs with a port are parsed correctly.
        """
        url = "http://tracker.example.com:6969/announce"

        self.assertEqual(("http", ("tracker.example.com", 6969), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_https_with_port(self) -> None:
        """
        Test if tracker HTTPS URLs with a port are parsed correctly.
        """
        url = "https://tracker.example.com:6969/announce"

        self.assertEqual(("https", ("tracker.example.com", 6969), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_http_without_port(self) -> None:
        """
        Test if tracker HTTP URLs without a port are parsed correctly.
        """
        url = "http://tracker.example.com/announce"

        self.assertEqual(("http", ("tracker.example.com", 80), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_https_without_port(self) -> None:
        """
        Test if tracker HTTPS URLs without a port are parsed correctly.
        """
        url = "https://tracker.example.com/announce"

        self.assertEqual(("https", ("tracker.example.com", 443), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_http_non_standard_port(self) -> None:
        """
        Test if tracker HTTP URLs with a non-standard port are parsed correctly.
        """
        url = "http://ipv6.tracker.example.com:6969/announce"

        self.assertEqual(("http", ("ipv6.tracker.example.com", 6969), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_https_non_standard_port(self) -> None:
        """
        Test if tracker HTTPS URLs with a non-standard port are parsed correctly.
        """
        url = "https://ipv6.tracker.example.com:6969/announce"

        self.assertEqual(("https", ("ipv6.tracker.example.com", 6969), "/announce"), parse_tracker_url(url))

    def test_parse_tracker_url_unknown_scheme(self) -> None:
        """
        Test if tracker URLs with an unknown scheme raise a MalformedTrackerURLException.
        """
        url = "unknown://ipv6.tracker.example.com:6969/announce"

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_http_bad_url(self) -> None:
        """
        Test if tracker HTTP URLs with a bad URL raise a MalformedTrackerURLException.
        """
        url = "http://tracker.example.com:6969/announce( %("

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_https_bad_url(self) -> None:
        """
        Test if tracker HTTP URLs with a bad URL raise a MalformedTrackerURLException.
        """
        url = "https://tracker.example.com:6969/announce( %("

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_unknown_scheme_no_path(self) -> None:
        """
        Test if tracker URLs with an unknown scheme and no path raise a MalformedTrackerURLException.
        """
        url = "unknown://tracker.example.com:80"

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_http_no_path(self) -> None:
        """
        Test if tracker HTTP URLs without a path raise a MalformedTrackerURLException.
        """
        url = "http://ipv6.tracker.example.com:6969"

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_https_no_path(self) -> None:
        """
        Test if tracker HTTPS URLs without a path  raise a MalformedTrackerURLException.
        """
        url = "https://ipv6.tracker.example.com:6969"

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_parse_tracker_url_udp_no_port(self) -> None:
        """
        Test if tracker UDP URLs without a port raise a MalformedTrackerURLException.
        """
        url = "udp://tracker.example.com"

        with self.assertRaises(MalformedTrackerURLException):
            parse_tracker_url(url)

    def test_add_url_param_some_present(self) -> None:
        """
        Test if appending parameters to a URL works.
        """
        url = "http://stackoverflow.com/test?answers=true"
        new_params = {"answers": False, "data": ["some", "values"]}

        result = add_url_params(url, new_params)

        self.assertIn("data=values", result)
        self.assertIn("answers=false", result)

    def test_add_url_param_clean(self) -> None:
        """
        Test if adding parameters to a URL works.
        """
        url = "http://stackoverflow.com/test"
        new_params = {"data": ["some", "values"]}

        result = add_url_params(url, new_params)

        self.assertIn("data=some", result)
        self.assertIn("data=values", result)

    def test_valid_url_invalid_with_space(self) -> None:
        """
        Test if a URL with a space is invalid.
        """
        url = "http://anno nce.torrentsmd.com:8080/announce"

        self.assertFalse(is_valid_url(url))

    def test_valid_url_wild(self) -> None:
        """
        Test if a normal dotcom URL is valid.
        """
        url = "http://announce.torrentsmd.com:8080/announce "

        self.assertTrue(is_valid_url(url))

    def test_valid_url_localhost(self) -> None:
        """
        Test if a localhost URL is valid.
        """
        url = "http://localhost:1920/announce"

        self.assertTrue(is_valid_url(url))

    def test_valid_url(self) -> None:
        """
        Test if a UDP URL is valid.
        """
        url = "udp://localhost:1264"

        self.assertTrue(is_valid_url(url))
