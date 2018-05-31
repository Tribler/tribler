import time
import unittest

from Tribler.Test.Core.base_test import MockObject
from Tribler.community.popular.payload import TorrentHealthPayload
from Tribler.community.popular.repository import ContentRepository, DEFAULT_FRESHNESS_LIMIT


class TestContentRepository(unittest.TestCase):

    def setUp(self):
        torrent_db = MockObject()
        channel_db = MockObject()
        self.content_repository = ContentRepository(torrent_db, channel_db)

    def test_add_content(self):
        """
        Test adding and removing content works as expected.
        """
        # Initial content queue is zero
        self.assertEqual(self.content_repository.num_content(), 0, "No item expected in queue initially")

        # Add a sample content and check the size
        sample_content = ('a' * 20, 6, 3, 123456789)
        sample_content_type = 1
        self.content_repository.add_content(sample_content_type, sample_content)
        self.assertEqual(self.content_repository.num_content(), 1, "One item expected in queue")

        # Pop an item
        (content_type, content) = self.content_repository.pop_content()
        self.assertEqual(content_type, sample_content_type, "Content type should be equal")
        self.assertEqual(content, sample_content, "Content should be equal")

        # Check size again
        self.assertEqual(self.content_repository.num_content(), 0, "No item expected in queue")

    def test_get_top_torrents(self):
        """
        Test if content repository returns expected top torrents.
        """

        def get_fake_torrents(limit):
            return [[chr(x) * 20, x, 0, 1525704192] for x in range(limit)]

        self.content_repository.torrent_db.getRecentlyCheckedTorrents = get_fake_torrents

        limit = 10
        self.assertEqual(self.content_repository.get_top_torrents(limit=limit), get_fake_torrents(limit))

    def test_update_torrent(self):

        MSG_TORRENT_DB_NONE = "Torrent DB is None"

        def fake_logger_error(repo, *args):
            if args[0] == MSG_TORRENT_DB_NONE:
                repo.torrent_db_none = True
            elif 'unknown' in args[0].lower():
                repo.unknown_torrent = True
            repo.logger_error_called = True

        def update_torrent(repo, _):
            repo.update_torrent_called = True

        original_logger = self.content_repository.logger
        self.content_repository.logger.error = lambda *args, **kw: fake_logger_error(self.content_repository, *args)

        # Assume a fake torrent response
        fake_torrent_health_payload = TorrentHealthPayload('a' * 20, 10, 4, time.time())

        # Case1: torrent db is none
        self.content_repository.torrent_db = None
        self.content_repository.logger_error_called = False

        self.content_repository.update_torrent_health(fake_torrent_health_payload, peer_trust=0)
        self.assertTrue(self.content_repository.torrent_db_none)
        self.assertTrue(self.content_repository.logger_error_called)

        # Case2: torrent db does not have torrent
        self.content_repository.torrent_db = MockObject()
        self.content_repository.torrent_db.updateTorrent = lambda infohash, *args, **kw: \
            update_torrent(self.content_repository, infohash)
        self.content_repository.logger_error_called = False
        self.content_repository.has_torrent = lambda infohash: False

        self.content_repository.update_torrent_health(fake_torrent_health_payload, peer_trust=0)
        self.assertTrue(self.content_repository.update_torrent_called)

        # restore logger
        self.content_repository.logger = original_logger

    def test_update_torrent_with_higher_trust(self):
        """
        Scenario: The database torrent has still fresh last_check_time and you receive a new response from
        peer with trust > 1.
        Expect: Torrent in database is updated.
        """
        # last_check_time for existing torrent in database
        db_last_time_check = time.time() - 10
        # Peer trust, higher than 1 in this scenario
        peer_trust = 10

        # Database record is expected to be updated
        self.assertTrue(self.try_torrent_update_with_options(db_last_time_check, peer_trust))

    def test_update_torrent_with_stale_check_time(self):
        """
        Scenario: The database torrent has stale last_check_time and you receive a new response from
        peer with no previous trust.
        Expect: Torrent in database is still updated.
        """
        # last_check_time for existing torrent in database
        db_last_time_check = time.time() - DEFAULT_FRESHNESS_LIMIT
        # Peer trust, higher than 1 in this scenario
        peer_trust = 0

        # Database record is expected to be updated
        self.assertTrue(self.try_torrent_update_with_options(db_last_time_check, peer_trust))

    def try_torrent_update_with_options(self, db_last_check_time, peer_trust):
        """
        Tries updating torrent considering the given last check time of existing torrent and a new response
        obtained from a peer with given peer_trust value.
        """
        sample_infohash, seeders, leechers, timestamp = 'a' * 20, 10, 5, db_last_check_time
        sample_payload = TorrentHealthPayload(sample_infohash, seeders, leechers, timestamp)

        def update_torrent(content_repo, _):
            content_repo.update_torrent_called = True

        def get_torrent(infohash):
            return {'infohash': infohash, 'num_seeders': seeders,
                    'num_leechers': leechers, 'last_tracker_check': timestamp}

        self.content_repository.torrent_db.getTorrent = lambda infohash, **kw: get_torrent(infohash)
        self.content_repository.torrent_db.hasTorrent = lambda infohash: infohash == sample_infohash
        self.content_repository.torrent_db.updateTorrent = \
            lambda infohash, *args, **kw: update_torrent(self.content_repository, infohash)

        self.content_repository.update_torrent_called = False
        self.content_repository.update_torrent_health(sample_payload, peer_trust=peer_trust)

        return self.content_repository.update_torrent_called
