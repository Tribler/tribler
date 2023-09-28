import os
import shutil
import time
from pathlib import Path
from typing import Set
from unittest.mock import patch

import pytest
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session, select

from tribler.core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler.core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler.core.components.metadata_store.db.store import CURRENT_DB_VERSION, MetadataStore
from tribler.core.tests.tools.common import TESTS_DATA_DIR
from tribler.core.upgrade.db8_to_db10 import calc_progress
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.tags_db import TagDatabase
from tribler.core.upgrade.upgrade import TriblerUpgrader, cleanup_noncompliant_channel_torrents
from tribler.core.utilities.configparser import CallbackConfigParser
from tribler.core.utilities.utilities import random_infohash


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
    return TriblerUpgrader(state_dir, channels_dir, trustchain_keypair, secondary_key=trustchain_keypair)


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
    db = mds.db

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


def test_upgrade_pony_10to11(upgrader, channels_dir, mds_path, trustchain_keypair):
    _copy('pony_v10.db', mds_path)

    upgrader.upgrade_pony_db_10to11()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        assert upgrader.column_exists_in_table(mds.db, 'TorrentState', 'self_checked')
        assert mds.get_value("db_version") == '11'
    mds.shutdown()


def test_upgrade_pony11to12(upgrader, channels_dir, mds_path, trustchain_keypair):
    _copy('pony_v11.db', mds_path)

    upgrader.upgrade_pony_db_11to12()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=11)
    with db_session:
        assert upgrader.column_exists_in_table(mds.db, 'ChannelNode', 'json_text')
        assert upgrader.column_exists_in_table(mds.db, 'ChannelNode', 'binary_data')
        assert upgrader.column_exists_in_table(mds.db, 'ChannelNode', 'data_type')
        assert mds.get_value("db_version") == '12'
    mds.shutdown()


def test_upgrade_pony13to14(upgrader: TriblerUpgrader, state_dir, channels_dir, trustchain_keypair, mds_path):
    tags_path = state_dir / 'sqlite/tags.db'

    _copy(source_name='pony_v13.db', target=mds_path)
    _copy(source_name='tags_v13.db', target=tags_path)

    upgrader.upgrade_pony_db_13to14()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False)

    with db_session:
        assert upgrader.column_exists_in_table(mds.db, 'ChannelNode', 'tag_processor_version')
        assert mds.get_value('db_version') == '14'


def test_upgrade_pony13to14_no_tags(upgrader: TriblerUpgrader, state_dir, channels_dir, trustchain_keypair, mds_path):
    tags_path = state_dir / 'sqlite/tags.db'

    _copy(source_name='pony_v13.db', target=mds_path)

    upgrader.upgrade_pony_db_13to14()  # No exception if the tags database file is missing before the upgrade
    assert not tags_path.exists()  # Tags' database file is still missing after upgrade if it has not existed before

    # TagsComponent specifies create_tables=True option when it creates TagDatabase.
    # That means that the empty tags' database will be automatically created if it was not already present
    tags = TagDatabase(str(tags_path), create_tables=True, check_tables=False)
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False)

    with db_session:
        def _exists(db, table, column):
            return upgrader.column_exists_in_table(db, table, column)

        # The end result is the same as in the previous test
        assert _exists(mds.db, 'ChannelNode', 'tag_processor_version')
        assert _exists(tags.instance, 'TorrentTagOp', 'auto_generated')

        assert mds.get_value('db_version') == '14'


