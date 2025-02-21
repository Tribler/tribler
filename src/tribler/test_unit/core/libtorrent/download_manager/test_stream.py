from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call

from configobj import ConfigObj
from ipv8.test.base import TestBase
from validate import Validator

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.stream import NoAvailableStreamError, Stream, StreamReader
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT
from tribler.test_unit.mocks import MockTriblerConfigManager


class MockStreamReader(StreamReader):
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

        self.chunk = MockStreamReader(Mock(), 0)
        self.chunk.stream.cursor_pieces = {0: []}

    def create_mock_content(self, content: bytes, piece_length: int = 1) -> None:
        """
        Set the value of the stream to certain content.
        """
        content_end = len(content) // piece_length
        self.chunk.stream.iter_pieces = lambda have, start_from: list(range(start_from, content_end))
        self.chunk.stream.wait_for_pieces = AsyncMock()
        self.chunk.stream.byte_to_piece = lambda x: x // piece_length
        self.chunk.stream.buffer_size = 1
        self.chunk.stream.piece_length = piece_length
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

    async def test_read_closed(self) -> None:
        """
        Test if all bytes can be read from a chunk when it's closed.
        """
        self.create_mock_content(b"content", len(b"content"))
        self.chunk.close()

        async with self.chunk:
            value = await self.chunk.read()

        self.assertEqual(b"", value)

    async def test_read_empty(self) -> None:
        """
        Test if all bytes can be read from a chunk when it has no data.
        """
        self.chunk.stream.iter_pieces = Mock(return_value=[])
        self.chunk.stream.buffer_size = self.chunk.stream.piece_length = 1
        self.chunk.stream.wait_for_pieces = AsyncMock()
        self.chunk.stream.byte_to_piece = Mock(return_value=-1)

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

        await self.chunk.seek(3)

        streamed = b""
        async with self.chunk:
            for _ in range(len(b"tent")):
                streamed += await self.chunk.read()

        self.assertEqual(b"tent", streamed)


