from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, UPLOAD, DOWNLOAD, DLSTATUS_STOPPED, DLSTATUS_SEEDING, \
    DLSTATUS_STOPPED_ON_ERROR, DLSTATUS_WAITING4HASHCHECK
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject


class TestDownloadState(TriblerCoreTest):
    """
    This class contains tests for the download state.
    """

    def setUp(self, annotate=True):
        TriblerCoreTest.setUp(self, annotate=annotate)
        self.mock_download = MockObject()
        mocked_tdef = MockObject()
        mocked_tdef.get_name = lambda: "test"
        mocked_tdef.get_length = lambda _: 43
        self.mock_download.get_def = lambda: mocked_tdef

        self.mock_transferred = MockObject()
        self.mock_transferred.upTotal = 5
        self.mock_transferred.downTotal = 6
        self.mock_transferred.numConInitiated = 10
        self.mock_transferred.numSeeds = 11
        self.mock_transferred.numPeers = 12

    def test_init(self):
        """
        Testing the init method of DownloadState
        """
        download_state = DownloadState(self.mock_download, DLSTATUS_DOWNLOADING, "error", 0.5)
        self.assertEqual(download_state.get_error(), "error")

        download_state = DownloadState(self.mock_download, DLSTATUS_SEEDING, None, 0.5)
        self.assertEqual(download_state.get_status(), DLSTATUS_SEEDING)

        download_state = DownloadState(self.mock_download, DLSTATUS_SEEDING, "error", 0.5, stats={})
        self.assertEqual(download_state.get_status(), DLSTATUS_STOPPED_ON_ERROR)

        download_state = DownloadState(self.mock_download, DLSTATUS_WAITING4HASHCHECK, None, 0.5, stats={})
        self.assertEqual(download_state.get_progress(), 0.0)

        download_state = DownloadState(self.mock_download, DLSTATUS_STOPPED, None, 0.5, stats={'frac': 0.6})
        self.assertEqual(download_state.get_progress(), 0.6)

    def test_getters_setters_1(self):
        """
        Testing various getters and setters in DownloadState
        """
        download_state = DownloadState(self.mock_download, DLSTATUS_DOWNLOADING, None, 0.5)
        self.assertEqual(download_state.get_download(), self.mock_download)
        self.assertEqual(download_state.get_progress(), 0.5)
        self.assertEqual(download_state.get_status(), DLSTATUS_DOWNLOADING)
        self.assertIsNone(download_state.get_error())

        self.assertEqual(download_state.get_current_speed(UPLOAD), 0)
        self.assertEqual(download_state.get_total_transferred(UPLOAD), 0)
        self.assertEqual(download_state.get_num_peers(), 0)
        self.assertEqual(download_state.get_num_nonseeds(), 0)
        self.assertEqual(download_state.get_num_seeds_peers(), (0, 0))
        self.assertEqual(download_state.get_vod_prebuffering_progress_consec(), 0)
        self.assertEqual(download_state.get_vod_prebuffering_progress(), 0)
        download_state.status = DLSTATUS_STOPPED
        download_state.progress = 1.0
        self.assertEqual(download_state.get_vod_prebuffering_progress_consec(), 1.0)
        self.assertEqual(download_state.get_vod_prebuffering_progress(), 1.0)
        self.assertFalse(download_state.is_vod())
        self.assertEqual(download_state.get_peerlist(), [])
        self.assertEqual(download_state.get_tracker_status(), {})

    def test_getters_setters_2(self):
        """
        Testing various getters and setters in DownloadState
        """
        download_state = DownloadState(self.mock_download, DLSTATUS_DOWNLOADING, None, 0.5)
        stats = {'up': 123, 'down': 1234, 'stats': self.mock_transferred, 'time': 42, 'vod_prebuf_frac_consec': 43,
                 'vod_prebuf_frac': 44, 'vod': True, 'tracker_status': {'a': 'b'}}
        download_state.stats = stats
        self.assertEqual(download_state.get_current_speed(UPLOAD), 123)
        self.assertEqual(download_state.get_current_speed(DOWNLOAD), 1234)
        self.assertEqual(download_state.get_total_transferred(UPLOAD), 5)
        self.assertEqual(download_state.get_total_transferred(DOWNLOAD), 6)
        self.assertEqual(download_state.get_vod_prebuffering_progress_consec(), 43)
        self.assertTrue(download_state.is_vod())
        self.assertEqual(download_state.get_tracker_status(), {'a': 'b'})

        seeding_stats = {'total_down': 8, 'total_up': 9, 'ratio': 0.42}
        download_state.set_seeding_statistics(seeding_stats)
        self.assertEqual(download_state.get_seeding_statistics(), seeding_stats)
        self.assertEqual(download_state.seeding_downloaded, 8)
        self.assertEqual(download_state.seeding_uploaded, 9)
        self.assertEqual(download_state.seeding_ratio, 0.42)

        self.assertEqual(download_state.get_eta(), 42)
        self.assertEqual(download_state.get_num_con_initiated(), 10)
        self.assertEqual(download_state.get_num_peers(), 23)
        self.assertEqual(download_state.get_num_nonseeds(), 12)
        self.assertEqual(download_state.get_num_seeds_peers(), (11, 12))

        self.assertEqual(download_state.get_pieces_complete(), [])
        self.assertEqual(download_state.get_pieces_total_complete(), (0, 0))
        download_state.haveslice = [1, 2, 3]
        self.assertEqual(download_state.get_pieces_complete(), [1, 2, 3])
        self.assertEqual(download_state.get_pieces_total_complete(), (3, 6))

        self.mock_download.get_selected_files = lambda: ['test']
        self.assertEqual(download_state.get_selected_files(), ['test'])
        self.assertEqual(download_state.get_length(), 43)

    def test_get_files_completion(self):
        """
        Testing whether the right completion of files is returned
        """
        self.mock_download.get_selected_files = lambda: [['test.txt', 42]]
        download_state = DownloadState(self.mock_download, DLSTATUS_DOWNLOADING, None, 0.6)
        self.assertEqual(download_state.get_files_completion(), [(['test.txt', 42], 0.6)])
        download_state.filepieceranges = [(5, 10, None, ['test.txt', 42])]
        self.assertEqual(download_state.get_files_completion(), [(['test.txt', 42], 0.0)])
        download_state.progress = 1.0
        self.assertEqual(download_state.get_files_completion(), [(['test.txt', 42], 1.0)])
        self.mock_download.get_selected_files = lambda: [['test.txt', 42], ['test2.txt', 43]]
        self.assertEqual(download_state.get_files_completion(), [(['test.txt', 42], 1.0)])

    def test_get_availability(self):
        """
        Testing whether the right availability of a file is returned
        """
        download_state = DownloadState(self.mock_download, DLSTATUS_DOWNLOADING, None, 0.6)
        download_state.stats = {'spew': [{}]}
        self.assertEqual(download_state.get_availability(), 0)
        download_state.stats = {'spew': [{'completed': 1.0}]}
        self.assertEqual(download_state.get_availability(), 1.0)
        download_state.stats = {'spew': [{'completed': 0.6}]}
        self.assertEqual(download_state.get_availability(), 0.0)
