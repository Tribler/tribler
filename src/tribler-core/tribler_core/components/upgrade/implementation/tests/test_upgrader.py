import os
import shutil
from asyncio import Future
from pathlib import Path
from unittest.mock import Mock

import pytest
from pony.orm import db_session, select

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from tribler_common.simpledefs import NTFY
from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.components.metadata_store.db.store import CURRENT_DB_VERSION, MetadataStore
from tribler_core.components.upgrade.implementation.db8_to_db10 import calc_progress
from tribler_core.components.upgrade.implementation.upgrade import TriblerUpgrader, \
    cleanup_noncompliant_channel_torrents
from tribler_core.notifier import Notifier
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.configparser import CallbackConfigParser


@pytest.fixture
def state_dir(tmp_path):
    os.makedirs(tmp_path / 'sqlite')
    return tmp_path


@pytest.fixture
def channels_dir(state_dir):
    channels_dir = state_dir / 'channels'
    os.makedirs(channels_dir)
    return channels_dir


@pytest.fixture
def trustchain_keypair():
    return LibNaCLSK()


@pytest.fixture
def upgrader(state_dir, channels_dir, trustchain_keypair):
    return TriblerUpgrader(state_dir, channels_dir, trustchain_keypair, Mock())


@pytest.fixture
def notifier():
    return Notifier()


@pytest.mark.asyncio
async def test_update_status_text(upgrader, notifier):
    upgrader.notifier = notifier
    test_future = Future()

    def on_upgrade_tick(status_text):
        assert status_text == "12345"
        test_future.set_result(None)

    notifier.add_observer(NTFY.UPGRADER_TICK, on_upgrade_tick)
    upgrader.update_status("12345")
    await test_future


@pytest.mark.asyncio
async def test_upgrade_72_to_pony(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
    old_database_path = state_dir / 'sqlite' / 'tribler.sdb'
    new_database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    await upgrader.run()
    mds = MetadataStore(new_database_path, channels_dir, trustchain_keypair, db_version=6)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 24
    mds.shutdown()


def test_upgrade_pony_db_6to7(upgrader, channels_dir, state_dir, trustchain_keypair):
    """
    Test that channels and torrents with forbidden words are cleaned up during upgrade from Pony db ver 6 to 7.
    Also, check that the DB version is upgraded.
    :return:
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
    old_database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.upgrade_pony_db_6to7()
    mds = MetadataStore(old_database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=7)
    with db_session:
        assert mds.TorrentMetadata.select().count() == 23
        assert mds.ChannelMetadata.select().count() == 2
        assert int(mds.MiscData.get(name="db_version").value) == 7
    mds.shutdown()


def test_upgrade_pony_db_7to8(upgrader, channels_dir, state_dir, trustchain_keypair):
    """
    Test that proper additional index is created.
    Also, check that the DB version is upgraded.
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v7.db'
    old_database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.upgrade_pony_db_7to8()
    mds = MetadataStore(old_database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=8)
    with db_session:
        assert int(mds.MiscData.get(name="db_version").value) == 8
        assert mds.Vsids[0].exp_period == 24.0 * 60 * 60 * 3
        assert list(mds._db.execute('PRAGMA index_info("idx_channelnode__metadata_type")'))
    mds.shutdown()


@pytest.mark.asyncio
async def test_upgrade_pony_db_complete(upgrader, channels_dir, state_dir, trustchain_keypair):
    """
    Test complete update sequence for Pony DB (e.g. 6->7->8)
    """
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
    old_database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, old_database_path)

    await upgrader.run()
    mds = MetadataStore(old_database_path, channels_dir, trustchain_keypair)
    db = mds._db  # pylint: disable=protected-access

    existing_indexes = [
        'idx_channelnode__metadata_type__partial',
        'idx_channelnode__metadata_subscribed__partial',
        'idx_torrentstate__last_check__partial',
    ]

    removed_indexes = [
        'idx_channelnode__public_key',
        'idx_channelnode__status',
        'idx_channelnode__size',
        'idx_channelnode__share',
        'idx_channelnode__subscribed',
        'idx_channelnode__votes',
        'idx_channelnode__tags',
        'idx_channelnode__title',
        'idx_channelnode__num_entries',
        'idx_channelnode__metadata_type',
    ]

    with db_session:
        assert mds.TorrentMetadata.select().count() == 23
        assert mds.ChannelMetadata.select().count() == 2
        assert int(mds.MiscData.get(name="db_version").value) == CURRENT_DB_VERSION
        for index_name in existing_indexes:
            assert list(db.execute(f'PRAGMA index_info("{index_name}")'))
        for index_name in removed_indexes:
            assert not list(db.execute(f'PRAGMA index_info("{index_name}")'))

        assert upgrader.trigger_exists(db, 'torrentstate_ai')
        assert upgrader.trigger_exists(db, 'torrentstate_au')
    mds.shutdown()


