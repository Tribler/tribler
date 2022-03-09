import os
import shutil
from pathlib import Path

from ipv8.keyvault.private.libnaclkey import LibNaCLSK

from pony.orm import db_session, select

import pytest

from tribler.core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler.core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler.core.components.metadata_store.db.store import CURRENT_DB_VERSION, MetadataStore
from tribler.core.components.tag.db.tag_db import TagDatabase
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.upgrade.db8_to_db10 import calc_progress
from tribler.core.upgrade.upgrade import TriblerUpgrader, cleanup_noncompliant_channel_torrents
from tribler.core.utilities.configparser import CallbackConfigParser

# pylint: disable=redefined-outer-name, protected-access

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
    return TriblerUpgrader(state_dir, channels_dir, trustchain_keypair)


@pytest.fixture
def mds_path(state_dir):
    return state_dir / 'sqlite/metadata.db'


def _copy(source_name, target):
    source = TESTS_DATA_DIR / 'upgrade_databases' / source_name
    shutil.copyfile(source, target)


def test_upgrade_pony_db_complete(upgrader, channels_dir, state_dir, trustchain_keypair,
                                  mds_path):  # pylint: disable=W0621
    """
    Test complete update sequence for Pony DB (e.g. 6->7->8)
    """
    tags_path = state_dir / 'sqlite/tags.db'

    _copy(source_name='pony_v8.db', target=mds_path)
    _copy(source_name='tags_v13.db', target=tags_path)

    upgrader.run()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair)
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
        assert mds.get_value("db_version") == str(CURRENT_DB_VERSION)
        for index_name in existing_indexes:
            assert list(db.execute(f'PRAGMA index_info("{index_name}")'))
        for index_name in removed_indexes:
            assert not list(db.execute(f'PRAGMA index_info("{index_name}")'))

        assert upgrader.trigger_exists(db, 'torrentstate_ai')
        assert upgrader.trigger_exists(db, 'torrentstate_au')
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


def test_upgrade_pony_8to10(upgrader, channels_dir, mds_path, trustchain_keypair):  # pylint: disable=W0621
    _copy('pony_v8.db', mds_path)

    upgrader.upgrade_pony_db_8to10()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=10)
    with db_session:
        assert mds.get_value("db_version") == '10'
        assert mds.ChannelNode.select().count() == 23
    mds.shutdown()


@pytest.mark.asyncio
async def test_upgrade_pony_10to11(upgrader, channels_dir, mds_path, trustchain_keypair):
    _copy('pony_v10.db', mds_path)

    upgrader.upgrade_pony_db_10to11()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        # pylint: disable=protected-access
        assert upgrader.column_exists_in_table(mds._db, 'TorrentState', 'self_checked')
        assert mds.get_value("db_version") == '11'
    mds.shutdown()


def test_upgrade_pony11to12(upgrader, channels_dir, mds_path, trustchain_keypair):
    _copy('pony_v11.db', mds_path)

    upgrader.upgrade_pony_db_11to12()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        # pylint: disable=protected-access
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'json_text')
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'binary_data')
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'data_type')
        assert mds.get_value("db_version") == '12'
    mds.shutdown()


def test_upgrade_pony13to14(upgrader: TriblerUpgrader, state_dir, channels_dir, trustchain_keypair, mds_path):
    tags_path = state_dir / 'sqlite/tags.db'

    _copy(source_name='pony_v13.db', target=mds_path)
    _copy(source_name='tags_v13.db', target=tags_path)

    upgrader.upgrade_pony_db_13to14()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False)
    tags = TagDatabase(str(tags_path), create_tables=False, check_tables=False)

    with db_session:
        assert upgrader.column_exists_in_table(mds._db, 'ChannelNode', 'tag_processor_version')
        assert upgrader.column_exists_in_table(tags.instance, 'TorrentTagOp', 'auto_generated')
        assert mds.get_value('db_version') == '14'


def test_upgrade_pony12to13(upgrader, channels_dir, mds_path, trustchain_keypair):  # pylint: disable=W0621
    _copy('pony_v12.db', mds_path)

    upgrader.upgrade_pony_db_12to13()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=12)
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
        assert mds.get_value("db_version") == '13'
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
async def test_upgrade_bw_accounting_db_8to9(upgrader, state_dir, trustchain_keypair):
    bandwidth_path = state_dir / 'sqlite/bandwidth.db'
    _copy('bandwidth_v8.db', bandwidth_path)

    upgrader.upgrade_bw_accounting_db_8to9()
    db = BandwidthDatabase(bandwidth_path, trustchain_keypair.key.pk)
    with db_session:
        assert not list(select(tx for tx in db.BandwidthTransaction))
        assert not list(select(item for item in db.BandwidthHistory))
        assert int(db.MiscData.get(name="db_version").value) == 9
    db.shutdown()
