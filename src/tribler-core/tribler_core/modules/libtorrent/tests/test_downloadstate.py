from tribler_common.simpledefs import (
    DLSTATUS_DOWNLOADING,
    DLSTATUS_EXIT_NODES,
    DLSTATUS_WAITING4HASHCHECK,
    DOWNLOAD,
    UPLOAD,
)

from tribler_core.modules.libtorrent.download_state import DownloadState
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest


class TestDownloadState(TriblerCoreTest):
    """
    This class contains tests for the download state.
    """

    async def setUp(self):
        await TriblerCoreTest.setUp(self)
        self.mock_download = MockObject()
        self.mocked_tdef = MockObject()
        self.mocked_tdef.get_name = lambda: "test"
        self.mocked_tdef.get_length = lambda: 43
        self.mock_download.get_def = lambda: self.mocked_tdef

        self.mock_transferred = MockObject()
        self.mock_transferred.upTotal = 5
        self.mock_transferred.downTotal = 6
        self.mock_transferred.numConInitiated = 10
        self.mock_transferred.numSeeds = 11
        self.mock_transferred.numPeers = 12

    def test_getters_setters_1(self):
        """
        Testing various getters and setters in DownloadState
        """
        self.mock_download.get_peerlist = lambda: []
        self.mock_download.session = MockObject()
        self.mock_download.session = MockObject()
        self.mock_download.session.tunnel_community = MockObject()
        self.mock_download.session.tunnel_community.get_candidates = lambda _: []
        self.mock_download.config = MockObject()
        self.mock_download.config.get_hops = lambda: 0
        download_state = DownloadState(self.mock_download, None, None)

        self.assertEqual(download_state.get_download(), self.mock_download)
        self.assertEqual(download_state.get_progress(), 0)
        self.assertEqual(download_state.get_status(), DLSTATUS_WAITING4HASHCHECK)
        self.assertIsNone(download_state.get_error())
        self.assertEqual(download_state.get_current_speed(UPLOAD), 0)
        self.assertEqual(download_state.get_total_transferred(UPLOAD), 0)
        self.assertEqual(download_state.get_num_seeds_peers(), (0, 0))
        self.assertEqual(download_state.get_peerlist(), [])

        self.mock_download.config.get_hops = lambda: 1
        download_state = DownloadState(self.mock_download, None, None)
        self.assertEqual(download_state.get_status(), DLSTATUS_EXIT_NODES)

    def test_getters_setters_2(self):
        """
        Testing various getters and setters in DownloadState
        """
        lt_status = MockObject()
        lt_status.state = 3
        lt_status.upload_rate = 123
        lt_status.download_rate = 43
        lt_status.total_upload = 100
        lt_status.total_download = 200
        lt_status.all_time_upload = 100
        lt_status.all_time_download = 200
        lt_status.list_peers = 10
        lt_status.list_seeds = 5
        lt_status.progress = 0.75
        lt_status.error = False
        lt_status.paused = False
        lt_status.state = 3
        lt_status.num_pieces = 0
        lt_status.pieces = []
        lt_status.finished_time = 10

        download_state = DownloadState(self.mock_download, lt_status, None)

        self.assertEqual(download_state.get_status(), DLSTATUS_DOWNLOADING)
        self.assertEqual(download_state.get_current_speed(UPLOAD), 123)
        self.assertEqual(download_state.get_current_speed(DOWNLOAD), 43)
        self.assertEqual(download_state.get_total_transferred(UPLOAD), 100)
        self.assertEqual(download_state.get_total_transferred(DOWNLOAD), 200)
        self.assertEqual(download_state.get_seeding_ratio(), 0.5)
        self.assertEqual(download_state.get_eta(), 0.25)
        self.assertEqual(download_state.get_num_seeds_peers(), (5, 5))
        self.assertEqual(download_state.get_pieces_complete(), [])
        self.assertEqual(download_state.get_pieces_total_complete(), (0, 0))
        self.assertEqual(download_state.get_seeding_time(), 10)

        lt_status.num_pieces = 6
        lt_status.pieces = [1, 1, 1, 0, 0, 0]
        self.assertEqual(download_state.get_pieces_complete(), [1, 1, 1, 0, 0, 0])
        self.assertEqual(download_state.get_pieces_total_complete(), (6, 3))

        self.mock_download.config = MockObject()
        self.mock_download.config.get_selected_files = lambda: ['test']
        self.assertEqual(download_state.get_selected_files(), ['test'])
        self.assertEqual(download_state.get_progress(), 0.75)

    def test_get_files_completion(self):
        """
        Testing whether the right completion of files is returned
        """
        self.mocked_tdef.get_files_with_length = lambda: [("test.txt", 100)]

        handle = MockObject()
        handle.file_progress = lambda **_: [60]
        handle.is_valid = lambda: True
        self.mock_download.handle = handle

        download_state = DownloadState(self.mock_download, MockObject(), None)
        self.assertEqual(download_state.get_files_completion(), [('test.txt', 0.6)])
        handle.file_progress = lambda **_: [0]
        self.assertEqual(download_state.get_files_completion(), [('test.txt', 0.0)])
        handle.file_progress = lambda **_: [100]
        self.assertEqual(download_state.get_files_completion(), [('test.txt', 1.0)])
        self.mocked_tdef.get_files_with_length = lambda: []
        handle.file_progress = lambda **_: []
        self.assertEqual(download_state.get_files_completion(), [])

        # Test a file with a length of zero
        self.mocked_tdef.get_files_with_length = lambda: [("test.txt", 0)]
        handle.file_progress = lambda **_: [0]
        self.assertEqual(download_state.get_files_completion(), [('test.txt', 1.0)])

    def test_get_availability(self):
        """
        Testing whether the right availability of a file is returned
        """
        mock_ltstate = MockObject()
        mock_ltstate.pieces = [True]
        download_state = DownloadState(self.mock_download, mock_ltstate, 0.6)
        download_state.get_peerlist = lambda: []

        self.assertEqual(download_state.get_availability(), 0)
        download_state.get_peerlist = lambda: [{'completed': 1.0}]
        self.assertEqual(download_state.get_availability(), 1.0)
        download_state.get_peerlist = lambda: [{'completed': 0.6}]
        self.assertEqual(download_state.get_availability(), 0.0)
        download_state.lt_status.pieces = [0, 0, 0, 0, 0]
        download_state.get_peerlist = lambda: [{'completed': 0}, {'have': [1, 1, 1, 1, 0]}]
        self.assertEqual(download_state.get_availability(), 0.8)

        # Test whether inaccurate piece information from other peers is ignored
        download_state.get_peerlist = lambda: [{'completed': 0.5, 'have': [1, 0]},
                                               {'completed': 0.9, 'have': [1, 0, 1]}]
        self.assertEqual(download_state.get_availability(), 0.0)
