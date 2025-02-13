from __future__ import annotations

import logging
import math
from asyncio import sleep
from typing import TYPE_CHECKING

from tribler.core.libtorrent.download_manager.download_state import DownloadStatus

if TYPE_CHECKING:
    from collections.abc import Generator
    from io import BufferedReader
    from pathlib import Path
    from types import TracebackType

    from typing_extensions import Self

    from tribler.core.libtorrent.download_manager.download import Download

# Before streaming starts, we first download the header/footer of the file.
HEADER_SIZE = 5 * 1024 * 1024
FOOTER_SIZE = 1 * 1024 * 1024
# Buffer size as percentage of the file size
BUFFER_PERCENT = 0.05
# Deadlines to be used for pieces that are at the current file cursor position
DEADLINE_PRIO_MAP = [7, 6, 6, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]


class NotStreamingError(Exception):
    """
    An attempt was made to create a chunk for no stream.
    """


class NoAvailableStreamError(Exception):
    """
    An attempt was made to create a stream for no files.
    """


class Stream:
    """
    Holds the streaming status of a specific download.
    """

    def __init__(self, download: Download) -> None:
        """
        Create a stream for the given download.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.download = download
        self.file_index: int = 0
        self.file_size: int = 0
        self.file_name: Path | None = None
        self.buffer_size: int = 0
        self.piece_length: int = 0
        self.cursor_pieces: dict[int, list[int]] = {}

    async def enable(self, file_index: int = 0,
                     buffer_position: int | None = None, buffer_percent: float = BUFFER_PERCENT,
                     header_size: int = HEADER_SIZE, footer_size: int = FOOTER_SIZE) -> None:
        """
        Sets the file index and waits for initial buffering  to be completed.
        """
        # Check if the file index exists
        files = self.download.get_def().get_files_with_length()
        if file_index >= len(files) or file_index < 0:
            raise NoAvailableStreamError

        # Set the new file
        self.file_index = file_index
        filename, self.file_size = files[file_index]
        content_dest = self.download.get_content_dest()
        self.file_name = content_dest / filename if self.download.get_def().is_multifile_torrent() else content_dest
        self.buffer_size = int(self.file_size * buffer_percent)
        self.piece_length = self.download.get_def().get_piece_length()

        # Ensure the download isn't paused
        self.download.resume()

        # Wait until the download is in the correct state
        status = self.download.get_state().get_status()
        while status not in [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING]:
            await sleep(1)
            status = self.download.get_state().get_status()

        # Give the selected file a high priority
        file_priorities = self.download.get_file_priorities()
        file_priorities[file_index] = 7
        self.download.set_file_priorities(file_priorities)

        # Check if buffer/header/footer needs downloading.
        pieces_needed = []
        if buffer_position is not None:
            pieces_needed += self.bytes_to_pieces(buffer_position, buffer_position + self.buffer_size - 1)
        if header_size:
            pieces_needed += self.bytes_to_pieces(0, header_size - 1)
        if footer_size:
            pieces_needed += self.bytes_to_pieces(self.file_size - footer_size, self.file_size - 1)
        if self.pieces_complete(pieces_needed):
            # Nothing to do here. Buffering is completed.
            return

        # Starting buffering
        priorities = self.download.get_piece_priorities()
        for piece in self.iter_pieces(have=False):
            if piece in pieces_needed:
                priorities[piece] = 7
                self.download.set_piece_deadline(piece, 0)
            else:
                # We don't use prio < 1, as that causes the download progress to jump up and down in the UI
                priorities[piece] = 1
        self.download.set_piece_priorities(priorities)

        # Wait until completed
        await self.wait_for_pieces(pieces_needed)

    def iter_pieces(self, have: bool | None = None, start_from: int | None = None) -> Generator[int, None, None]:
        """
        Generator function that yield the pieces for the active file index.
        """
        pieces_have = self.download.get_state().get_pieces_complete()
        first_piece = self.byte_to_piece(0)
        last_piece = min(self.byte_to_piece(self.file_size - 1), len(pieces_have) - 1)

        for piece in range(first_piece, last_piece + 1):
            if start_from is not None and piece < start_from:
                continue
            if have is None or (have and pieces_have[piece]) or (not have and not pieces_have[piece]):
                yield piece

    async def wait_for_pieces(self, pieces_needed: list[int]) -> None:
        """
        Waits until the specified pieces have been completed.
        """
        while not self.pieces_complete(pieces_needed):
            await sleep(1)

    def pieces_complete(self, pieces: list[int]) -> bool:
        """
        Checks if the specified pieces have been completed.
        """
        have = self.download.get_state().get_pieces_complete()
        return all(have[piece] for piece in pieces)

    def bytes_to_pieces(self, bytes_begin: int, bytes_end: int) -> list[int]:
        """
        Returns the pieces that represents the given byte range.
        """
        pieces_have = self.download.get_state().get_pieces_complete()
        first_piece = self.byte_to_piece(0)
        last_piece = min(self.byte_to_piece(self.file_size - 1), len(pieces_have) - 1)

        bytes_begin = max(bytes_begin, 0)
        bytes_end = min(bytes_end, self.file_size - 1)
        start_piece = max(self.byte_to_piece(bytes_begin), first_piece)
        end_piece = min(self.byte_to_piece(bytes_end), last_piece)
        return list(range(start_piece, end_piece + 1))

    def byte_to_piece(self, byte_begin: int) -> int:
        """
        Finds the piece position that begin_bytes is mapped to.
        """
        return self.download.get_def().torrent_info.map_file(self.file_index, byte_begin, 0).piece

    def update_priorities(self) -> None:
        """
        Sets the piece priorities and deadlines according to the cursors of the outstanding stream requests.
        """
        if not (piece_priorities := self.download.get_piece_priorities()):
            return

        # Iterate over all pieces that have not yet been downloaded, and determine their appropriate priority/deadline.
        for piece in self.iter_pieces(have=False):
            deadline = None
            for pieces in self.cursor_pieces.values():
                if piece in pieces and (deadline is None or pieces.index(piece) < deadline):
                    deadline = pieces.index(piece)
                    break

            if deadline is not None and deadline < len(DEADLINE_PRIO_MAP):
                # Starting at the position of the cursor, set priorities according to DEADLINE_PRIO_MAP
                if piece_priorities[piece] != DEADLINE_PRIO_MAP[deadline]:
                    self.download.set_piece_deadline(piece, deadline * 10)
                piece_priorities[piece] = DEADLINE_PRIO_MAP[deadline]
            elif deadline is not None:
                # Set the pieces that are within the buffer to a lower priority
                if piece_priorities[piece] != 1:
                    self.download.set_piece_deadline(piece, deadline * 10)
                piece_priorities[piece] = 1
            else:
                # All other pieces get the lowest priority
                if piece_priorities[piece] != 1:
                    self.download.reset_piece_deadline(piece)
                piece_priorities[piece] = 1

        self.download.set_piece_priorities(piece_priorities)

    def reset_priorities(self, pieces: list[int] | None = None, priority: int = 4) -> None:
        """
        Resets the priorities and deadlines of pieces.
        If no pieces are provided reset all pieces within the current file.
        """
        piece_priorities = self.download.get_piece_priorities()
        if pieces is None:
            pieces = list(range(len(piece_priorities)))
        for piece in pieces:
            self.download.reset_piece_deadline(piece)
        self.download.set_piece_priorities([priority] * len(pieces))
        file_priorities = self.download.get_file_priorities()
        file_priorities[self.file_index] = 4
        self.download.set_file_priorities(file_priorities)

    def close(self) -> None:
        """
        Closes the Stream.
        """
        self.cursor_pieces.clear()
        self.reset_priorities()


class StreamReader:
    """
    File-like object that reads a file from a torrent, and controls the dynamic buffer of the
    stream instance according to read position.
    """

    def __init__(self, stream: Stream, start_offset: int = 0) -> None:
        """
        Creates a new StreamChunk.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.stream = stream
        self.file: BufferedReader | None = None
        self.start_offset = self.seek_offset = start_offset

    async def __aenter__(self) -> Self:
        """
        Opens the chunk.
        """
        await self.open()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None,
                        traceback: TracebackType | None) -> None:
        """
        Closes the chunk.
        """
        self.close()

    async def open(self) -> None:
        """
        Opens the file in the filesystem until its ready and seeks to seek_offset.
        """
        if self.stream.file_name is None:
            raise NotStreamingError

        while not self.stream.file_name.exists():
            await sleep(1)

        self.file = open(self.stream.file_name, "rb")  # noqa: SIM115, ASYNC230
        self.file.seek(self.seek_offset)

        # If we seek multiple times in a row, the video player will keep all connections open until the required
        # pieces have been downloaded. This considerably slows down the final and most important request.
        # To avoid issues, we allow only 1 connection at a time. By clearing cursor_pieces, the read functions of
        # the other connections will return b"", caused the DownloadsEndpoint to drop the connections.
        self.stream.cursor_pieces.clear()

    async def seek(self, byte_offset: int) -> None:
        """
        Seeks the stream to the related piece that represents the position byte.
        Also updates the dynamic buffer accordingly.
        """
        # Find and store the pieces that we need at the given offset
        piece_offset = self.stream.byte_to_piece(byte_offset)
        num_pieces = math.ceil(self.stream.buffer_size / self.stream.piece_length)
        pieces = list(self.stream.iter_pieces(have=False, start_from=piece_offset))[:num_pieces]
        self.stream.cursor_pieces[self.start_offset] = pieces

        # Update the torrent priorities
        self.stream.update_priorities()

        # Update the file cursor
        if self.file:
            self.seek_offset = byte_offset
            self.file.seek(self.seek_offset)

    async def read(self) -> bytes:
        """
        Reads piece_length bytes starting from the current seek position.
        """
        # Do we need to stop reading?
        if self.start_offset not in self.stream.cursor_pieces or not self.file:
            return b""

        await self.seek(self.seek_offset)
        piece = self.stream.byte_to_piece(self.seek_offset)
        self._logger.debug('Chunk %s: Get piece %s', self.start_offset, piece)

        # Note the even though we're reading piece_length at a time, that doesn't mean that we only need 1 piece.
        pieces_needed = self.stream.bytes_to_pieces(self.seek_offset, self.seek_offset + self.stream.piece_length)
        await self.stream.wait_for_pieces(pieces_needed)

        # Using libtorrent's `read_piece` is too slow for our purposes, so we read the data from disk.
        result = self.file.read(self.stream.piece_length)
        self._logger.debug('Chunk %s: Got bytes %s-%s, piecelen: %s',
                           self.start_offset, self.seek_offset, self.seek_offset + len(result),
                           self.stream.piece_length)
        self.seek_offset = self.file.tell()
        return result

    def close(self) -> None:
        """
        Closes the reader amd unregisters the cursor pieces from the stream instance
        and resets the relevant piece priorities.
        """
        if self.file:
            self.file.close()
            self.file = None

        pieces = self.stream.cursor_pieces.pop(self.start_offset, None)
        if pieces:
            self.stream.reset_priorities(pieces)
