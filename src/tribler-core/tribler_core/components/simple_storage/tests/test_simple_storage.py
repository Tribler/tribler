import asyncio
from json import JSONDecodeError
from unittest.mock import Mock, call, patch

import pytest

from tribler_core.components.simple_storage.simple_storage import DEFAULT_SAVE_INTERVAL, SimpleStorage, StorageData

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def simple_storage(tmp_path):
    return SimpleStorage(path=tmp_path / 'storage.json')


def test_constructor(simple_storage: SimpleStorage):
    assert simple_storage.logger
    assert simple_storage.data == StorageData()
    assert simple_storage.path
    assert simple_storage.save_interval == DEFAULT_SAVE_INTERVAL
    assert simple_storage._loop
    assert simple_storage._task


@patch('tribler_core.components.simple_storage.simple_storage.StorageData.parse_file',
       Mock(side_effect=FileNotFoundError))
def test_load_missed_file(simple_storage: SimpleStorage):
    # test that in case of missed file, default values will be created
    simple_storage.data = None
    simple_storage.logger.info = Mock()
    assert not simple_storage.load()
    assert simple_storage
    simple_storage.logger.info.assert_has_calls([call('The storage file does not exist.')])


@patch('tribler_core.components.simple_storage.simple_storage.StorageData.parse_file',
       Mock(side_effect=JSONDecodeError))
def test_load_corrupted_file(simple_storage: SimpleStorage):
    # test that in case of corrupted file, default values will be created
    simple_storage.data = None
    simple_storage.logger.exception = Mock()
    assert not simple_storage.load()
    assert simple_storage
    simple_storage.logger.exception.assert_called_once()


def test_load(simple_storage: SimpleStorage):
    # test that in case of existed file, values will be loaded from file
    simple_storage.data.last_processed_torrent_id = 100
    simple_storage.save()

    simple_storage.data.last_processed_torrent_id = 1
    assert simple_storage.load()
    assert simple_storage.data.last_processed_torrent_id == 100


def test_shutdown(simple_storage: SimpleStorage):
    # test that on shutdown values have been saved and task has been cancelled
    simple_storage.data.last_processed_torrent_id = 100
    simple_storage.shutdown()

    assert simple_storage.path.exists()
    assert simple_storage._task.cancelled()


@pytest.mark.asyncio
async def test_save_and_schedule_next(tmp_path):
    # In this test we will set up save_interval as 0.1 sec, then wait for 1 sec
    # and count how many times function `save` will be called.
    storage = SimpleStorage(path=tmp_path / 'storage.json', save_interval=0.1)
    storage.save = Mock()
    await asyncio.sleep(1)
    assert 8 <= storage.save.call_count <= 10
