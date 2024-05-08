from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call

from configobj import ConfigObj
from ipv8.test.base import TestBase
from validate import Validator

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.stream import Stream, StreamChunk
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT


class MockStreamChunk(StreamChunk):
    """
    StreamChunk with a mocked open method.
    """

    async def open(self) -> None:
        """
        Fake opening a file.
        """
        if self.file is None:
            self.file = BytesIO()
        self.file.seek(0)


class TestStreamChunk(TestBase):
    """
    Tests for the StreamChunk class.
    """

    def setUp(self) -> None:
        """
        Create a new mocked stream chunk.
        """
        super().setUp()

        self.chunk = MockStreamChunk(Mock(), 0)
        self.chunk.stream.cursorpiecemap = {0: [False, []]}

    def create_mock_content(self, content: bytes, piece_length: int = 1) -> None:
        """
        Set the value of the stream to certain content.
        """
        content_end = len(content) // piece_length
        self.chunk.stream.updateprios = AsyncMock()
        self.chunk.stream.iterpieces = lambda have, startfrom: list(range(startfrom, content_end))
        self.chunk.stream.pieceshave = [True] * content_end
        self.chunk.stream.lastpiece = content_end
        self.chunk.stream.bytetopiece = lambda x: x // piece_length
        self.chunk.stream.prebuffsize = 1
        self.chunk.stream.piecelen = piece_length
        self.chunk.file = BytesIO()
        self.chunk.file.write(b"content")
        self.chunk.file.seek(0)

    async def test_stream_error(self) -> None:
        """
        Test if a chunk context closes the chunk when an exception occurs.
        """
        with self.assertRaises(RuntimeError):
            async with self.chunk:
                raise RuntimeError

        self.assertIsNone(self.chunk.file)
        self.assertTrue(self.chunk.isclosed)

    async def test_read_empty(self) -> None:
        """
        Test if all bytes can be read from a chunk when it has no data.
        """
        self.chunk.stream.updateprios = AsyncMock()
        self.chunk.stream.iterpieces = Mock(return_value=[])
        self.chunk.stream.lastpiece = 0
        self.chunk.stream.bytetopiece = Mock(return_value=-1)

        async with self.chunk:
            value = await self.chunk.read()

        self.assertEqual(b"", value)

    async def test_read_single_piece(self) -> None:
        """
        Test if all bytes can be read from a chunk when its data is in a single piece.
        """
        self.create_mock_content(b"content", len(b"content"))

        async with self.chunk:
            streamed = await self.chunk.read()

        self.assertEqual(b"content", streamed)

    async def test_read_multiple_pieces(self) -> None:
        """
        Test if all bytes can be read from a chunk when its data is in multiple pieces.
        """
        self.create_mock_content(b"content", 1)

        streamed = b""
        async with self.chunk:
            for _ in range(len(b"content")):
                streamed += await self.chunk.read()

        self.assertEqual(b"content", streamed)

    async def test_seek(self) -> None:
        """
        Test if we can seek to a certain piece.
        """
        self.create_mock_content(b"content", 1)

        value = await self.chunk.seek(3)

        streamed = b""
        async with self.chunk:
            for _ in range(len(b"tent")):
                streamed += await self.chunk.read()

        self.assertEqual([3], value)
        self.assertEqual(b"tent", streamed)

    def test_pause(self) -> None:
        """
        Test if the chunk can tell its stream to pause.
        """
        self.chunk.stream.cursorpiecemap[1] = [False, [0]]

        result = self.chunk.pause()

        self.assertTrue(result)
        self.assertTrue(self.chunk.stream.cursorpiecemap[0][0])

    def test_pause_no_next(self) -> None:
        """
        Test if the chunk cannot tell its stream to pause if it is at the cursor position.
        """
        result = self.chunk.pause()

        self.assertFalse(result)

    def test_pause_already_paused(self) -> None:
        """
        Test if the chunk cannot tell its stream to pause if its chunk is already paused.
        """
        self.chunk.stream.cursorpiecemap[0][0] = True

        result = self.chunk.pause()

        self.assertFalse(result)

    def test_resume(self) -> None:
        """
        Test if the chunk can tell its stream to resume.
        """
        self.chunk.stream.cursorpiecemap[0] = [True, [0]]
        self.chunk.stream.cursorpiecemap[1] = [True, [1]]

        result = self.chunk.resume()

        self.assertTrue(result)
        self.assertFalse(self.chunk.stream.cursorpiecemap[0][0])

    def test_resume_no_next(self) -> None:
        """
        Test if the chunk can tell its stream to resume even if it is at the cursor position.
        """
        self.chunk.stream.cursorpiecemap[0] = [True, []]

        result = self.chunk.resume()

        self.assertTrue(result)

    def test_resume_not_paused(self) -> None:
        """
        Test if the chunk cannot tell its stream to resume if its chunk is not paused.
        """
        result = self.chunk.resume()

        self.assertFalse(result)


