# -*- coding: utf-8 -*-
from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony import orm
from pony.orm import db_session

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.discrete_clock import clock
from tribler_core.modules.metadata_store.orm_bindings.channel_node import TODELETE
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = database_blob(b"")


def rnd_torrent():
    return {"title": "", "infohash": random_infohash(), "torrent_date": datetime(1970, 1, 1), "tags": "video"}


class TestTorrentMetadata(TriblerCoreTest):
    """
    Contains various tests for the torrent metadata type.
    """

    async def setUp(self):
        await super(TestTorrentMetadata, self).setUp()
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(':memory:', self.session_base_dir, self.my_key)
        clock.clock = 0  # We want deterministic discrete clock values for tests

    async def tearDown(self):
        self.mds.shutdown()
        await super(TestTorrentMetadata, self).tearDown()

    @db_session
    def test_serialization(self):
        """
        Test converting torrent metadata to serialized data
        """
        torrent_metadata = self.mds.TorrentMetadata.from_dict({"infohash": random_infohash()})
        self.assertTrue(torrent_metadata.serialized())

    @db_session
    def test_create_ffa_from_dict(self):
        """
        Test creating a free-for-all torrent entry
        """
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

        # Make sure that FFA entry with the infohash that is already known to GigaChannel cannot be created
        signed_entry = self.mds.TorrentMetadata.from_dict(tdef_to_metadata_dict(tdef))
        self.mds.TorrentMetadata.add_ffa_from_dict(tdef_to_metadata_dict(tdef))
        self.assertEqual(self.mds.TorrentMetadata.select(lambda g: g.public_key == EMPTY_BLOB).count(), 0)

        signed_entry.delete()
        # Create FFA entry
        self.mds.TorrentMetadata.add_ffa_from_dict(tdef_to_metadata_dict(tdef))
        self.assertEqual(self.mds.TorrentMetadata.select(lambda g: g.public_key == EMPTY_BLOB).count(), 1)

    @db_session
    def test_sanitize_tdef(self):
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        tdef.metainfo["creation date"] = -100000
        self.assertTrue(self.mds.TorrentMetadata.from_dict(tdef_to_metadata_dict(tdef)))

    @db_session
    def test_get_magnet(self):
        """
        Test converting torrent metadata to a magnet link
        """
        torrent_metadata = self.mds.TorrentMetadata.from_dict({"infohash": random_infohash()})
        self.assertTrue(torrent_metadata.get_magnet())
        torrent_metadata2 = self.mds.TorrentMetadata.from_dict({'title': u'\U0001f4a9', "infohash": random_infohash()})
        self.assertTrue(torrent_metadata2.get_magnet())

    @db_session
    def test_search_keyword(self):
        """
        Test searching in a database with some torrent metadata inserted
        """
        torrent1 = self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foo bar 123"))
        torrent2 = self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="eee 123"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="xoxoxo bar"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="xoxoxo bar"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"\""))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"\'"))
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

    @db_session
    def test_search_deduplicated(self):
        """
        Test SQL-query base deduplication of search results with the same infohash
        """
        key2 = default_eccrypto.generate_key(u"curve25519")
        torrent = rnd_torrent()
        self.mds.TorrentMetadata.from_dict(dict(torrent, title="foo bar 123"))
        self.mds.TorrentMetadata.from_dict(dict(torrent, title="eee 123", sign_with=key2))
        results = self.mds.TorrentMetadata.search_keyword("foo")[:]
        self.assertEqual(len(results), 1)

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
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"я маленький апельсин"))
        results = self.mds.TorrentMetadata.search_keyword(u"маленький")[:]
        self.assertEqual(1, len(results))

    @db_session
    def test_wildcard_search(self):
        """
        Test searching in the database with a wildcard
        """
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobar 123"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobla 123"))
        self.assertEqual(0, len(self.mds.TorrentMetadata.search_keyword("*")[:]))
        self.assertEqual(1, len(self.mds.TorrentMetadata.search_keyword("foobl*")[:]))
        self.assertEqual(2, len(self.mds.TorrentMetadata.search_keyword("foo*")[:]))
        self.assertEqual(1, len(self.mds.TorrentMetadata.search_keyword("(\"12\"* AND \"foobl\"*)")[:]))

    @db_session
    def test_stemming_search(self):
        """
        Test searching in the database with stemmed words
        """
        torrent = self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheep", tags="video"))

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
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheep", tags="video"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheep', autocomplete_terms)

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("shee", 10)
        self.assertIn('sheepish', autocomplete_terms)

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("", 10)
        self.assertEqual([], autocomplete_terms)

    @db_session
    def test_get_autocomplete_terms_max(self):
        """
        Test fetching autocompletion terms from the database with a maximum number of terms
        """
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheeps wolf", tags="video"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="lakes sheep", tags="video"))
        self.mds.TorrentMetadata.from_dict(dict(rnd_torrent(), title="regular sheepish guy", tags="video"))

        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms("sheep", 2)
        self.assertEqual(len(autocomplete_terms), 2)
        # Check that we can chew the special character "."
        autocomplete_terms = self.mds.TorrentMetadata.get_auto_complete_terms(".", 2)

    @db_session
    def test_get_entries(self):
        """
        Test base method for getting torrents
        """

        # First we create a few channels and add some torrents to these channels
        tlist = []
        keys = [*(default_eccrypto.generate_key('curve25519') for _ in range(4)), self.mds.ChannelNode._my_key]
        for ind, key in enumerate(keys):
            self.mds.ChannelMetadata(
                title='channel%d' % ind,
                subscribed=(ind % 2 == 0),
                infohash=random_infohash(),
                num_entries=5,
                sign_with=key,
            )
            tlist.extend(
                [
                    self.mds.TorrentMetadata(
                        title='torrent%d' % torrent_ind, infohash=random_infohash(), size=123, sign_with=key
                    )
                    for torrent_ind in range(5)
                ]
            )
        tlist[-1].xxx = 1
        tlist[-2].status = TODELETE

        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=5)
        self.assertEqual(5, len(torrents))

        count = self.mds.TorrentMetadata.get_entries_count(metadata_type=REGULAR_TORRENT)
        self.assertEqual(25, count)

        # Test fetching torrents in a channel
        channel_pk = self.mds.ChannelNode._my_key.pub().key_to_bin()[10:]

        args = dict(channel_pk=channel_pk, hide_xxx=True, exclude_deleted=True, metadata_type=REGULAR_TORRENT)
        torrents = self.mds.TorrentMetadata.get_entries_query(**args)[:]
        self.assertListEqual(tlist[-5:-2], list(torrents))

        count = self.mds.TorrentMetadata.get_entries_count(**args)
        self.assertEqual(count, 3)

        args = dict(sort_by='title', channel_pk=channel_pk, origin_id=0, metadata_type=REGULAR_TORRENT)
        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=10, **args)
        self.assertEqual(5, len(torrents))

        count = self.mds.TorrentMetadata.get_entries_count(**args)
        self.assertEqual(5, count)

        # Test that channels get priority over torrents when querying for mixed content
        args = dict(sort_by='size', sort_desc=True, channel_pk=channel_pk, origin_id=0)
        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=10, **args)
        self.assertEqual(torrents[0].metadata_type, CHANNEL_TORRENT)

        args = dict(sort_by='size', sort_desc=False, channel_pk=channel_pk, origin_id=0)
        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=10, **args)
        self.assertEqual(torrents[-1].metadata_type, CHANNEL_TORRENT)

        # Test getting entries by timestamp range
        args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp", 3, 30),))
        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=10, **args)
        self.assertListEqual(sorted([t.timestamp for t in torrents]), list(range(25, 30)))

        # Test catching SQL injection
        args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp < 3 and g.timestamp", 3, 30),))
        self.assertRaises(AttributeError, self.mds.TorrentMetadata.get_entries, **args)

        # Test getting entry by id_
        with db_session:
            entry = self.mds.TorrentMetadata(id_=123, infohash=random_infohash())
        args = dict(channel_pk=channel_pk, id_=123)
        torrents = self.mds.TorrentMetadata.get_entries(first=1, last=10, **args)
        self.assertListEqual(list(torrents), [entry])

    @db_session
    def test_metadata_conflicting(self):
        tdict = dict(rnd_torrent(), title="lakes sheep", tags="video", infohash=b'\x00\xff')
        md = self.mds.TorrentMetadata.from_dict(tdict)
        self.assertFalse(md.metadata_conflicting(tdict))
        self.assertTrue(md.metadata_conflicting(dict(tdict, title="bla")))
        tdict.pop('title')
        self.assertFalse(md.metadata_conflicting(tdict))

    @db_session
    def test_update_properties(self):
        """
        Test the updating of several properties of a TorrentMetadata object
        """
        metadata = self.mds.TorrentMetadata(title='foo', infohash=random_infohash())
        orig_timestamp = metadata.timestamp

        # Test updating the status only
        self.assertEqual(metadata.update_properties({"status": 456}).status, 456)
        self.assertEqual(orig_timestamp, metadata.timestamp)
        self.assertEqual(metadata.update_properties({"title": "bar"}).title, "bar")
        self.assertLess(orig_timestamp, metadata.timestamp)
