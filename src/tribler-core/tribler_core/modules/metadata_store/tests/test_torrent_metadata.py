# -*- coding: utf-8 -*-
from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony import orm
from pony.orm import db_session

import pytest

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.discrete_clock import clock
from tribler_core.modules.metadata_store.orm_bindings.channel_node import TODELETE
from tribler_core.modules.metadata_store.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = database_blob(b"")


def rnd_torrent():
    return {"title": "", "infohash": random_infohash(), "torrent_date": datetime(1970, 1, 1), "tags": "video"}


@db_session
def test_serialization(metadata_store):
    """
    Test converting torrent metadata to serialized data
    """
    torrent_metadata = metadata_store.TorrentMetadata.from_dict({"infohash": random_infohash()})
    assert torrent_metadata.serialized()


@db_session
def test_create_ffa_from_dict(metadata_store):
    """
    Test creating a free-for-all torrent entry
    """
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

    # Make sure that FFA entry with the infohash that is already known to GigaChannel cannot be created
    signed_entry = metadata_store.TorrentMetadata.from_dict(tdef_to_metadata_dict(tdef))
    metadata_store.TorrentMetadata.add_ffa_from_dict(tdef_to_metadata_dict(tdef))
    assert metadata_store.TorrentMetadata.select(lambda g: g.public_key == EMPTY_BLOB).count() == 0

    signed_entry.delete()
    # Create FFA entry
    metadata_store.TorrentMetadata.add_ffa_from_dict(tdef_to_metadata_dict(tdef))
    assert metadata_store.TorrentMetadata.select(lambda g: g.public_key == EMPTY_BLOB).count() == 1


@db_session
def test_sanitize_tdef(metadata_store):
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
    tdef.metainfo["creation date"] = -100000
    assert metadata_store.TorrentMetadata.from_dict(tdef_to_metadata_dict(tdef))


@db_session
def test_get_magnet(metadata_store):
    """
    Test converting torrent metadata to a magnet link
    """
    torrent_metadata = metadata_store.TorrentMetadata.from_dict({"infohash": random_infohash()})
    assert torrent_metadata.get_magnet()
    torrent_metadata2 = metadata_store.TorrentMetadata.from_dict({'title': '\U0001f4a9', "infohash": random_infohash()})
    assert torrent_metadata2.get_magnet()


@db_session
def test_search_keyword(metadata_store):
    """
    Test searching in a database with some torrent metadata inserted
    """
    torrent1 = metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foo bar 123"))
    torrent2 = metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="eee 123"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="xoxoxo bar"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="xoxoxo bar"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"\""))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"\'"))
    orm.flush()

    # Search for torrents with the keyword 'foo', it should return one result
    results = metadata_store.TorrentMetadata.search_keyword("foo")[:]
    assert len(results) == 1
    assert results[0].rowid == torrent1.rowid

    # Search for torrents with the keyword 'eee', it should return one result
    results = metadata_store.TorrentMetadata.search_keyword("eee")[:]
    assert len(results) == 1
    assert results[0].rowid == torrent2.rowid

    # Search for torrents with the keyword '123', it should return two results
    results = metadata_store.TorrentMetadata.search_keyword("123")[:]
    assert len(results) == 2


@db_session
def test_search_deduplicated(metadata_store):
    """
    Test SQL-query base deduplication of search results with the same infohash
    """
    key2 = default_eccrypto.generate_key(u"curve25519")
    torrent = rnd_torrent()
    metadata_store.TorrentMetadata.from_dict(dict(torrent, title="foo bar 123"))
    metadata_store.TorrentMetadata.from_dict(dict(torrent, title="eee 123", sign_with=key2))
    results = metadata_store.TorrentMetadata.search_keyword("foo")[:]
    assert len(results) == 1


def test_search_empty_query(metadata_store):
    """
    Test whether an empty query returns nothing
    """
    assert not metadata_store.TorrentMetadata.search_keyword(None)[:]


@db_session
def test_unicode_search(metadata_store):
    """
    Test searching in the database with unicode characters
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title=u"я маленький апельсин"))
    results = metadata_store.TorrentMetadata.search_keyword(u"маленький")[:]
    assert len(results) == 1


@db_session
def test_wildcard_search(metadata_store):
    """
    Test searching in the database with a wildcard
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobar 123"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobla 123"))
    assert not metadata_store.TorrentMetadata.search_keyword("*")[:]
    assert len(metadata_store.TorrentMetadata.search_keyword("foobl*")[:]) == 1
    assert len(metadata_store.TorrentMetadata.search_keyword("foo*")[:]) == 2
    assert len(metadata_store.TorrentMetadata.search_keyword("(\"12\"* AND \"foobl\"*)")[:]) == 1


@db_session
def test_stemming_search(metadata_store):
    """
    Test searching in the database with stemmed words
    """
    torrent = metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheep", tags="video"))

    # Search with the word 'mountain' should return the torrent with 'mountains' in the title
    results = metadata_store.TorrentMetadata.search_keyword("mountain")[:]
    assert torrent.rowid == results[0].rowid

    # Search with the word 'sheeps' should return the torrent with 'sheep' in the title
    results = metadata_store.TorrentMetadata.search_keyword("sheeps")[:]
    assert torrent.rowid == results[0].rowid


