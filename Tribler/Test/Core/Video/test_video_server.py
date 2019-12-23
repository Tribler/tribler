"""
Tests for the video server.

Author(s): Arno Bakker
"""
import os
from asyncio import Future, Protocol, get_event_loop

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Core.Video.VideoServer import VideoServer
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


class VideoServerProtocol(Protocol):

    def __init__(self, finished, content_size, expected_content, setset, exp_byte_range):
        self.finished = finished
        self.content_size = content_size
        self.seen_empty_line = False
        self.has_header = False
        self.expected_content = expected_content
        self.setset = setset
        self.exp_byte_range = exp_byte_range
        self.data = b''

    def connection_made(self, transport):
        self.transport = transport

    def send(self, msg):
        self.transport.write(msg.encode('utf8'))

    def data_received(self, data):
        self.data += data

    def eof_received(self):
        data = self.data
        if not self.has_header:
            for line in data.split(b'\r\n'):
                if len(line) == 0 and self.seen_empty_line:
                    self.has_header = True
                elif len(line) == 0:
                    self.seen_empty_line = True
                else:
                    self.seen_empty_line = False
                    self.check_header(line)
        else:
            assert self.expected_content == data
            self.transport.close()

    def connection_lost(self, _):
        if not self.finished.done():
            self.finished.set_result(None)

    def check_header(self, line):
        if not self.transport.is_closing():
            return

        if line.startswith(b"HTTP"):
            if not self.setset:
                # Python returns "HTTP/1.0 206 Partial Content\r\n" HTTP 1.0???
                assert line.startswith(b"HTTP/1.")
                assert line.find(b"206") != -1  # Partial content
            else:
                assert line.startswith(b"HTTP/1.")
                assert line.find(b"416") != -1  # Requested Range Not Satisfiable
                self.transport.close()

        elif line.startswith(b"Content-Range:"):
            expline = "Content-Range: bytes " + TestVideoServerSession.create_range_str(
                self.exp_byte_range[0], self.exp_byte_range[1]) + "/" + str(self.content_size)
            assert expline.encode() == line

        elif line.startswith(b"Content-Type:") and not self.setset:
            # We do not check for an exact content-type since that might differ between platforms.
            assert line.startswith(b"Content-Type: video")

        elif line.startswith(b"Content-Length:"):
            assert line == b"Content-Length: " + str(len(self.expected_content)).encode()


class TestVideoServer(TriblerCoreTest):

    async def setUp(self):
        await TriblerCoreTest.setUp(self)
        self.mock_session = MockObject()
        self.video_server = VideoServer(self.get_port(), self.mock_session)

    def test_get_vod_dest_dir(self):
        """
        Testing whether the right destination of a VOD download is returned
        """
        mock_download = MockObject()
        mock_download.get_content_dest = lambda: "abc"
        mock_download.config = MockObject()
        mock_download.config.get_selected_files = lambda: ["def"]
        mock_def = MockObject()
        mock_def.is_multifile_torrent = lambda: True
        mock_download.get_def = lambda: mock_def

        self.assertEqual(self.video_server.get_vod_destination(mock_download), os.path.join("abc", "def"))

    def test_get_vod_stream(self):
        """
        Testing whether the right VOD stream is returned
        """
        self.mock_session.ltmgr = MockObject()
        self.mock_session.ltmgr.get_download = lambda _: None
        self.assertEqual(self.video_server.get_vod_stream("abcd"), (None, None))


class TestVideoServerSession(TestAsServer):

    """
    Class for testing HTTP-based video server in a session.

    Mainly HTTP range queries.
    """
    async def setUp(self):
        """ unittest test setup code """
        await super(TestVideoServerSession, self).setUp()
        self.port = self.session.config.get_video_server_port()
        self.sourcefn = os.path.join(TESTS_DATA_DIR, "video.avi")
        self.sourcesize = os.path.getsize(self.sourcefn)
        self.tdef = None
        self.expsize = 0
        await self.start_vod_download()

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent_enabled(True)
        self.config.set_video_server_enabled(True)

    @timeout(10)
    async def test_specific_range(self):
        await self.range_check(115, 214)

    @timeout(10)
    async def test_last_100(self):
        await self.range_check(self.sourcesize - 100, None)

    @timeout(10)
    async def test_first_100(self):
        await self.range_check(None, 100)

    @timeout(10)
    async def test_combined(self):
        await self.range_check(115, 214, setset=True)

    async def start_vod_download(self):
        self.tdef = TorrentDef()
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_tracker("http://127.0.0.1:12/announce")
        self.tdef.save()

        dscfg = DownloadConfig()
        dscfg.set_dest_dir(os.path.dirname(self.sourcefn))

        download = self.session.ltmgr.add(self.tdef, dscfg)
        await download.get_handle()

    def get_std_header(self):
        msg = "GET /%s/0 HTTP/1.1\r\n" % hexlify(self.tdef.get_infohash())
        msg += "Host: 127.0.0.1:" + str(self.port) + "\r\n"
        return msg

    @staticmethod
    def create_range_str(firstbyte, lastbyte):
        head = ""
        if firstbyte is not None:
            head += str(firstbyte)
        head += "-"
        if lastbyte is not None:
            head += str(lastbyte)

        return head

    def get_header(self, firstbyte, lastbyte, setset=False):
        head = self.get_std_header()

        head += "Range: bytes="
        head += self.create_range_str(firstbyte, lastbyte)
        if setset:
            # Make into set of byte ranges, VideoHTTPServer should refuse.
            head += ",0-99"
        head += "\r\n"

        head += "Connection: close\r\n"

        return head + "\r\n"

    async def range_check(self, firstbyte, lastbyte, setset=False):
        test_future = Future()
        self._logger.debug("range_test: %s %s %s setset %s", firstbyte, lastbyte, self.sourcesize, setset)

        if firstbyte is not None and lastbyte is None:
            exp_byte_range = (firstbyte, self.sourcesize - 1)
        elif firstbyte is None and lastbyte is not None:
            exp_byte_range = (self.sourcesize - lastbyte, self.sourcesize - 1)
        else:
            exp_byte_range = (firstbyte, lastbyte)

        # the amount of bytes actually requested. (Content-length)
        self.expsize = exp_byte_range[1] - exp_byte_range[0] + 1
        with open(self.sourcefn, "rb") as f:
            f.seek(exp_byte_range[0])

            expdata = f.read(self.expsize)

        protocol = VideoServerProtocol(test_future, self.sourcesize, expdata, setset, exp_byte_range)
        transport, _ = await get_event_loop().create_connection(lambda: protocol, "localhost", self.port)
        protocol.send(self.get_header(firstbyte, lastbyte, setset))
        await test_future
        transport.close()
