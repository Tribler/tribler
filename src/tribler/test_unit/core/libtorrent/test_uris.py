from pathlib import PurePosixPath, PureWindowsPath
from unittest.mock import AsyncMock, Mock, patch

from ipv8.test.base import TestBase
from multidict import istr

import tribler
from tribler.core.libtorrent.uris import unshorten, url_to_path


class TestURIs(TestBase):
    """
    Tests for the URI-related functionality.
    """

    def test_url_to_path_unc(self) -> None:
        """
        Test if UNC URLs can be converted to Paths.
        """
        with patch("os.name", "nt"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PureWindowsPath}):
            path = url_to_path("file://server/share/path")

        self.assertEqual(r"\\server\share\path", path)

    def test_url_to_path_win_path(self) -> None:
        """
        Test if normal Windows file URLs can be converted to Paths.
        """
        with patch("os.name", "nt"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PureWindowsPath}):
            path = url_to_path("file:///C:/path/to/file")

        self.assertEqual(r"C:\path\to\file", path)

    def test_url_to_path_win_path_with_spaces(self) -> None:
        """
        Test if Windows file URLs with spaces can be converted to Paths.
        """
        with patch("os.name", "nt"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PureWindowsPath}):
            path = url_to_path("file:///C:/path/to/file%20with%20space")

        self.assertEqual(r"C:\path\to\file with space", path)

    def test_url_to_path_win_path_with_special_chars(self) -> None:
        """
        Test if Windows file URLs with special characters can be converted to Paths.
        """
        with patch("os.name", "nt"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PureWindowsPath}):
            path = url_to_path("file:///C:/%2520%2521file")

        self.assertEqual(r"C:\%20%21file", path)

    def test_url_to_path_posix_file(self) -> None:
        """
        Test if normal POSIX file URLs can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file:///path/to/file")

        self.assertEqual("/path/to/file", path)

    def test_url_to_path_posix_file_with_space(self) -> None:
        """
        Test if POSIX file URLs with spaces can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file:///path/to/file%20with%20space")

        self.assertEqual("/path/to/file with space", path)

    def test_url_to_path_posix_file_with_special_chars(self) -> None:
        """
        Test if POSIX file URLs with special characters can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file:///path/to/%2520%2521file")

        self.assertEqual("/path/to/%20%21file", path)

    def test_url_to_path_posix_file_with_double_slash(self) -> None:
        """
        Test if POSIX file URLs with double slashes can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file:////path/to/file")

        self.assertEqual("//path/to/file", path)

    def test_url_to_path_posix_file_absolute(self) -> None:
        """
        Test if POSIX file URLs starting at root can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file:/path")

        self.assertEqual("/path", path)

    def test_url_to_path_posix_file_host(self) -> None:
        """
        Test if POSIX file URLs starting at a host can be converted to Paths.
        """
        with patch("os.name", "posix"), patch.dict(tribler.core.libtorrent.uris.__dict__, {"Path": PurePosixPath}):
            path = url_to_path("file://localhost/path")

        self.assertEqual("/path", path)

    async def test_unshorten_non_http_https(self) -> None:
        """
        Test if URLs with non-HTTP(s) schemes are not followed.
        """
        url = "udp://tracker.example.com/"

        unshortened = await unshorten(url)

        self.assertEqual(url, unshortened)

    async def test_unshorten_non_redirect(self) -> None:
        """
        Test if following URLs that are not redirected are ignored.
        """
        url = "http://tracker.example.com/"

        with patch.dict(tribler.core.libtorrent.uris.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=AsyncMock(
                    __aexit__=AsyncMock(),
                    __aenter__=AsyncMock(return_value=Mock(status=200, headers={istr("Location"): "test"}))
                ))))
        ))}):
            unshortened = await unshorten(url)

        self.assertEqual(url, unshortened)

    async def test_unshorten_redirect_no_location(self) -> None:
        """
        Test if following URLs that are redirected but specify no location are ignored.
        """
        url = "http://tracker.example.com/"

        with patch.dict(tribler.core.libtorrent.uris.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=AsyncMock(
                    __aexit__=AsyncMock(),
                    __aenter__=AsyncMock(return_value=Mock(status=301, headers={}))
                ))))
        ))}):
            unshortened = await unshorten(url)

        self.assertEqual(url, unshortened)

    async def test_unshorten_redirect(self) -> None:
        """
        Test if following URLs that are properly redirected are followed.
        """
        url = "http://tracker.example.com/"

        with patch.dict(tribler.core.libtorrent.uris.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(get=AsyncMock(return_value=AsyncMock(
                    __aexit__=AsyncMock(),
                    __aenter__=AsyncMock(return_value=Mock(status=301, headers={istr("Location"): "test"}))
                ))))
        ))}):
            unshortened = await unshorten(url)

        self.assertEqual("test", unshortened)
