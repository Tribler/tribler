# -*- coding: utf-8 -*-
from datetime import datetime

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import TestAsServer


class TestTorrentMetadata(TestAsServer):
    """
    Contains various tests for the torrent metadata type.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestTorrentMetadata, self).setUp()
        self.torrent_template = {
            "infohash": "",
            "torrent_date": datetime(1970, 1, 1),
            "tags": "video"
        }

    def setUpPreSession(self):
        super(TestTorrentMetadata, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @db_session
    def test_serialization(self):
        """
        Test converting torrent metadata to serialized data
        """
        torrent_metadata = self.session.lm.mds.TorrentMetadata.from_dict({})
        self.assertTrue(torrent_metadata.serialized())

    @db_session
    def test_get_magnet(self):
        """
        Test converting torrent metadata to a magnet link
        """
        torrent_metadata = self.session.lm.mds.TorrentMetadata.from_dict({})
        self.assertTrue(torrent_metadata.get_magnet())

    @db_session
    def test_search_keyword(self):
        """
        Test searching in a database with some torrent metadata inserted
        """
        torrent1 = self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="foo bar 123", tags="video"))
        torrent2 = self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="eee 123", tags="video"))
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="xoxoxo bar", tags="video"))
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="xoxoxo bar", tags="audio"))

        # Search for torrents with the keyword 'foo', it should return one result
        results = self.session.lm.mds.TorrentMetadata.search_keyword("foo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rowid, torrent1.rowid)

        # Search for torrents with the keyword 'eee', it should return one result
        results = self.session.lm.mds.TorrentMetadata.search_keyword("eee")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rowid, torrent2.rowid)

        # Search for torrents with the keyword '123', it should return two results
        results = self.session.lm.mds.TorrentMetadata.search_keyword("123")
        self.assertEqual(len(results), 2)

        # Search for torrents with the keyword 'video', it should return three results
        results = self.session.lm.mds.TorrentMetadata.search_keyword("video")
        self.assertEqual(len(results), 3)

    def test_search_empty_query(self):
        """
        Test whether an empty query returns nothing
        """
        self.assertFalse(self.session.lm.mds.TorrentMetadata.search_keyword(None))

    @db_session
    def test_unicode_search(self):
        """
        Test searching in the database with unicode characters
        """
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title=u"я маленький апельсин"))
        results = self.session.lm.mds.TorrentMetadata.search_keyword(u"маленький")
        self.assertEqual(1, len(results))

    @db_session
    def test_wildcard_search(self):
        """
        Test searching in the database with a wildcard
        """
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title="foobar 123"))
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title="foobla 123"))
        self.assertEqual(0, len(self.session.lm.mds.TorrentMetadata.search_keyword("*")))
        self.assertEqual(1, len(self.session.lm.mds.TorrentMetadata.search_keyword("foobl*")))
        self.assertEqual(2, len(self.session.lm.mds.TorrentMetadata.search_keyword("foo*")))

    @db_session
    def test_stemming_search(self):
        """
        Test searching in the database with stemmed words
        """
        torrent = self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheep", tags="video"))

        # Search with the word 'mountain' should return the torrent with 'mountains' in the title
        results = self.session.lm.mds.TorrentMetadata.search_keyword("mountain")
        self.assertEqual(torrent.rowid, results[0].rowid)

        # Search with the word 'sheeps' should return the torrent with 'sheep' in the title
        results = self.session.lm.mds.TorrentMetadata.search_keyword("sheeps")
        self.assertEqual(torrent.rowid, results[0].rowid)

    @db_session
    def test_get_autocomplete_terms(self):
        """
        Test fetching autocompletion terms from the database
        """
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheep", tags="video"))
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.session.lm.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheep', autocomplete_terms)

        autocomplete_terms = self.session.lm.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheepish', autocomplete_terms)

    @db_session
    def test_get_autocomplete_terms_max(self):
        """
        Test fetching autocompletion terms from the database with a maximum number of terms
        """
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheep", tags="video"))
        self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.session.lm.mds.TorrentMetadata.get_auto_complete_terms("sheep", 2)
        self.assertEqual(len(autocomplete_terms), 1)