class TestStream(TestBase):
    """
    Tests for the Stream class.
    """

    dlmngr = Mock(config=MockTriblerConfigManager())

    def create_mock_download(self, piece_size: int | None = None, pieces: list[bool] | None = None) -> Download:
        """
        Create a mocked DownloadConfig.
        """
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        conf = ConfigObj()
        conf.configspec = defaults
        conf.validate(Validator())
        config = DownloadConfig(conf)
        config.set_dest_dir(Path(""))
        download = Download(TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT), self.dlmngr, config,
                            checkpoint_disabled=True)
        download.handle = Mock(is_valid=Mock(return_value=True), file_priorities=Mock(return_value=[0] * 6),
                               torrent_file=Mock(return_value=download.tdef.torrent_info))
        download.lt_status = Mock(state=3, paused=False, error=None, pieces=[])
        if piece_size is not None:
            self.convert_to_piece_size(download, piece_size)
        if pieces is not None:
            download.lt_status.pieces = pieces
            download.handle.piece_priorities = Mock(return_value=[0] * len(pieces))
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
        await stream.enable(file_index=0)

        self.assertEqual(Path("torrent_create") / "abc" / "file2.txt", stream.file_name)
        self.assertEqual(6, stream.file_size)

    async def test_enable_unknown_file_index(self) -> None:
        """
        Test if trying to enable a stream with an unknown file index produces an error.
        """
        stream = Stream(self.create_mock_download())
        with self.assertRaises(NoAvailableStreamError):
            await stream.enable(file_index=6)

    async def test_enable_no_buffering(self) -> None:
        """
        Test if a stream can be enabled without buffering.
        """
        download = self.create_mock_download()
        stream = Stream(download)
        await stream.enable(file_index=0, header_size=0, footer_size=0)

        download.handle.prioritize_pieces.assert_not_called()

    async def test_enable_header_footer(self) -> None:
        """
        Test if a stream can be enabled with a header and footer.
        """
        download = self.create_mock_download(piece_size=1, pieces=[False] * 12)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, header_size=1, footer_size=1)

        self.assertEqual(call([7, 1, 1, 1, 1, 7] + [0] * 6), download.handle.prioritize_pieces.call_args)

    async def test_enable_buffer(self) -> None:
        """
        Test if a stream can be enabled with a buffer.
        """
        download = self.create_mock_download(piece_size=1, pieces=[False] * 12)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, buffer_position=2, buffer_percent=3/6, header_size=0, footer_size=0)

        self.assertEqual(call([1, 1, 7, 7, 7, 1] + [0] * 6), download.handle.prioritize_pieces.call_args)

    async def test_enable_have_pieces(self) -> None:
        """
        Test if a stream can be enabled when we already have all pieces.
        """
        download = self.create_mock_download(piece_size=1, pieces=[True] * 12)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0)

        self.assertEqual(Path("torrent_create") / "abc" / "file2.txt", stream.file_name)
        stream.wait_for_pieces.assert_not_called()

    async def test_bytes_to_pieces(self) -> None:
        """
        Test if we can get the pieces from byte indices.
        """
        download = self.create_mock_download()
        download.lt_status.pieces = [False, True]
        self.convert_to_piece_size(download, 3)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        download.handle.piece_priorities = Mock(return_value=[0, 0])
        await stream.enable(file_index=0)

        for i in range(7):
            self.assertEqual(i // 3, stream.byte_to_piece(i))
        self.assertEqual([0, 1], stream.bytes_to_pieces(0, 6))

    async def test_update_priorities_all_missing(self) -> None:
        """
        Test if priorities are set to retrieve missing pieces.
        """
        download = self.create_mock_download(piece_size=1, pieces=[False] * 12)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, header_size=0, footer_size=0)
        stream.cursor_pieces[0] = list(range(3))
        stream.update_priorities()

        self.assertEqual(call([7, 6, 6, 1, 1, 1] + [0] * 6), download.handle.prioritize_pieces.call_args)

    async def test_update_priorities_single_missing(self) -> None:
        """
        Test if priorities are set to retrieve a missing piece.
        """
        download = self.create_mock_download(piece_size=1, pieces=[False] + [True] * 11)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, header_size=0, footer_size=0)
        stream.cursor_pieces[0] = list(range(3))
        stream.update_priorities()

        self.assertEqual(call([7] + [0] * 11), download.handle.prioritize_pieces.call_args)

    async def test_update_priorities_sparse(self) -> None:
        """
        Test if priorities can be updated for sparesely retrieved pieces.
        """
        download = self.create_mock_download(piece_size=1, pieces=[False, True] * 6)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, header_size=0, footer_size=0)
        stream.cursor_pieces[0] = list(range(4))
        stream.update_priorities()

        self.assertEqual(call([7, 0, 6, 0, 1, 0] + [0] * 6), download.handle.prioritize_pieces.call_args)

    async def test_update_priorities_offset_buffer(self) -> None:
        """
        Test if priorities are set correctly if the buffer has an offset > 0.
        """
        download = self.create_mock_download(piece_size=1, pieces=[True] + [False] * 11)
        stream = Stream(download)
        stream.wait_for_pieces = AsyncMock()
        await stream.enable(file_index=0, header_size=0, footer_size=0)
        stream.cursor_pieces[2] = [2, 3, 4]
        stream.update_priorities()

        self.assertEqual(call([0, 1, 7, 6, 6, 1] + [0] * 6), download.handle.prioritize_pieces.call_args)

    async def test_reset_priorities_default(self) -> None:
        """
        Test if streams can be reset to the default priority (4) for all pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(file_index=0)

        stream.reset_priorities()

        self.assertEqual(call([4]), download.handle.prioritize_pieces.call_args)

    async def test_reset_priorities_prio(self) -> None:
        """
        Test if streams can be reset to the given priority for all pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(file_index=0)

        stream.reset_priorities(priority=6)

        self.assertEqual(call([6]), download.handle.prioritize_pieces.call_args)

    async def test_reset_priorities_given(self) -> None:
        """
        Test if streams can be reset to the given priority for a given pieces.
        """
        download = self.create_mock_download()
        download.handle.piece_priorities = Mock(return_value=[2])
        stream = Stream(download)
        await stream.enable(file_index=0)

        stream.reset_priorities(pieces=[0], priority=6)

        self.assertEqual(call([6]), download.handle.prioritize_pieces.call_args)
