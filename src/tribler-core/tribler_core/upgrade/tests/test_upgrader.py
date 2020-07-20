import os
import shutil
from asyncio import Future
from pathlib import Path

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.upgrade import cleanup_noncompliant_channel_torrents
from tribler_core.utilities.configparser import CallbackConfigParser


@pytest.mark.asyncio
async def test_update_status_text(upgrader, session):
    test_future = Future()

    def on_upgrade_tick(status_text):
        assert status_text == "12345"
        test_future.set_result(None)

    session.notifier.add_observer(NTFY.UPGRADER_TICK, on_upgrade_tick)
    upgrader.update_status("12345")
    await test_future


@pytest.mark.asyncio
async def test_upgrade_72_to_pony(upgrader, session):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
    old_database_path = session.config.get_state_dir() / 'sqlite' / 'tribler.sdb'
    new_database_path = session.config.get_state_dir() / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    await upgrader.run()
    channels_dir = session.config.get_chant_channels_dir()
    mds = MetadataStore(new_database_path, channels_dir, session.trustchain_keypair)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 24
    mds.shutdown()


def test_upgrade_pony_db_6to7(upgrader, session):
    """
    Test that channels and torrents with forbidden words are cleaned up during upgrade from Pony db ver 6 to 7.
    Also, check that the DB version is upgraded.
    :return:
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
    old_database_path = session.config.get_state_dir() / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.upgrade_pony_db_6to7()
    channels_dir = session.config.get_chant_channels_dir()
    mds = MetadataStore(old_database_path, channels_dir, session.trustchain_keypair)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 23
        assert mds.ChannelMetadata.select().count() == 2
        assert int(mds.MiscData.get(name="db_version").value) == 7
    mds.shutdown()


def test_upgrade_pony_db_7to8(upgrader, session):
    """
    Test that proper additionald index is created.
    Also, check that the DB version is upgraded.
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v7.db'
    old_database_path = session.config.get_state_dir() / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.upgrade_pony_db_7to8()
    channels_dir = session.config.get_chant_channels_dir()
    mds = MetadataStore(old_database_path, channels_dir, session.trustchain_keypair)
    with db_session:
        assert int(mds.MiscData.get(name="db_version").value) == 8
        assert mds.Vsids[0].exp_period == 24.0 * 60 * 60 * 3
        assert list(mds._db.execute('PRAGMA index_info("idx_channelnode__metadata_type")'))
    mds.shutdown()


@pytest.mark.asyncio
async def test_upgrade_pony_db_complete(upgrader, session):
    """
    Test complete update sequence for Pony DB (e.g. 6->7->8)
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
    old_database_path = session.config.get_state_dir() / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    await upgrader.run()
    channels_dir = session.config.get_chant_channels_dir()
    mds = MetadataStore(old_database_path, channels_dir, session.trustchain_keypair)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 23
        assert mds.ChannelMetadata.select().count() == 2
        assert int(mds.MiscData.get(name="db_version").value) == 8
        assert list(mds._db.execute('PRAGMA index_info("idx_channelnode__metadata_type")'))
    mds.shutdown()


@pytest.mark.asyncio
async def test_skip_upgrade_72_to_pony(upgrader, session):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
    old_database_path = session.config.get_state_dir() / 'sqlite' / 'tribler.sdb'
    new_database_path = session.config.get_state_dir() / 'sqlite' / 'metadata.db'
    channels_dir = session.config.get_chant_channels_dir()

    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.skip()
    await upgrader.run()
    mds = MetadataStore(new_database_path, channels_dir, session.trustchain_keypair)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 0
        assert mds.ChannelMetadata.select().count() == 0
    mds.shutdown()


def test_delete_noncompliant_state(tmpdir):
    state_dir = TESTS_DATA_DIR / 'noncompliant_state_dir'
    shutil.copytree(str(state_dir), str(tmpdir / "test"))
    cleanup_noncompliant_channel_torrents(Path(tmpdir) / "test")

    # Check cleanup of the channels dir
    dir_listing = list((Path(tmpdir) / "test" / "channels").iterdir())
    assert len(dir_listing) == 3
    for f in (Path(tmpdir) / "test" / "channels").iterdir():
        assert CHANNEL_DIR_NAME_LENGTH == len(f.stem)

    # Check cleanup of torrent state dir
    checkpoints_dir = tmpdir / "test" / "dlcheckpoints"
    dir_listing = os.listdir(checkpoints_dir)
    assert len(dir_listing) == 1
    file_path = checkpoints_dir / dir_listing[0]
    pstate = CallbackConfigParser()
    pstate.read_file(file_path)
    assert CHANNEL_DIR_NAME_LENGTH == len(pstate.get('state', 'metainfo')['info']['name'])
