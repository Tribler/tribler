from __future__ import annotations

import dataclasses
from unittest.mock import Mock

from ipv8.test.base import TestBase

from tribler.core.database.layers.knowledge import ResourceType
from tribler.core.database.serialization import REGULAR_TORRENT
from tribler.core.knowledge.rules.knowledge_rules_processor import (
    LAST_PROCESSED_TORRENT_ID,
    RULES_PROCESSOR_VERSION,
    KnowledgeRulesProcessor,
)
from tribler.core.notifier import Notifier


@dataclasses.dataclass
class MockTorrentMetadata:
    """
    Mocked TorrentMetadata.
    """

    infohash: bytes
    metadata_type: int
    rowid: int
    title: str = "foo"
    tag_processor_version: int = 0


class TestKnowledgeRulesProcessor(TestBase):
    """
    Tests for the KnowledgeRulesProcessor class.
    """

    def setUp(self) -> None:
        """
        Create a new KnowledgeRulesProcessor.
        """
        self.tag_rules_processor = KnowledgeRulesProcessor(Notifier(), Mock(), Mock(), 100, 0.1)

    async def tearDown(self) -> None:
        """
        Shut down the KnowledgeRulesProcessor.
        """
        await self.tag_rules_processor.shutdown()
        await super().tearDown()

    def test_save_tags(self) -> None:
        """
        Test if the tag_rules_processor calls TagDatabase with correct args.
        """
        expected_calls = [
            {'obj': 'tag2', 'predicate': ResourceType.TAG, 'subject': 'infohash', 'subject_type': ResourceType.TORRENT},
            {'obj': 'tag1', 'predicate': ResourceType.TAG, 'subject': 'infohash', 'subject_type': ResourceType.TORRENT}
        ]

        self.tag_rules_processor.save_statements(subject_type=ResourceType.TORRENT, subject='infohash',
                                                 predicate=ResourceType.TAG,
                                                 objects={'tag1', 'tag2'})

        actual_calls = [c.kwargs for c in self.tag_rules_processor.db.add_auto_generated_operation.mock_calls]
        self.assertEqual([], [c for c in actual_calls if c not in expected_calls])

    async def test_process_batch(self) -> None:
        """
        Test if batches are correctly processed.
        """
        mocked_last_processed = ["0"]
        tmd = [MockTorrentMetadata(infohash=bytes([i]) * 20, metadata_type=REGULAR_TORRENT, rowid=i) for i in range(51)]
        self.tag_rules_processor.mds.get_max_rowid = Mock(return_value=50)
        self.tag_rules_processor.mds.TorrentMetadata.select = lambda x: [t for t in tmd if x(t)]
        self.tag_rules_processor.db.get_misc = lambda _, default: mocked_last_processed[0]
        self.tag_rules_processor.db.set_misc = lambda _, x: mocked_last_processed.__setitem__(0, x)

        self.tag_rules_processor.set_last_processed_torrent_id(10)  # batch should start from 11
        self.tag_rules_processor.batch_size = 30  # and process 30 entities
        _ = self.tag_rules_processor.register_task("process_batch", self.tag_rules_processor.process_batch, delay=10.0)

        self.assertEqual(30, await self.tag_rules_processor.process_batch())
        self.assertEqual(40, self.tag_rules_processor.get_last_processed_torrent_id())
        self.assertTrue(self.tag_rules_processor.is_pending_task_active("process_batch"))
        self.assertEqual(10, await self.tag_rules_processor.process_batch())
        self.assertEqual(50, self.tag_rules_processor.get_last_processed_torrent_id())
        self.assertFalse(self.tag_rules_processor.is_pending_task_active("process_batch"))

    def test_start_current_version(self) -> None:
        """
        Test if processing starts from the last processed torrent id.
        """
        mocked_last_processed = {LAST_PROCESSED_TORRENT_ID: "100", RULES_PROCESSOR_VERSION: "5"}

        def get_misc(key: str, default: str | None = None) -> str:
            return mocked_last_processed.get(key, default)

        self.tag_rules_processor.db.get_misc = get_misc

        self.tag_rules_processor.start()

        self.assertEqual(self.tag_rules_processor.version, self.tag_rules_processor.get_rules_processor_version())
        self.assertEqual(100, self.tag_rules_processor.get_last_processed_torrent_id())

    def test_start_batch_processing(self) -> None:
        """
        Test if there are torrents in the database that the batch processing will be started.
        """
        self.tag_rules_processor.start()

        self.assertTrue(self.tag_rules_processor.is_pending_task_active("process_queue"))

    def test_add_to_queue(self) -> None:
        """
        Test if add_to_queue adds the title to the queue.
        """
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash', 'title')

        title = self.tag_rules_processor.queue.get_nowait()

        self.assertEqual(0, self.tag_rules_processor.queue.qsize())
        self.assertEqual(b'infohash', title.infohash)
        self.assertEqual("title", title.title)

    def test_add_empty_to_queue(self) -> None:
        """
        Test if add_to_queue does not add the empty title to the queue.
        """
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash', None)

        self.assertEqual(0, self.tag_rules_processor.queue.qsize())

    async def test_process_queue(self) -> None:
        """
        Test if process_queue processes the queue.
        """
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash', 'title')
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash2', 'title2')
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash3', 'title3')

        self.assertEqual(3, await self.tag_rules_processor.process_queue())
        self.assertEqual(0, await self.tag_rules_processor.process_queue())

    async def test_process_queue_out_of_limit(self) -> None:
        """
        Test if process_queue processes the queue by using batch size.
        """
        self.tag_rules_processor.queue_batch_size = 2
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash', 'title')
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash2', 'title2')
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash3', 'title3')

        self.assertEqual(2, await self.tag_rules_processor.process_queue())
        self.assertEqual(1, await self.tag_rules_processor.process_queue())

    async def test_put_entity_to_the_queue_out_of_limit(self) -> None:
        """
        Test if put_entity_to_the_queue does not add the title to the queue if the queue is full.
        """
        self.tag_rules_processor.queue.maxsize = 1
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash', 'title')
        self.tag_rules_processor.put_entity_to_the_queue(b'infohash2', 'title2')

        self.assertEqual(1, self.tag_rules_processor.queue.qsize())