class TestStream(TestBase):
    """
    Tests for the Stream class.
    """

    def create_mock_download(self) -> Download:
        """
        Create a mocked DownloadConfig.
        """
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        conf = ConfigObj()
        conf.configspec = defaults
        conf.validate(Validator())
        config = DownloadConfig(conf)
        config.set_dest_dir(Path(""))
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), None, config,
                            checkpoint_disabled=True)
        download.handle = Mock(is_valid=Mock(return_value=True), file_priorities=Mock(return_value=[0] * 6),
                               torrent_file=Mock(return_value=download.tdef.torrent_info))
        download.lt_status = Mock(state=3, paused=False, pieces=[])
        return download

    def convert_to_piece_size(self, download: Download, piece_size: int) -> None:
        """
        Convert the mock download to use a different piece size.

        Don't call this with anything other than the download from create_mock_download().

        The pieces are 20 byte hashes for the number of pieces in a 6-byte file per 6 files.
        """
        download.tdef.metainfo[b'info'][b'piece length'] = piece_size
        download.tdef.torrent_parameters[b'piece length'] = piece_size
        download.tdef.metainfo[b'info'][b'pieces'] = b"\x01" * 20 * (6 // piece_size) * 6
        download.tdef.invalidate_torrent_info()

    async def test_enable(self) -> None:
        """
        Test if a stream can be enabled without known pieces.
        """
        stream = Stream(self.create_mock_download())

        await stream.enable(fileindex=0)

        self.assertEqual(Path("torrent_create") / "abc" / "file2.txt", stream.filename)
        self.assertEqual(0, stream.firstpiece)
        self.assertEqual(-1, stream.lastpiece)

    async def test_enable_have_pieces(self) -> None:
        """
        Test if a stream can be enabled when we already have pieces.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False]
        stream = Stream(download)

        await stream.enable(fileindex=0)

        self.assertEqual(Path("torrent_create") / "abc" / "file2.txt", stream.filename)
        self.assertEqual(0, stream.firstpiece)
        self.assertEqual(0, stream.lastpiece)

    async def test_bytes_to_pieces(self) -> None:
        """
        Test if we can get the pieces from byte indices.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False, True]
        self.convert_to_piece_size(download, 3)
        stream = Stream(download)
        await stream.enable(fileindex=0)

        for i in range(7):
            self.assertEqual(i // 3, stream.bytetopiece(i))
        self.assertEqual([0, 1], stream.bytestopieces(0, 6))

    async def test_calculateprogress_empty(self) -> None:
        """
        Test if progress can be calculated without requested pieces.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False]
        stream = Stream(download)
        await stream.enable(fileindex=0)

        self.assertEqual(1.0, stream.calculateprogress([], False))

    async def test_calculateprogress_not_done(self) -> None:
        """
        Test if progress can be calculated without for a given piece that is not done.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False]
        stream = Stream(download)
        await stream.enable(fileindex=0)

        self.assertEqual(0.0, stream.calculateprogress([0], False))

    async def test_calculateprogress_done(self) -> None:
        """
        Test if progress can be calculated without for a given piece that is done.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [True]
        stream = Stream(download)
        await stream.enable(fileindex=0)

        self.assertEqual(1.0, stream.calculateprogress([0], False))

    async def test_calculateprogress_partial(self) -> None:
        """
        Test if progress can be calculated without for two pieces of which one is done and one is not.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False, True]
        self.convert_to_piece_size(download, 3)
        stream = Stream(download)
        await stream.enable(fileindex=0)

        self.assertEqual(0.5, stream.calculateprogress([0, 1], False))

    async def test_updateprios_no_headers_all_missing(self) -> None:
        """
        Test if priorities are set to retrieve missing pieces.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False] * 12
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)

        await stream.updateprios()

        self.assertEqual(call([7, 7, 7] + [0] * 9), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_no_headers_single_missing(self) -> None:
        """
        Test if priorities are set to retrieve a missing piece.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False] + [True] * 11
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)

        await stream.updateprios()

        self.assertEqual(call([7] + [0] * 11), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_no_headers_sparse(self) -> None:
        """
        Test if priorities can be updated for sparesely retrieved pieces.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False, True] * 6
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)

        await stream.updateprios()

        self.assertEqual(call([7, 0, 7, 0] + [0] * 8), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_headers_all_missing(self) -> None:
        """
        Test if priorities are set to retrieve missing headers before anything else.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False] * 12
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)
        stream.headerpieces = [0]
        stream.footerpieces = [11]

        await stream.updateprios()

        self.assertEqual(call([7] + [0] * 11), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_footer_missing(self) -> None:
        """
        Test if priorities are set to retrieve the first pieces with less priority if the footer is missing.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [True] + [False] * 11
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)
        stream.headerpieces = [0]
        stream.footerpieces = [11]

        await stream.updateprios()

        self.assertEqual(call([0, 1, 1] + [0] * 9), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_header_footer_available(self) -> None:
        """
        Test if priorities are set to retrieve the first pieces with less priority if the header and footer are there.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [True] + [False] * 10 + [True]
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)
        stream.headerpieces = [0]
        stream.footerpieces = [11]

        await stream.updateprios()

        self.assertEqual(call([0, 1, 1] + [0] * 9), download.handle.prioritize_pieces.call_args)

    async def test_updateprios_header_footer_prebuffer(self) -> None:
        """
        Test if priorities are set to retrieve the prebuffer pieces with higher priority.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [True] + [False] * 10 + [True]
        self.convert_to_piece_size(download, 3)
        download.handle.piece_priorities = Mock(return_value=[0] * 12)  # 6 files, 2 pieces per file
        stream = Stream(download)
        await stream.enable(fileindex=0)
        stream.headerpieces = [0]
        stream.prebuffpieces = [2, 3, 4]
        stream.footerpieces = [11]

        await stream.updateprios()

        self.assertEqual(call([0, 1, 7] + [0] * 9), download.handle.prioritize_pieces.call_args)

    async def test_resetprios_default(self) -> None:
        """
        Test if streams can be reset to the default priority (4) for all pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(fileindex=0)

        stream.resetprios()

        self.assertEqual(call([4]), download.handle.prioritize_pieces.call_args)

    async def test_resetprios_prio(self) -> None:
        """
        Test if streams can be reset to the given priority for all pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(fileindex=0)

        stream.resetprios(prio=6)

        self.assertEqual(call([6]), download.handle.prioritize_pieces.call_args)

    async def test_resetprios_given(self) -> None:
        """
        Test if streams can be reset to the given priority for a given pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(fileindex=0)

        stream.resetprios(pieces=[0], prio=6)

        self.assertEqual(call([6]), download.handle.prioritize_pieces.call_args)
