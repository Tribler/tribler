import os
import random
import string
import tarfile
import time
import unittest
from binascii import unhexlify

from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.Core.test_sqlitecachedbhandler import BUSYTIMEOUT
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.community.popularity.payload import TorrentHealthPayload
from Tribler.community.popularity.repository import ContentRepository, DEFAULT_FRESHNESS_LIMIT
from Tribler.pyipv8.ipv8.test.base import TestBase


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
        self.assertEqual(self.content_repository.count_content(), 0, "No item expected in queue initially")

        # Add a sample content and check the size
        sample_content = ('a' * 20, 6, 3, 123456789)
        sample_content_type = 1
        self.content_repository.add_content(sample_content_type, sample_content)
        self.assertEqual(self.content_repository.count_content(), 1, "One item expected in queue")

        # Pop an item
        (content_type, content) = self.content_repository.pop_content()
        self.assertEqual(content_type, sample_content_type, "Content type should be equal")
        self.assertEqual(content, sample_content, "Content should be equal")

        # Check size again
        self.assertEqual(self.content_repository.count_content(), 0, "No item expected in queue")

    def test_get_top_torrents(self):
        """
        Test if content repository returns expected top torrents.
        """

        def get_fake_torrents(limit):
            return [[chr(x) * 20, x, 0, 1525704192] for x in range(limit)]

        self.content_repository.torrent_db.getRecentlyCheckedTorrents = get_fake_torrents

        limit = 10
        self.assertEqual(self.content_repository.get_top_torrents(limit=limit), get_fake_torrents(limit))

    def test_update_torrent_health(self):
        """
        Tests update torrent health.
        """
        def update_torrent(repo, _):
            repo.update_torrent_called = True

        # Assume a fake torrent response
        fake_torrent_health_payload = TorrentHealthPayload('a' * 20, 10, 4, time.time())

        self.content_repository.torrent_db = MockObject()
        self.content_repository.torrent_db.updateTorrent = lambda infohash, *args, **kw: \
            update_torrent(self.content_repository, infohash)

        # If torrent does not exist in the database, then it should be added to the database
        self.content_repository.has_torrent = lambda infohash: False
        self.content_repository.update_torrent_health(fake_torrent_health_payload, peer_trust=0)

        self.assertTrue(self.content_repository.update_torrent_called)

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

    def test_update_torrent_info(self):
        """ Test updating torrent info """
        self.content_repository.called_update_torrent = False

        def fake_update_torrent(ref):
            ref.called_update_torrent = True

        self.content_repository.torrent_db.updateTorrent = lambda infohash, **kw: \
            fake_update_torrent(self.content_repository)
        self.content_repository.has_torrent = lambda infohash: False
        torrent_info_response = MockObject()
        torrent_info_response.infohash = 'a' * 20

        torrent_info_response.name = 'ubuntu'
        torrent_info_response.length = 123
        torrent_info_response.creation_date = 123123123
        torrent_info_response.num_files = 2
        torrent_info_response.comment = 'Ubuntu ISO'

        self.content_repository.update_torrent_info(torrent_info_response)
        self.assertTrue(self.content_repository.called_update_torrent)

    def test_update_conflicting_torrent_info(self):
        """ Test updating torrent info response with existing record in the database."""
        torrent_info_response = MockObject()
        torrent_info_response.infohash = 'a' * 20
        torrent_info_response.name = 'ubuntu'
        torrent_info_response.length = 123
        torrent_info_response.creation_date = 123123123
        torrent_info_response.num_files = 2
        torrent_info_response.comment = 'Ubuntu ISO'

        self.content_repository.called_update_torrent = False

        def fake_update_torrent(ref):
            ref.called_update_torrent = True

        def fake_get_torrent(infohash, name):
            torrent = {'infohash': infohash, 'name': name}
            return torrent

        self.content_repository.torrent_db.updateTorrent = lambda infohash, **kw: fake_update_torrent(
            self.content_repository)
        self.content_repository.has_torrent = lambda infohash: True
        self.content_repository.get_torrent = lambda infohash: fake_get_torrent(infohash, torrent_info_response.name)

        self.content_repository.update_torrent_info(torrent_info_response)
        self.assertFalse(self.content_repository.called_update_torrent)

    def test_search_torrent(self):
        """ Test torrent search """
        def random_string(size=6, chars=string.ascii_uppercase + string.digits):
            return ''.join(random.choice(chars) for _ in range(size))

        def random_infohash():
            return ''.join(random.choice('0123456789abcdef') for _ in range(20))

        sample_torrents = []
        for _ in range(10):
            infohash = random_infohash()
            name = random_string()
            length = random.randint(1000, 9999)
            num_files = random.randint(1, 10)
            category_list = ['video', 'audio']
            creation_date = random.randint(1000000, 111111111)
            seeders = random.randint(10, 200)
            leechers = random.randint(5, 1000)
            cid = random_string(size=20)

            sample_torrents.append([infohash, name, length, num_files, category_list, creation_date, seeders,
                                    leechers, cid])

        def fake_torrentdb_search_names(_):
            return sample_torrents

        self.content_repository.torrent_db.searchNames = lambda query, **kw: fake_torrentdb_search_names(query)

        search_query = "Ubuntu"
        search_results = self.content_repository.search_torrent(search_query)

        for index in range(10):
            db_torrent = sample_torrents[index]
            search_result = search_results[index]

            self.assertEqual(db_torrent[0], search_result.infohash)
            self.assertEqual(db_torrent[1], search_result.name)
            self.assertEqual(db_torrent[2], search_result.length)
            self.assertEqual(db_torrent[3], search_result.num_files)
            self.assertEqual(db_torrent[6], search_result.seeders)
            self.assertEqual(db_torrent[7], search_result.leechers)

    def test_search_channel(self):
        """ Test channel search """
        def random_string(size=6, chars=string.ascii_uppercase + string.digits):
            return ''.join(random.choice(chars) for _ in range(size))

        sample_channels = []
        for index in range(10):
            dbid = index
            cid = random_string(size=20)
            name = random_string()
            description = random_string(20)
            nr_torrents = random.randint(1, 10)
            nr_favorite = random.randint(1, 10)
            nr_spam = random.randint(1, 10)
            my_vote = 1
            modified = random.randint(1, 10000000)
            relevance_score = 0.0

            sample_channels.append([dbid, cid, name, description, nr_torrents, nr_favorite, nr_spam, my_vote,
                                    modified, relevance_score])

        def fake_torrentdb_search_channels(_):
            return sample_channels

        self.content_repository.channel_db.search_in_local_channels_db = lambda query, **kw: \
            fake_torrentdb_search_channels(query)

        search_query = "Ubuntu"
        search_results = self.content_repository.search_channels(search_query)

        for index in range(10):
            db_channel = sample_channels[index]
            search_result = search_results[index]

            self.assertEqual(db_channel[0], search_result.id)
            self.assertEqual(db_channel[1], search_result.cid)
            self.assertEqual(db_channel[2], search_result.name)
            self.assertEqual(db_channel[3], search_result.description)
            self.assertEqual(db_channel[4], search_result.nr_torrents)
            self.assertEqual(db_channel[5], search_result.nr_favorite)
            self.assertEqual(db_channel[6], search_result.nr_spam)
            self.assertEqual(db_channel[8], search_result.modified)

    def test_update_torrent_from_search_results(self):
        """ Tests updating database from the search results """
        def random_string(size=6, chars=string.ascii_uppercase + string.digits):
            return ''.join(random.choice(chars) for _ in range(size))

        def random_infohash():
            return ''.join(random.choice('0123456789abcdef') for _ in range(20))

        search_results = dict()
        for _ in range(10):
            infohash = random_infohash()
            name = random_string()
            length = random.randint(1000, 9999)
            num_files = random.randint(1, 10)
            category_list = ['video', 'audio']
            creation_date = random.randint(1000000, 111111111)
            seeders = random.randint(10, 200)
            leechers = random.randint(5, 1000)
            cid = random_string(size=20)

            search_results[infohash] = [infohash, name, length, num_files, category_list, creation_date,
                                        seeders, leechers, cid]

        def get_torrent(torrent_as_list):
            return {'infohash': torrent_as_list[0],
                    'name': torrent_as_list[1],
                    'length': torrent_as_list[2],
                    'num_files': torrent_as_list[3],
                    'category_list': torrent_as_list[4],
                    'creation_date': torrent_as_list[5],
                    'seeders': torrent_as_list[6],
                    'leechers': torrent_as_list[7],
                    'cid': torrent_as_list[8]}

        def fake_update_torrent(ref):
            ref.called_update_torrent = True

        def fake_add_or_get_torrent_id(ref):
            ref.called_add_or_get_torrent_id = True

        self.content_repository.torrent_db.updateTorrent = lambda infohash, **kw: fake_update_torrent(
            self.content_repository)
        self.content_repository.torrent_db.addOrGetTorrentID = lambda infohash: fake_add_or_get_torrent_id(
            self.content_repository)

        # Case 1: Assume torrent does not exist in the database
        self.content_repository.has_torrent = lambda infohash: False
        self.content_repository.get_torrent = lambda infohash: None

        self.content_repository.torrent_db._db = MockObject()
        self.content_repository.torrent_db._db.commit_now = lambda x=None: None

        self.content_repository.called_update_torrent = False
        self.content_repository.update_from_torrent_search_results(search_results.values())
        self.assertTrue(self.content_repository.called_update_torrent)
        self.assertTrue(self.content_repository.called_add_or_get_torrent_id)

        # Case 2: Torrent already exist in the database
        self.content_repository.has_torrent = lambda infohash: infohash in search_results
        self.content_repository.get_torrent = lambda infohash: get_torrent(search_results[infohash])

        self.content_repository.called_update_torrent = False
        self.content_repository.called_add_or_get_torrent_id = False
        self.content_repository.update_from_torrent_search_results(search_results.values())
        self.assertFalse(self.content_repository.called_update_torrent)
        self.assertFalse(self.content_repository.called_add_or_get_torrent_id)