def test_upgrade_pony14to15(upgrader: TriblerUpgrader, channels_dir, trustchain_keypair, mds_path):
    _copy(source_name='pony_v14.db', target=mds_path)

    now = int(time.time())
    in_the_past = now - 1000
    in_the_future = now + 1000
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False)

    def _add_torrent_state(self_checked, last_check):
        mds.TorrentState(infohash=random_infohash(), seeders=1, leechers=1,
                         self_checked=self_checked, last_check=last_check)

    with db_session:
        mds.TorrentState(infohash=random_infohash())  # a TorrentState for an infohash that was never checked
        _add_torrent_state(self_checked=0, last_check=in_the_past)
        _add_torrent_state(self_checked=1, last_check=in_the_past)
        _add_torrent_state(self_checked=0, last_check=in_the_future)
        _add_torrent_state(self_checked=1, last_check=in_the_future)

    def _execute(sql, **kwargs):
        return mds.db.execute(sql, kwargs).fetchone()[0]

    with db_session:
        assert mds.get_value('db_version') == '14'
        # Total number of records should not be changed after the upgrade
        assert _execute('select count(*) from TorrentState') == 5
        # There will be fewer records with nonzero seeders/leechers after the upgrade
        assert _execute('select count(*) from TorrentState where seeders > 0 or leechers > 0') == 4
        # Before the upgrade, the database contained several corrupted records, and SQL queries were able to find them
        assert _execute('select count(*) from TorrentState where self_checked > 0') == 2
        assert _execute('select count(*) from TorrentState where last_check > $x', x=now) == 2

    mds.shutdown()

    # The upgrade should clear the self_checked flag for all records, as due to a bug, we cannot be sure they are
    # really self-checked. Also, it should clear all records with the future last_check timestamp value, resetting
    # their seeders/leechers values
    upgrader.upgrade_pony_db_14to15()

    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False)
    with db_session:
        assert mds.get_value('db_version') == '15'
        # After the upgrade, the same SQL queries found the same total number of records
        assert _execute('select count(*) from TorrentState') == 5
        # Records with correct last_check values still have their seeders/leechers values;
        # only the records with incorrect last_check values were cleared
        assert _execute('select count(*) from TorrentState where seeders > 0 or leechers > 0') == 2
        # After the upgrade, the same SQL queries found no corrupted records
        assert _execute('select count(*) from TorrentState where self_checked > 0') == 0
        assert _execute('select count(*) from TorrentState where last_check > $x', x=now) == 0

    mds.shutdown()


def test_upgrade_pony12to13(upgrader, channels_dir, mds_path, trustchain_keypair):  # pylint: disable=W0621
    _copy('pony_v12.db', mds_path)

    upgrader.upgrade_pony_db_12to13()
    mds = MetadataStore(mds_path, channels_dir, trustchain_keypair, check_tables=False, db_version=12)
    db = mds.db

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


def test_upgrade_bw_accounting_db_8to9(upgrader, state_dir, trustchain_keypair):
    bandwidth_path = state_dir / 'sqlite/bandwidth.db'
    _copy('bandwidth_v8.db', bandwidth_path)

    upgrader.upgrade_bw_accounting_db_8to9()
    db = BandwidthDatabase(bandwidth_path, trustchain_keypair.key.pk)
    with db_session:
        assert not list(select(tx for tx in db.BandwidthTransaction))
        assert not list(select(item for item in db.BandwidthHistory))
        assert int(db.MiscData.get(name="db_version").value) == 9
    db.shutdown()


def test_remove_old_logs(upgrader: TriblerUpgrader, state_dir: Path, tmp_path):
    """Ensure that the `remove_old_logs` function removes only logs"""

    # create Tribler folder structure
    def _create(path: str) -> Set[Path]:
        log_file = upgrader.state_dir / path
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text('content')

        return {log_file}

    def _count():
        glob_result = list(upgrader.state_dir.glob('**/*'))
        files = [f for f in glob_result if f.is_file()]
        return len(files)

    # log files
    expected = set()
    expected |= _create('7.12/log/resources.log')
    expected |= _create('7.11/log/resources.log')
    expected |= _create('crash-report.log')
    expected |= _create('tribler-core-error.log')
    expected |= _create('tribler-gui-info.log.1')

    # no log files
    _create('7.12/sqlite/metadata.db')
    _create('version_history.json')
    _create('log_config.json')

    assert _count() == 8

    removed, left = upgrader.remove_old_logs()
    assert _count() == 3
    assert set(removed) == expected
    assert not left


def test_remove_old_logs_with_exception(upgrader: TriblerUpgrader, state_dir: Path, tmp_path):
    """ Ensure that in the case that one of the files raises OSError during removing procedure,
    it is not affect remove procedure of other files.

    In this test two files will be created. The normal file and the file that will raise `PermissionError` exception.

    At the end, the normal file must be removed and the file with the side effect must remain.
    """
    normal_log_file = Path(tmp_path) / 'normal.log'
    normal_log_file.write_text('content')

    side_effect_log_file = Path(tmp_path) / 'side_effect.log'
    side_effect_log_file.write_text('content')

    def patched_unlink(self, *_, **__):
        if self == side_effect_log_file:
            raise PermissionError

        os.remove(self)

    with patch.object(Path, 'unlink', patched_unlink):
        removed, left = upgrader.remove_old_logs()

    assert removed == [normal_log_file]
    assert left == [side_effect_log_file]
    assert not normal_log_file.exists()
    assert side_effect_log_file.exists()
