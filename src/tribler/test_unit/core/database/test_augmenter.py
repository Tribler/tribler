from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock

from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase

from tribler.core.database.augmenter import AugmentedSearch
from tribler.core.notifier import Notification, Notifier
from tribler.test_unit.mocks import MockTriblerConfigManager


class TestAugmentedSearch(TestBase):
    """
    Tests for augmenting queries.
    """

    def setUp(self) -> None:
        """
        Create a mock config and an AugmentedSearch setup.
        """
        self.config = MockTriblerConfigManager()
        self.config.set("state_dir", self.temporary_directory())
        self.notifier = Notifier()
        self.tm = TaskManager()
        self.augmenter = AugmentedSearch(self.config, self.notifier, self.tm)

    async def test_write_cache_on_shutdown(self) -> None:
        """
        Test if an incomplete title window is flushed to disk before shutting down.
        """
        for i in range(5):
            self.notifier.notify(Notification.torrent_metadata_added, metadata={"title": f"test {i}"})

        await self.tm.shutdown_task_manager()

        self.assertEqual(50, os.stat(str(
            Path(self.config.get("state_dir")) / "git" / "_m_torrent_titles.cache.txt")
        ).st_size)

    def test_title_trunc(self) -> None:
        """
        Test if long torrent titles are truncated.
        """
        self.notifier.notify(Notification.torrent_metadata_added, metadata={"title": "a" * 5000})

        self.assertEqual(self.augmenter.max_title_length, len(self.augmenter.title_window[0]))

    def test_schedule_study(self) -> None:
        """
        Test if a study is scheduled when we have sufficient training data.
        """
        self.augmenter.title_window = ["test"] * 50  # Max size, next will overflow

        self.notifier.notify(Notification.torrent_metadata_added, metadata={"title": "test"})

        self.assertEqual(1, len(self.tm.get_tasks()))
        self.tm.cancel_all_pending_tasks()  # Note that this test is not async, we have to do cleanup here.

    def test_schedule_study_from_cache(self) -> None:
        """
        Test if the cache file is checked after a restart for pending training data.
        """
        (Path(self.config.get("state_dir")) / "git" / "_m_torrent_titles.cache.txt").write_text(
            "[" + ",".join(['"test"'] * 50) + "]"  # JSON
        )

        self.notifier.notify(Notification.torrent_metadata_added, metadata={"title": "test"})

        self.assertEqual(1, len(self.tm.get_tasks()))
        self.tm.cancel_all_pending_tasks()  # Note that this test is not async, we have to do cleanup here.

    async def test_study(self) -> None:
        """
        Test if learning is actually taking place. Warning: id assignment and exact vocabulary are non-deterministic!
        """
        await self.augmenter.study(["test" + chr(i) for i in range(65, 96)])
        encoded = self.augmenter.processor.Encode("test")

        self.assertEqual(1, len(encoded))
        self.assertLessEqual(5, self.augmenter.processor.vocab_size())  # Should have [PAD, UNK, BOS, EOS, "test"]

    def test_needs_kickstart(self) -> None:
        """
        Test if an uninitialized augmenter asks for a kickstart.
        """
        self.assertTrue(self.augmenter.needs_kickstart())

    def test_needs_kickstart_initialized_empty(self) -> None:
        """
        Test if an initialized-but-empty augmenter asks for a kickstart.
        """
        self.augmenter.initialized = True

        self.assertTrue(self.augmenter.needs_kickstart())

    async def test_needs_kickstart_initialized(self) -> None:
        """
        Test if an initialized augmenter signals no need for a kickstart.
        """
        self.augmenter.initialized = True

        await self.augmenter.study(["test" + chr(i) for i in range(65, 96)])

        self.assertFalse(self.augmenter.needs_kickstart())

    def test_to_phrases(self) -> None:
        """
        Test if pieces are correctly mapped to phrases.
        """
        pieces = ["▁I", "▁lo", "v", "e", "▁Trib", "ler"]

        phrases = self.augmenter.to_phrases(pieces)

        self.assertEqual(3, len(phrases))
        self.assertListEqual(["I"], phrases[0])
        self.assertListEqual(["lo", "v", "e"], phrases[1])
        self.assertListEqual(["Trib", "ler"], phrases[2])

    def test_augment(self) -> None:
        """
        Test if a full e2e enhancement works. With a fixed vocabulary/model, this is deterministic!

        Explanation for the "test_augment is testing!" transformation:
         0. We load the vocabulary from test_study, which is trained on the unigram "test". However, note that "augm"
            and "ing!" have also snuck their way into the vocabulary.
         1. We parse three words (into as many phrases) "test_augment", "is", "testing!" and output their conjuction.
         2.a. The first disjunction permutates ["test", "_", "augm", "e", "n", "t"].
         2.b. The second is ["i", "s"]. Both symbols are completely unknown to our vocabulary.
         2.c. The third is ["test", "ing!"].
        """
        self.augmenter.processor.LoadFromFile(str(Path(__file__).parent / "augmenter.model"))

        sql, parameters = self.augmenter.augment("test_augment is testing!", 42, 1337)

        self.assertEqual(
            "SELECT rowid FROM ChannelNode WHERE"
            " (title LIKE ? OR title LIKE ? OR title LIKE ? OR title LIKE ? OR title LIKE ? OR title LIKE ?)"
            " AND (title LIKE ? OR title LIKE ?)"
            " AND (title LIKE ? OR title LIKE ?)"
            " LIMIT 42 OFFSET 1337", sql)
        self.assertListEqual([
            "%_augment%", "%test%augment%", "%test_%ent%", "%test_augm%nt%", "%test_augme%t%", "%test_augmen%",
            "%s%", "%i%",
            "%ing!%", "%test%"
        ], parameters)

    def test_schedule_study_double(self) -> None:
        """
        Scheduling a study should not cause two trainings to happen at once.
        """
        mock_register_task = Mock()
        self.augmenter.task_manager = Mock(register_task=mock_register_task, get_task=Mock(return_value=(
            mock_register_task.call_args[0] if mock_register_task.call_args else None
        )))
        self.augmenter.title_window = ["test"] * 51

        self.augmenter.schedule_study()
        self.augmenter.schedule_study()

        self.assertEqual(1, mock_register_task.call_count)
