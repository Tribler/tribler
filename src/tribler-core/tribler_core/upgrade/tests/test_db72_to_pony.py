import contextlib
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.orm_bindings.channel_node import COMMITTED, LEGACY_ENTRY
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.db72_to_pony import (
    CONVERSION_FINISHED,
    CONVERSION_FROM_72,
    CONVERSION_FROM_72_CHANNELS,
    CONVERSION_FROM_72_DISCOVERED,
    CONVERSION_FROM_72_PERSONAL,
    CONVERSION_STARTED,
    already_upgraded,
    cleanup_pony_experimental_db,
    new_db_version_ok,
    old_db_version_ok,
    should_upgrade,
)


OLD_DB_SAMPLE = TESTS_DATA_DIR / 'upgrade_databases/tribler_v29.sdb'


def test_get_personal_channel_title(dispersy_to_pony_migrator):
    assert dispersy_to_pony_migrator.personal_channel_title


def test_get_old_torrents_count(dispersy_to_pony_migrator):
    assert dispersy_to_pony_migrator.get_old_torrents_count() == 19


def test_get_personal_torrents_count(dispersy_to_pony_migrator):
    assert dispersy_to_pony_migrator.get_personal_channel_torrents_count() == 2


@pytest.mark.asyncio
async def test_convert_personal_channel(dispersy_to_pony_migrator, metadata_store):
    async def check_channel():
        await dispersy_to_pony_migrator.convert_personal_channel()
        with db_session:
            my_channel = metadata_store.ChannelMetadata.get_my_channels().first()

        assert len(my_channel.contents_list) == 2
        assert my_channel.num_entries == 2
        for t in my_channel.contents_list:
            assert t.has_valid_signature()
        assert my_channel.has_valid_signature()
        assert dispersy_to_pony_migrator.personal_channel_title[:200] == my_channel.title

    await check_channel()

    # Now check the case where previous conversion of the personal channel had failed
    with db_session:
        metadata_store.MiscData.get_for_update(name=CONVERSION_FROM_72_PERSONAL).value = CONVERSION_STARTED
    await check_channel()


@pytest.mark.asyncio
@db_session
async def test_convert_legacy_channels(dispersy_to_pony_migrator, metadata_store):
    async def check_conversion():
        await dispersy_to_pony_migrator.convert_discovered_torrents()
        dispersy_to_pony_migrator.convert_discovered_channels()
        chans = metadata_store.ChannelMetadata.get_entries()

        assert len(chans) == 2
        for c in chans:
            assert dispersy_to_pony_migrator.personal_channel_title[:200] != c.title[:200]
            assert c.status == LEGACY_ENTRY
            assert c.contents_list
            for t in c.contents_list:
                assert t.status == COMMITTED
    await check_conversion()

    # Now check the case where the previous conversion failed at channels conversion
    metadata_store.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS).value = CONVERSION_STARTED
    await check_conversion()

    # Now check the case where the previous conversion stopped at torrents conversion
    metadata_store.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS).delete()
    metadata_store.MiscData.get_for_update(name=CONVERSION_FROM_72_DISCOVERED).value = CONVERSION_STARTED
    for d in metadata_store.TorrentMetadata.select()[:10][:10]:
        d.delete()
    await check_conversion()


@db_session
def test_update_trackers(dispersy_to_pony_migrator, metadata_store):
    tr = metadata_store.TrackerState(url="http://ipv6.torrent.ubuntu.com:6969/announce")
    dispersy_to_pony_migrator.update_trackers_info()
    assert tr.failures == 2
    assert tr.alive
    assert tr.last_check == 1548776649


def test_old_db_version_check(tmpdir):
    # Correct old database
    assert old_db_version_ok(OLD_DB_SAMPLE)

    # Wrong old database version
    old_db = tmpdir / 'old.db'
    shutil.copyfile(OLD_DB_SAMPLE, old_db)
    with contextlib.closing(sqlite3.connect(old_db)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE MyInfo SET value = 28 WHERE entry == 'version'")
    assert not old_db_version_ok(old_db)


def test_cleanup_pony_experimental_db(tmpdir, metadata_store):
    # Assert True is returned for a garbled db and nothing is done with it
    garbled_db = tmpdir / 'garbled.db'
    with open(garbled_db, 'w') as f:
        f.write("123")

    with pytest.raises(sqlite3.DatabaseError):
        cleanup_pony_experimental_db(garbled_db)
    assert garbled_db.exists()

    # Create a Pony database of older experimental version
    pony_db = Path(tmpdir) / 'test.db'
    pony_db_bak = Path(tmpdir) / 'pony2.db'
    metadata_store.shutdown()
    shutil.copyfile(pony_db, pony_db_bak)

    with contextlib.closing(sqlite3.connect(pony_db)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute("DROP TABLE MiscData")

    # Assert older experimental version is deleted
    cleanup_pony_experimental_db(pony_db)
    assert not pony_db.exists()

    # Assert recent database version is left untouched
    cleanup_pony_experimental_db(pony_db_bak)
    assert pony_db_bak.exists()


def test_new_db_version_ok(tmpdir, metadata_store):
    pony_db_path = Path(tmpdir) / 'test.db'
    metadata_store.shutdown()

    # Correct new database
    assert new_db_version_ok(pony_db_path)

    # Wrong new database version
    with contextlib.closing(sqlite3.connect(pony_db_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE MiscData SET value = 12313512 WHERE name == 'db_version'")
    assert not new_db_version_ok(pony_db_path)


def test_already_upgraded(tmpdir, metadata_store):
    pony_db_path = Path(tmpdir) / 'test.db'
    my_key = default_eccrypto.generate_key("curve25519")
    metadata_store.shutdown()

    assert not already_upgraded(pony_db_path)

    mds = MetadataStore(pony_db_path, tmpdir, my_key)
    with db_session:
        mds.MiscData(name=CONVERSION_FROM_72, value=CONVERSION_FINISHED)
    mds.shutdown()

    assert already_upgraded(pony_db_path)


def test_should_upgrade(tmpdir):
    from tribler_core.upgrade import db72_to_pony
    pony_db = tmpdir / 'pony.db'

    # Old DB does not exist
    assert not should_upgrade(Path(tmpdir) / 'nonexistent.db', None)

    # Old DB is not OK
    db72_to_pony.old_db_version_ok = lambda _: False
    assert not should_upgrade(OLD_DB_SAMPLE, None)

    # Pony DB does not exist
    db72_to_pony.old_db_version_ok = lambda _: True
    assert should_upgrade(OLD_DB_SAMPLE, pony_db)

    # Bad Pony DB
    with open(pony_db, 'w') as f:
        f.write("")
    assert not should_upgrade(OLD_DB_SAMPLE, pony_db, logger=Mock())
