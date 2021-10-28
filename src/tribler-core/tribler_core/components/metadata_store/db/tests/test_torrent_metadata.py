from datetime import datetime
from time import time

from ipv8.keyvault.crypto import default_eccrypto

from pony import orm
from pony.orm import db_session

import pytest

from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.metadata_store.db.orm_bindings.channel_node import TODELETE
from tribler_core.components.metadata_store.db.orm_bindings.discrete_clock import clock
from tribler_core.components.metadata_store.db.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = b""


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
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="\""))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="\'"))
    orm.flush()

    # Search for torrents with the keyword 'foo', it should return one result
    results = metadata_store.search_keyword("foo")[:]
    assert len(results) == 1
    assert results[0].rowid == torrent1.rowid

    # Search for torrents with the keyword 'eee', it should return one result
    results = metadata_store.search_keyword("eee")[:]
    assert len(results) == 1
    assert results[0].rowid == torrent2.rowid

    # Search for torrents with the keyword '123', it should return two results
    results = metadata_store.search_keyword("123")[:]
    assert len(results) == 2


@db_session
def test_search_deduplicated(metadata_store):
    """
    Test SQL-query base deduplication of search results with the same infohash
    """
    key2 = default_eccrypto.generate_key("curve25519")
    torrent = rnd_torrent()
    metadata_store.TorrentMetadata.from_dict(dict(torrent, title="foo bar 123"))
    metadata_store.TorrentMetadata.from_dict(dict(torrent, title="eee 123", sign_with=key2))
    results = metadata_store.search_keyword("foo")[:]
    assert len(results) == 1


def test_search_empty_query(metadata_store):
    """
    Test whether an empty query returns nothing
    """
    assert not metadata_store.search_keyword(None)[:]


@db_session
def test_unicode_search(metadata_store):
    """
    Test searching in the database with unicode characters
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="я маленький апельсин"))
    results = metadata_store.search_keyword("маленький")[:]
    assert len(results) == 1


@db_session
def test_wildcard_search(metadata_store):
    """
    Test searching in the database with a wildcard
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobar 123"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foobla 123"))
    assert not metadata_store.search_keyword("*")[:]
    assert len(metadata_store.search_keyword("foobl*")[:]) == 1
    assert len(metadata_store.search_keyword("foo*")[:]) == 2
    assert len(metadata_store.search_keyword("(\"12\"* AND \"foobl\"*)")[:]) == 1


@db_session
def test_stemming_search(metadata_store):
    """
    Test searching in the database with stemmed words
    """
    torrent = metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheep", tags="video"))

    # Search with the word 'mountain' should return the torrent with 'mountains' in the title
    results = metadata_store.search_keyword("mountain")[:]
    assert torrent.rowid == results[0].rowid

    # Search with the word 'sheeps' should return the torrent with 'sheep' in the title
    results = metadata_store.search_keyword("sheeps")[:]
    assert torrent.rowid == results[0].rowid