@pytest.mark.asyncio
async def test_skip_upgrade_72_to_pony(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
    old_database_path = state_dir / 'sqlite' / 'tribler.sdb'
    new_database_path = state_dir / 'sqlite' / 'metadata.db'

    shutil.copyfile(old_db_sample, old_database_path)

    upgrader.skip()
    await upgrader.run()
    mds = MetadataStore(new_database_path, channels_dir, trustchain_keypair, db_version=6)
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


@pytest.mark.asyncio
async def test_upgrade_pony_8to10(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
    database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, database_path)

    upgrader.upgrade_pony_db_6to7()
    upgrader.upgrade_pony_db_7to8()
    await upgrader.upgrade_pony_db_8to10()
    mds = MetadataStore(database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=10)
    with db_session:
        assert int(mds.MiscData.get(name="db_version").value) == 10
        assert mds.ChannelNode.select().count() == 23
    mds.shutdown()


@pytest.mark.asyncio
async def test_upgrade_pony_10to11(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v10.db'
    database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, database_path)

    upgrader.upgrade_pony_db_10to11()
    mds = MetadataStore(database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        # pylint: disable=protected-access
        assert upgrader.column_exists_in_table(mds._db, 'TorrentState', 'self_checked')
        assert int(mds.MiscData.get(name="db_version").value) == 11
    mds.shutdown()


def test_upgrade_pony11to12(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v11.db'
    database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, database_path)

    upgrader.upgrade_pony_db_11to12()
    mds = MetadataStore(database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        # pylint: disable=protected-access
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'json_text')
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'binary_data')
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'data_type')
        assert int(mds.MiscData.get(name="db_version").value) == 12
    mds.shutdown()


def test_upgrade_pony12to13(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v12.db'
    database_path = state_dir / 'sqlite' / 'metadata.db'
    shutil.copyfile(old_db_sample, database_path)

    upgrader.upgrade_pony_db_12to13()
    mds = MetadataStore(database_path, channels_dir, trustchain_keypair, check_tables=False, db_version=12)
    db = mds._db  # pylint: disable=protected-access

    existing_indexes = [
        'idx_channelnode__metadata_type__partial',
        'idx_channelnode__metadata_subscribed__partial',
        'idx_torrentstate__last_check__partial',
    ]

    removed_indexes = [
        'idx_channelnode__public_key',
        'idx_channelnode__status',
        'idx_channelnode__size',
        'idx_channelnode__share',
        'idx_channelnode__subscribed',
        'idx_channelnode__votes',
        'idx_channelnode__tags',
        'idx_channelnode__title',
        'idx_channelnode__num_entries',
        'idx_channelnode__metadata_type',
    ]

    with db_session:
        assert mds.TorrentMetadata.select().count() == 23
        assert mds.ChannelMetadata.select().count() == 2
        assert int(mds.MiscData.get(name="db_version").value) == CURRENT_DB_VERSION
        for index_name in existing_indexes:
            assert list(db.execute(f'PRAGMA index_info("{index_name}")')), index_name
        for index_name in removed_indexes:
            assert not list(db.execute(f'PRAGMA index_info("{index_name}")')), index_name

        assert upgrader.trigger_exists(db, 'torrentstate_ai')
        assert upgrader.trigger_exists(db, 'torrentstate_au')
    mds.shutdown()


def test_calc_progress():
    EPSILON = 0.001
    assert calc_progress(0) == pytest.approx(0.0, abs=EPSILON)
    assert calc_progress(0, 1) == pytest.approx(0.0, abs=EPSILON)

    assert calc_progress(1, 0) == pytest.approx(75.0, abs=EPSILON)
    assert calc_progress(10, 0) == pytest.approx(99.173553, abs=EPSILON)

    assert calc_progress(0, 100) == pytest.approx(0.0, abs=EPSILON)
    assert calc_progress(10, 100) == pytest.approx(17.206395, abs=EPSILON)
    assert calc_progress(50, 100) == pytest.approx(55.260734, abs=EPSILON)
    assert calc_progress(80, 100) == pytest.approx(68.862366, abs=EPSILON)
    assert calc_progress(100, 100) == pytest.approx(74.750624, abs=EPSILON)
    assert calc_progress(200, 100) == pytest.approx(88.740742, abs=EPSILON)
    assert calc_progress(1000, 100) == pytest.approx(99.158472, abs=EPSILON)


@pytest.mark.asyncio
async def test_upgrade_bw_accounting_db_8to9(upgrader, channels_dir, state_dir, trustchain_keypair):
    old_db_sample = TESTS_DATA_DIR / 'upgrade_databases' / 'bandwidth_v8.db'
    database_path = state_dir / 'sqlite' / 'bandwidth.db'
    shutil.copyfile(old_db_sample, database_path)

    upgrader.upgrade_bw_accounting_db_8to9()
    db = BandwidthDatabase(database_path, trustchain_keypair.key.pk)
    with db_session:
        assert not list(select(tx for tx in db.BandwidthTransaction))
        assert not list(select(item for item in db.BandwidthHistory))
        assert int(db.MiscData.get(name="db_version").value) == 9
    db.shutdown()