class TestContentRepositoryWithRealDatabase(TestBase):
    """
    Tests content repository with real database.
    """

    def setUp(self):
        super(TestContentRepositoryWithRealDatabase, self).setUp()

        session_base_dir = self.temporary_directory()
        tar = tarfile.open(os.path.join(TESTS_DATA_DIR, 'bak_new_tribler.sdb.tar.gz'), 'r|gz')
        tar.extractall(session_base_dir)
        db_path = os.path.join(session_base_dir, 'bak_new_tribler.sdb')
        self.sqlitedb = SQLiteCacheDB(db_path, busytimeout=BUSYTIMEOUT)

        session = MockObject()
        session.sqlite_db = self.sqlitedb
        session.notifier = MockObject()

        self.torrent_db = TorrentDBHandler(session)
        channel_db = MockObject()
        self.content_repository = ContentRepository(self.torrent_db, channel_db)

    def tearDown(self):
        self.torrent_db.close()
        self.sqlitedb.close()
        super(TestContentRepositoryWithRealDatabase, self).tearDown()

    def test_update_db_from_search_results(self):
        """
        Test if database is properly updated with the search results.
        Should not raise any UnicodeDecodeError.
        """
        # Add a torrent infohash before updating from search results
        infohash = unhexlify('ed81da94d21ad1b305133f2726cdaec5a57fed98')
        self.content_repository.torrent_db.addOrGetTorrentID(infohash)

        # Sample search results
        name = 'Puppy.Linux.manual.301.espa\xc3\xb1ol.pdf'
        length = random.randint(1000, 9999)
        num_files = random.randint(1, 10)
        category_list = ['other']
        creation_date = random.randint(1000000, 111111111)
        seeders = random.randint(10, 200)
        leechers = random.randint(5, 1000)
        cid = None
        search_results = [[infohash, name, length, num_files, category_list, creation_date, seeders, leechers, cid]]

        # Update from search results
        self.content_repository.update_from_torrent_search_results(search_results)

        # Check if database has correct results
        torrent_info = self.content_repository.get_torrent(infohash)
        expected_name = u'Puppy.Linux.manual.301.espa\xc3\xb1ol.pdf'
        self.assertEqual(expected_name, torrent_info['name'])
        self.assertEqual(seeders, torrent_info['num_seeders'])
        self.assertEqual(leechers, torrent_info['num_leechers'])
        self.assertEqual(creation_date, torrent_info['creation_date'])
        self.assertEqual(num_files, torrent_info['num_files'])
        self.assertEqual(length, torrent_info['length'])