@db_session
def test_get_autocomplete_terms(metadata_store):
    """
    Test fetching autocompletion terms from the database
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foo: bar baz", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="foo - bar, xyz", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="barbarian xyz!", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="n.a.m.e: foobar", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="xyz n.a.m.e", tags="video"))

    autocomplete_terms = metadata_store.get_auto_complete_terms("", 10)
    assert autocomplete_terms == []

    autocomplete_terms = metadata_store.get_auto_complete_terms("foo", 10)
    assert set(autocomplete_terms) == {"foo: bar", "foo - bar", "foobar"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("foo: bar", 10)
    assert set(autocomplete_terms) == {"foo: bar baz", "foo: bar, xyz"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("foo ", 10)
    assert set(autocomplete_terms) == {"foo bar"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("bar", 10)
    assert set(autocomplete_terms) == {"bar baz", "bar, xyz", "barbarian"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("barb", 10)
    assert set(autocomplete_terms) == {"barbarian"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("barbarian", 10)
    assert set(autocomplete_terms) == {"barbarian xyz"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("barbarian ", 10)
    assert set(autocomplete_terms) == {"barbarian xyz"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("barbarian x", 10)
    assert set(autocomplete_terms) == {"barbarian xyz"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("n.a.m", 10)
    assert set(autocomplete_terms) == {"n.a.m.e"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("n.a.m.", 10)
    assert set(autocomplete_terms) == {"n.a.m.e"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("n.a.m.e", 10)
    assert set(autocomplete_terms) == {"n.a.m.e", "n.a.m.e: foobar"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("n.a.m.e ", 10)
    assert set(autocomplete_terms) == {"n.a.m.e ", "n.a.m.e foobar"}

    autocomplete_terms = metadata_store.get_auto_complete_terms("n.a.m.e f", 10)
    assert set(autocomplete_terms) == {"n.a.m.e foobar"}


@db_session
def test_get_autocomplete_terms_max(metadata_store):
    """
    Test fetching autocompletion terms from the database with a maximum number of terms
    """
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="mountains sheeps wolf", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="lakes sheep", tags="video"))
    metadata_store.TorrentMetadata.from_dict(dict(rnd_torrent(), title="regular sheepish guy", tags="video"))

    autocomplete_terms = metadata_store.get_auto_complete_terms("sheep", 2)
    assert len(autocomplete_terms) == 2
    # Check that we can chew the special character "."
    autocomplete_terms = metadata_store.get_auto_complete_terms(".", 2)


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

    torrents = metadata_store.get_entries(first=1, last=5)
    assert len(torrents) == 5

    count = metadata_store.get_entries_count(metadata_type=REGULAR_TORRENT)
    assert count == 25

    # Test fetching torrents in a channel
    channel_pk = metadata_store.ChannelNode._my_key.pub().key_to_bin()[10:]

    args = dict(channel_pk=channel_pk, hide_xxx=True, exclude_deleted=True, metadata_type=REGULAR_TORRENT)
    torrents = metadata_store.get_entries_query(**args)[:]
    assert tlist[-5:-2] == list(torrents)[::-1]

    count = metadata_store.get_entries_count(**args)
    assert count == 3

    args = dict(sort_by='title', channel_pk=channel_pk, origin_id=0, metadata_type=REGULAR_TORRENT)
    torrents = metadata_store.get_entries(first=1, last=10, **args)
    assert len(torrents) == 5

    count = metadata_store.get_entries_count(**args)
    assert count == 5

    # Test that channels get priority over torrents when querying for mixed content
    args = dict(sort_by='size', sort_desc=True, channel_pk=channel_pk, origin_id=0)
    torrents = metadata_store.get_entries(first=1, last=10, **args)
    assert torrents[0].metadata_type == CHANNEL_TORRENT

    args = dict(sort_by='size', sort_desc=False, channel_pk=channel_pk, origin_id=0)
    torrents = metadata_store.get_entries(first=1, last=10, **args)
    assert torrents[-1].metadata_type == CHANNEL_TORRENT

    # Test getting entries by timestamp range
    args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp", 3, 30),))
    torrents = metadata_store.get_entries(first=1, last=10, **args)
    assert sorted([t.timestamp for t in torrents]) == list(range(25, 30))

    # Test catching SQL injection
    args = dict(channel_pk=channel_pk, origin_id=0, attribute_ranges=(("timestamp < 3 and g.timestamp", 3, 30),))
    with pytest.raises(AttributeError):
        metadata_store.get_entries(**args)

    # Test getting entry by id_
    with db_session:
        entry = metadata_store.TorrentMetadata(id_=123, infohash=random_infohash())
    args = dict(channel_pk=channel_pk, id_=123)
    torrents = metadata_store.get_entries(first=1, last=10, **args)
    assert list(torrents) == [entry]

    # Test getting complete channels
    with db_session:
        complete_chan = metadata_store.ChannelMetadata(
            infohash=random_infohash(), title='bla', local_version=222, timestamp=222
        )
        incomplete_chan = metadata_store.ChannelMetadata(
            infohash=random_infohash(), title='bla', local_version=222, timestamp=223
        )
        channels = metadata_store.get_entries(complete_channel=True)
        assert [complete_chan] == channels


@db_session
def test_get_entries_health_checked_after(metadata_store):
    # Test querying for torrents last checked after a certain moment in time

    # Add a torrent checked just now
    t1 = metadata_store.TorrentMetadata(infohash=random_infohash())
    t1.health.last_check = int(time())

    # Add a torrent checked awhile ago
    t2 = metadata_store.TorrentMetadata(infohash=random_infohash())
    t2.health.last_check = t1.health.last_check - 10000

    # Check that only the more recently checked torrent is returned, because we limited the selection by time
    torrents = metadata_store.get_entries(health_checked_after=t2.health.last_check + 1)
    assert torrents == [t1]


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


@db_session
def test_popular_torrens_with_metadata_type(metadata_store):
    """
    Test that `popular` argument cannot be combiner with `metadata_type` argument
    """

    with pytest.raises(TypeError):
        metadata_store.get_entries(popular=True)

    metadata_store.get_entries(popular=True, metadata_type=REGULAR_TORRENT)

    with pytest.raises(TypeError):
        metadata_store.get_entries(popular=True, metadata_type=CHANNEL_TORRENT)

    with pytest.raises(TypeError):
        metadata_store.get_entries(popular=True, metadata_type=[REGULAR_TORRENT, CHANNEL_TORRENT])
