from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tribler.core import notifications
from tribler.core.components.tag.db.tag_db import Predicate
from tribler.core.components.tag.rules.tag_rules_processor import LAST_PROCESSED_TORRENT_ID, TagRulesProcessor

TEST_BATCH_SIZE = 100
TEST_INTERVAL = 0.1


# pylint: disable=redefined-outer-name, protected-access
@pytest.fixture
async def tag_rules_processor():
    processor = TagRulesProcessor(notifier=MagicMock(), db=MagicMock(), mds=MagicMock(), batch_size=TEST_BATCH_SIZE,
                                  interval=TEST_INTERVAL)
    yield processor
    await processor.shutdown()


def test_constructor(tag_rules_processor: TagRulesProcessor):
    # test that constructor of TagRulesProcessor works as expected
    assert tag_rules_processor.batch_size == TEST_BATCH_SIZE
    assert tag_rules_processor.interval == TEST_INTERVAL

    m: MagicMock = tag_rules_processor.notifier.add_observer
    m.assert_called_with(notifications.new_torrent_metadata_created, tag_rules_processor.process_torrent_title,
                         synchronous=True)


@patch.object(TagRulesProcessor, 'save_statements')
def test_process_torrent_file(mocked_save_tags: MagicMock, tag_rules_processor: TagRulesProcessor):
    # test on None
    assert not tag_rules_processor.process_torrent_title(infohash=None, title='title')
    assert not tag_rules_processor.process_torrent_title(infohash=b'infohash', title=None)

    # test that process_torrent_title doesn't find any tags in the title
    assert not tag_rules_processor.process_torrent_title(infohash=b'infohash', title='title')
    mocked_save_tags.assert_not_called()

    # test that process_torrent_title does find tags in the title
    assert tag_rules_processor.process_torrent_title(infohash=b'infohash', title='title [tag]') == 1
    mocked_save_tags.assert_called_with({'infohash'}, {'tag'}, relation=Predicate.HAS_TAG)


def test_save_tags(tag_rules_processor: TagRulesProcessor):
    # test that tag_rules_processor calls TagDatabase with correct args
    expected_calls = [{'obj': 'tag2', 'predicate': Predicate.HAS_TAG, 'subject': 'infohash'},
                      {'obj': 'tag1', 'predicate': Predicate.HAS_TAG, 'subject': 'infohash'}]
    tag_rules_processor.save_statements(subjects={'infohash'}, predicate=Predicate.HAS_TAG, objects={'tag1', 'tag2'})
    actual_calls = [c.kwargs for c in tag_rules_processor.db.add_auto_generated.mock_calls]

    # compare two lists of dict
    assert [c for c in actual_calls if c not in expected_calls] == []


@patch.object(TagRulesProcessor, 'process_torrent_title', new=MagicMock(return_value=1))
def test_process_batch_within_the_boundary(tag_rules_processor: TagRulesProcessor):
    # test inner logic of `process_batch` in case this batch located within the boundary
    returned_batch_size = TEST_BATCH_SIZE // 2  # let's return a half of requested items

    def select(_):
        return [SimpleNamespace(infohash=i, title=i) for i in range(returned_batch_size)]

    tag_rules_processor.mds.TorrentMetadata.select = select
    tag_rules_processor.mds.get_value = lambda *_, **__: 0  # let's start from 0 for LAST_PROCESSED_TORRENT_ID

    # let's specify `max_rowid` in such a way that it is far more than end of the current batch
    tag_rules_processor.mds.get_max_rowid = lambda: TEST_BATCH_SIZE * 10

    # assert that actually returned count of processed items is equal to `returned_batch_size`
    assert tag_rules_processor.process_batch() == returned_batch_size

    # assert that actually stored last_processed_torrent_id is equal to `TEST_BATCH_SIZE`
    tag_rules_processor.mds.set_value.assert_called_with(LAST_PROCESSED_TORRENT_ID, str(TEST_BATCH_SIZE))


@patch.object(TagRulesProcessor, 'process_torrent_title', new=MagicMock(return_value=1))
def test_process_batch_beyond_the_boundary(tag_rules_processor: TagRulesProcessor):
    # test inner logic of `process_batch` in case this batch located on a border
    returned_batch_size = TEST_BATCH_SIZE // 2  # let's return a half of requested items

    # let's specify `max_rowid` in such a way that it is less than end of the current batch
    max_rowid = returned_batch_size // 2

    def select(_):
        return [SimpleNamespace(infohash=i, title=i) for i in range(returned_batch_size)]

    tag_rules_processor.mds.get_value = lambda *_, **__: 0  # let's start from 0 for LAST_PROCESSED_TORRENT_ID
    tag_rules_processor.mds.TorrentMetadata.select = select

    tag_rules_processor.mds.get_max_rowid = lambda: max_rowid

    # assert that actually returned count of processed items is equal to `max_rowid`
    assert tag_rules_processor.process_batch() == returned_batch_size
    tag_rules_processor.mds.set_value.assert_called_with(LAST_PROCESSED_TORRENT_ID, str(max_rowid))
