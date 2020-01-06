from unittest.mock import Mock

from tribler_core.modules.libtorrent.stream import Stream
from tribler_core.tests.tools.base_test import TriblerCoreTest


class TestStream(TriblerCoreTest):
    """
    This class contains tests for the download state.
    """

    async def setUp(self):
        await TriblerCoreTest.setUp(self)

        download = Mock()
        download.handle.torrent_file.return_value.file_at.return_value = Mock(size=250)
        self.stream = Stream(download, 0)

    def test_get_file_size(self):
        """
        Testing whether the right file size is returned
        """
        self.assertEqual(self.stream.file_size, 250)

    def test_get_piece_progress(self):
        """
        Testing whether the right piece progress is returned
        """
        self.assertEqual(self.stream.get_piece_progress(None), 1.0)

        self.stream.download.get_state.return_value.get_pieces_complete.return_value = [True, False]
        self.assertEqual(self.stream.get_piece_progress([0, 1], True), 0.5)

        self.stream.download.get_state.return_value.get_pieces_complete.return_value = []
        self.assertEqual(self.stream.get_piece_progress([3, 1]), 0.0)

    def test_get_byte_progress(self):
        """
        Testing whether the right byte progress is returned
        """
        self.assertEqual(self.stream.get_byte_progress([(-1, 0, 0)], False), 1.0)

        # Scenario: we have a file with 4 pieces, 250 bytes in each piece.
        self.stream.info.map_file = lambda _, start_byte, __: Mock(piece=int(start_byte / 250))
        self.stream.info.num_pieces.return_value = 4
        self.stream.info.file_at.return_value = Mock(size=1000)
        self.stream.download.get_state.return_value.get_pieces_complete.return_value = [True, False, False, False]
        self.assertEqual(self.stream.get_byte_progress([(0, 10, 270)], True), 0.5)

    def test_priority_reset(self):
        """
        Testing whether the priorities get reset to their original values after stream is completed
        """
        self.stream.info.map_file = lambda _, start_byte, __: Mock(piece=int(start_byte / 250))
        self.stream.info.num_pieces.return_value = 4
        self.stream.download.get_piece_priorities.return_value = []
        self.stream.download.get_state.return_value.get_pieces_complete.return_value = []

        file_priorities = [1, 1, 0, 1]
        self.stream.download.get_file_priorities.return_value = file_priorities

        self.stream.set_vod_mode(True)
        self.assertEqual(self.stream.file_priorities, file_priorities)

        self.stream.close()
        self.stream.download.set_file_priorities.assert_called_once_with(file_priorities)
