# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
from datetime import datetime

from pony import orm
from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestTorrentMetadata(TriblerCoreTest):
    """
    Contains various tests for the torrent metadata type.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestTorrentMetadata, self).setUp()
        self.torrent_template = {
            "title": "",
            "infohash": "",
            "torrent_date": datetime(1970, 1, 1),
            "tags": "video"
        }
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir,
                                 self.my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestTorrentMetadata, self).tearDown()

    @db_session
    def test_serialization(self):
        """
        Test converting torrent metadata to serialized data
        """
        torrent_metadata = self.mds.TorrentMetadata.from_dict({})
        self.assertTrue(torrent_metadata.serialized())

    @db_session
    def test_get_magnet(self):
        """
        Test converting torrent metadata to a magnet link
        """
        torrent_metadata = self.mds.TorrentMetadata.from_dict({})
        self.assertTrue(torrent_metadata.get_magnet())
        torrent_metadata2 = self.mds.TorrentMetadata.from_dict({'title': u'\U0001f4a9'})
        self.assertTrue(torrent_metadata2.get_magnet())

    @db_session
    def test_search_keyword(self):
        """
        Test searching in a database with some torrent metadata inserted
        """
        torrent1 = self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="foo bar 123", tags="video"))
        torrent2 = self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="eee 123", tags="video"))
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="xoxoxo bar", tags="video"))
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="xoxoxo bar", tags="audio"))
        orm.flush()

        # Search for torrents with the keyword 'foo', it should return one result
        results = self.mds.TorrentMetadata.search_keyword("foo")[:]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rowid, torrent1.rowid)

        # Search for torrents with the keyword 'eee', it should return one result
        results = self.mds.TorrentMetadata.search_keyword("eee")[:]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rowid, torrent2.rowid)

        # Search for torrents with the keyword '123', it should return two results
        results = self.mds.TorrentMetadata.search_keyword("123")[:]
        self.assertEqual(len(results), 2)

        # Search for torrents with the keyword 'video', it should return three results
        results = self.mds.TorrentMetadata.search_keyword("video")[:]
        self.assertEqual(len(results), 3)

    def test_search_empty_query(self):
        """
        Test whether an empty query returns nothing
        """
        self.assertFalse(self.mds.TorrentMetadata.search_keyword(None)[:])

    @db_session
    def test_unicode_search(self):
        """
        Test searching in the database with unicode characters
        """
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title=u"я маленький апельсин"))
        results = self.mds.TorrentMetadata.search_keyword(u"маленький")[:]
        self.assertEqual(1, len(results))

    @db_session
    def test_wildcard_search(self):
        """
        Test searching in the database with a wildcard
        """
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title="foobar 123"))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, title="foobla 123"))
        self.assertEqual(0, len(self.mds.TorrentMetadata.search_keyword("*")[:]))
        self.assertEqual(1, len(self.mds.TorrentMetadata.search_keyword("foobl*")[:]))
        self.assertEqual(2, len(self.mds.TorrentMetadata.search_keyword("foo*")[:]))

    @db_session
    def test_stemming_search(self):
        """
        Test searching in the database with stemmed words
        """
        torrent = self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheep", tags="video"))

        # Search with the word 'mountain' should return the torrent with 'mountains' in the title
        results = self.mds.TorrentMetadata.search_keyword("mountain")[:]
        self.assertEqual(torrent.rowid, results[0].rowid)

        # Search with the word 'sheeps' should return the torrent with 'sheep' in the title
        results = self.mds.TorrentMetadata.search_keyword("sheeps")[:]
        self.assertEqual(torrent.rowid, results[0].rowid)

    @db_session
    def test_get_autocomplete_terms(self):
        """
        Test fetching autocompletion terms from the database
        """
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheep", tags="video"))
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheep', autocomplete_terms)

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheepish', autocomplete_terms)

    @db_session
    def test_get_autocomplete_terms_max(self):
        """
        Test fetching autocompletion terms from the database with a maximum number of terms
        """
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="mountains sheeps wolf", tags="video"))
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="lakes sheep", tags="video"))
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("sheep", 2)
        self.assertEqual(len(autocomplete_terms), 2)

    @db_session
    def test_get_torrents(self):
        """
        Test whether we can get torrents
        """

        # First we create a few channels and add some torrents to these channels
        for ind in xrange(5):
            self.mds.ChannelNode._my_key = default_eccrypto.generate_key('curve25519')
            _ = self.mds.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0))
            for torrent_ind in xrange(5):
                _ = self.mds.TorrentMetadata(title='torrent%d' % torrent_ind)

        torrents = self.mds.ChannelMetadata.get_torrents(first=1, last=5)
        self.assertEqual(len(torrents[0]), 5)
        self.assertEqual(torrents[1], 25)

        # Test fetching torrents in a channel
        channel_pk = self.mds.ChannelNode._my_key.pub().key_to_bin()[10:]
        torrents = self.mds.ChannelMetadata.get_torrents(first=1, last=10, sort_by='title', channel_pk=channel_pk)
        self.assertEqual(len(torrents[0]), 5)
        self.assertEqual(torrents[1], 5)