@db_session
def test_get_autocomplete_terms(metadata_store):
    """
    Test fetching autocompletion terms from the database
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheep", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="regular sheepish guy", tags="video"))

    autocomplete_terms = metadata_store.TorrentMetadata.get_auto_complete_terms("shee", 10)
    assert 'sheep' in autocomplete_terms

    autocomplete_terms = metadata_store.TorrentMetadata.get_auto_complete_terms("shee", 10)
    assert 'sheepish' in autocomplete_terms

    autocomplete_terms = metadata_store.TorrentMetadata.get_auto_complete_terms("", 10)
    assert [] == autocomplete_terms


@db_session
def test_get_autocomplete_terms_max(metadata_store):
    """
    Test fetching autocompletion terms from the database with a maximum number of terms
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheeps wolf", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="lakes sheep", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="regular sheepish guy", tags="video"))

    autocomplete_terms = metadata_store.TorrentMetadata.get_auto_complete_terms("sheep", 2)
    assert len(autocomplete_terms) == 2
    # Check that we can chew the special character "."
    autocomplete_terms = metadata_store.TorrentMetadata.get_auto_complete_terms(".", 2)


@db_session
def test_get_entries(metadata_store):
    """
    Test base method for getting torrents
    """
    clock.clock = 0  # We want deterministic discrete clock values for tests

    # First we create a few channels and add some torrents to these channels
    tlist = []
    keys = [*(default_eccrypto.generate_key('curve25519') for _ in range(4)), metadata_store.ChannelNode._my_key]
    for ind, key in enumerate(keys):
        metadata_store.ChannelMetadata(
            title='channel%d' % ind, subscribed=(ind % 2 == 0), infohash=random_infohash(), num_entries=5, sign_with=key
        )
        tlist.extend(
            [
                metadata_store.TorrentMetadata(
                    title='torrent%d' % torrent_ind, infohash=random_infohash(), size=123, sign_with=key
                )
                for torrent_ind in range(5)
            ]
        )
    tlist[-1].xxx = 1
    tlist[-2].status = TODELETE

    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=5)
    assert len(torrents) == 5

    count = metadata_store.TorrentMetadata.get_entries_count(metadata_type=REGULAR_TORRENT)
    assert count == 25

    # Test fetching torrents in a channel
    channel_pk = metadata_store.ChannelNode._my_key.pub().key_to_bin()[10:]

    args = dict(channel_pk=channel_pk, hide_xxx=True, exclude_deleted=True, metadata_type=REGULAR_TORRENT)
    torrents = metadata_store.TorrentMetadata.get_entries_query(**args)[:]
    assert tlist[-5:-2] == list(torrents)

    count = metadata_store.TorrentMetadata.get_entries_count(**args)
    assert count == 3

    args = dict(sort_by='title', channel_pk=channel_pk, origin_id=0, metadata_type=REGULAR_TORRENT)
    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=10, **args)
    assert len(torrents) == 5

    count = metadata_store.TorrentMetadata.get_entries_count(**args)
    assert count == 5

    # Test that channels get priority over torrents when querying for mixed content
    args = dict(sort_by='size', sort_desc=True, channel_pk=channel_pk, origin_id=0)
    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=10, **args)
    assert torrents[0].metadata_type == CHANNEL_TORRENT

    args = dict(sort_by='size', sort_desc=False, channel_pk=channel_pk, origin_id=0)
    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=10, **args)
    assert torrents[-1].metadata_type == CHANNEL_TORRENT

    # Test getting entries by timestamp range
    args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp", 3, 30),))
    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=10, **args)
    assert sorted([t.timestamp for t in torrents]) == list(range(25, 30))

    # Test catching SQL injection
    args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp < 3 and g.timestamp", 3, 30),))
    with pytest.raises(AttributeError):
        metadata_store.TorrentMetadata.get_entries(**args)

    # Test getting entry by id_
    with db_session:
        entry = metadata_store.TorrentMetadata(id_=123, infohash=random_infohash())
    args = dict(channel_pk=channel_pk, id_=123)
    torrents = metadata_store.TorrentMetadata.get_entries(first=1, last=10, **args)
    assert list(torrents) == [entry]


@db_session
def test_metadata_conflicting(metadata_store):
    tdict = dict(rnd_torrent(), title="lakes sheep", tags="video", infohash=b'\x00\xff')
    md = metadata_store.TorrentMetadata.from_dict(tdict)
    assert not md.metadata_conflicting(tdict)
    assert md.metadata_conflicting(dict(tdict, title="bla"))
    tdict.pop('title')
    assert not md.metadata_conflicting(tdict)


@db_session
def test_update_properties(metadata_store):
    """
    Test the updating of several properties of a TorrentMetadata object
    """
    metadata = metadata_store.TorrentMetadata(title='foo', infohash=random_infohash())
    orig_timestamp = metadata.timestamp

    # Test updating the status only
    assert metadata.update_properties({"status": 456}).status == 456
    assert orig_timestamp == metadata.timestamp
    assert metadata.update_properties({"title": "bar"}).title == "bar"
    assert metadata.timestamp > orig_timestamp
