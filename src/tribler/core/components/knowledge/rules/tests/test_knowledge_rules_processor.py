import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session

from tribler.core import notifications
from tribler.core.components.knowledge.db.knowledge_db import ResourceType
from tribler.core.components.knowledge.rules.knowledge_rules_processor import KnowledgeRulesProcessor
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import MEMORY_DB

TEST_BATCH_SIZE = 100
TEST_INTERVAL = 0.1


# pylint: disable=redefined-outer-name, protected-access
@pytest.fixture
async def tag_rules_processor(tmp_path: Path):
    mds = MetadataStore(db_filename=MEMORY_DB, channels_dir=tmp_path, my_key=LibNaCLSK())
    processor = KnowledgeRulesProcessor(notifier=MagicMock(), db=MagicMock(), mds=mds,
                                        batch_size=TEST_BATCH_SIZE,
                                        interval=TEST_INTERVAL)
    yield processor
    await processor.shutdown()


def test_constructor(tag_rules_processor: KnowledgeRulesProcessor):
    # test that constructor of TagRulesProcessor works as expected
    assert tag_rules_processor.batch_size == TEST_BATCH_SIZE
    assert tag_rules_processor.interval == TEST_INTERVAL

    m: MagicMock = tag_rules_processor.notifier.add_observer
    m.assert_called_with(notifications.new_torrent_metadata_created, tag_rules_processor.process_torrent_title,
                         synchronous=True)


@patch.object(KnowledgeRulesProcessor, 'save_statements')
def test_process_torrent_file(mocked_save_tags: MagicMock, tag_rules_processor: KnowledgeRulesProcessor):
    # test on None
    assert not tag_rules_processor.process_torrent_title(infohash=None, title='title')
    assert not tag_rules_processor.process_torrent_title(infohash=b'infohash', title=None)

    # test that process_torrent_title doesn't find any tags in the title
    assert not tag_rules_processor.process_torrent_title(infohash=b'infohash', title='title')
    mocked_save_tags.assert_not_called()

    # test that process_torrent_title does find tags in the title
    assert tag_rules_processor.process_torrent_title(infohash=b'infohash', title='title [tag]') == 1
    mocked_save_tags.assert_called_with(subject_type=ResourceType.TORRENT, subject='696e666f68617368', objects={'tag'},
                                        predicate=ResourceType.TAG)


def test_save_tags(tag_rules_processor: KnowledgeRulesProcessor):
    # test that tag_rules_processor calls TagDatabase with correct args
    expected_calls = [
        {'obj': 'tag2', 'predicate': ResourceType.TAG, 'subject': 'infohash', 'subject_type': ResourceType.TORRENT},
        {'obj': 'tag1', 'predicate': ResourceType.TAG, 'subject': 'infohash', 'subject_type': ResourceType.TORRENT}
    ]
    tag_rules_processor.save_statements(subject_type=ResourceType.TORRENT, subject='infohash',
                                        predicate=ResourceType.TAG,
                                        objects={'tag1', 'tag2'})
    actual_calls = [c.kwargs for c in tag_rules_processor.db.add_auto_generated.mock_calls]

    # compare two lists of dict
    assert [c for c in actual_calls if c not in expected_calls] == []


@db_session
@patch.object(KnowledgeRulesProcessor, 'process_torrent_title', new=MagicMock(return_value=1))
@patch.object(KnowledgeRulesProcessor, 'cancel_pending_task')
def test_process_batch(mocked_cancel_pending_task: Mock, tag_rules_processor: KnowledgeRulesProcessor):
    # test the correctness of the inner logic of process_batch.

    # fill the db with 50 torrents
    for _ in range(50):
        tag_rules_processor.mds.TorrentMetadata(infohash=os.urandom(20), metadata_type=REGULAR_TORRENT)

    tag_rules_processor.set_last_processed_torrent_id(10)  # batch should start from 11
    tag_rules_processor.batch_size = 30  # and process 30 entities

    # first iteration
    assert tag_rules_processor.process_batch() == 30
    assert tag_rules_processor.get_last_processed_torrent_id() == 40
    assert not mocked_cancel_pending_task.called  # it should not be the last batch in the db

    # second iteration
    assert tag_rules_processor.process_batch() == 10
    assert tag_rules_processor.get_last_processed_torrent_id() == 50
    assert mocked_cancel_pending_task.called  # it should  be the last batch in the db


@db_session
@patch.object(KnowledgeRulesProcessor, 'register_task', new=MagicMock())
def test_start_no_previous_version(tag_rules_processor: KnowledgeRulesProcessor):
    # test that if there is no previous version of the rules processor, it will be created
    assert tag_rules_processor.get_rules_processor_version() == 0
    assert tag_rules_processor.get_rules_processor_version() != tag_rules_processor.version

    tag_rules_processor.start()

    # version should be set to the current version
    assert tag_rules_processor.get_rules_processor_version() == tag_rules_processor.version
    # last processed torrent id should be set to 0
    assert tag_rules_processor.get_last_processed_torrent_id() == 0


@db_session
@patch.object(KnowledgeRulesProcessor, 'register_task', new=MagicMock())
def test_start_previous_version(tag_rules_processor: KnowledgeRulesProcessor):
    # test that if there is a previous version of the rules processor, it will be updated to the current
    tag_rules_processor.set_rules_processor_version(tag_rules_processor.version - 1)
    tag_rules_processor.set_last_processed_torrent_id(100)

    tag_rules_processor.start()

    # version should be set to the current version
    assert tag_rules_processor.get_rules_processor_version() == tag_rules_processor.version
    # last processed torrent id should be set to 0
    assert tag_rules_processor.get_last_processed_torrent_id() == 0


@db_session
@patch.object(KnowledgeRulesProcessor, 'register_task', new=MagicMock())
def test_start_current_version(tag_rules_processor: KnowledgeRulesProcessor):
    # test that if there is a current version of the rules processor, it will process the database from
    # the last processed torrent id
    tag_rules_processor.set_rules_processor_version(tag_rules_processor.version)
    tag_rules_processor.set_last_processed_torrent_id(100)

    tag_rules_processor.start()

    # version should be the same
    assert tag_rules_processor.get_rules_processor_version() == tag_rules_processor.version
    # last processed torrent id should be the same
    assert tag_rules_processor.get_last_processed_torrent_id() == 100


@db_session
@patch.object(KnowledgeRulesProcessor, 'register_task')
def test_start_batch_processing(mocked_register_task: Mock, tag_rules_processor: KnowledgeRulesProcessor):
    # test that if there are torrents in the database, the batch processing will be started
    tag_rules_processor.mds.TorrentMetadata(infohash=os.urandom(20), metadata_type=REGULAR_TORRENT)
    tag_rules_processor.start()

    assert mocked_register_task.called
