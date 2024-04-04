from __future__ import annotations

from collections import deque

from ipv8.test.base import TestBase

from tribler.core.database.ranks import (
    find_word_and_rotate_title,
    freshness_rank,
    seeders_rank,
    title_rank,
    torrent_rank,
)


class TestRanks(TestBase):
    """
    Tests for the ranking logic.
    """

    def test_title_rank_exact_match(self) -> None:
        """
        Test if an exact title match leads to a score of exactly 1.
        """
        self.assertEqual(1, title_rank("Big Buck Bunny", "Big Buck Bunny"))

    def test_title_rank_no_match(self) -> None:
        """
        Test if input of different titles leads to a score less than 1.
        """
        self.assertLess(title_rank("Big Buck Bunny", "Aji Ayvl Aybbu"), 1)

    def test_freshness_rank_zero(self) -> None:
        """
        Test if invalid or unknown freshness has the lowest rank.
        """
        self.assertEqual(0, freshness_rank(-1))
        self.assertEqual(0, freshness_rank(None))

    def test_freshness_rank_max(self) -> None:
        """
        Test if maximum freshness has the highest rank.
        """
        self.assertEqual(1, freshness_rank(0))

    def test_freshness_rank_relative(self) -> None:
        """
        Test if fresh torrents have a higher score than old torrents.
        """
        self.assertLess(freshness_rank(10), freshness_rank(1))

    def test_seeders_rank_zero(self) -> None:
        """
        Test if a torrent without seeders scores a 0.
        """
        self.assertEqual(0, seeders_rank(0))

    def test_seeders_rank_many(self) -> None:
        """
        Test if a torrent with many seeders scores more than a 0.
        """
        self.assertGreater(seeders_rank(1000000), 0)

    def test_seeders_rank_relative(self) -> None:
        """
        Test if a torrent with more seeders scores higher.
        """
        self.assertGreaterEqual(seeders_rank(100), seeders_rank(10))

    def test_seeders_rank_leechers(self) -> None:
        """
        Test if a torrent with more leechers scores higher.
        """
        self.assertGreaterEqual(seeders_rank(10, 100), seeders_rank(10, 10))

    def test_torrent_rank_exact_match(self) -> None:
        """
        Test if an exact title match leads to a score of exactly 0.81.

        This is 90% (no seeders/leechers) of 90% (no freshness) of an exact match score of 1.
        """
        self.assertEqual(0.81, torrent_rank("Big Buck Bunny", "Big Buck Bunny"))

    def test_torrent_rank__no_freshness(self) -> None:
        """
        Test if no freshness is worse than any freshness.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny", seeders=1000, freshness=1)
        rank2 = torrent_rank("Big Buck Bunny", "Big Buck Bunny", seeders=1000, freshness=None)

        self.assertGreaterEqual(rank1, rank2)

    def test_torrent_rank_freshness(self) -> None:
        """
        Test if recent freshness is better than old freshness.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny", seeders=1000, freshness=1)
        rank2 = torrent_rank("Big Buck Bunny", "Big Buck Bunny", seeders=1000, freshness=100)

        self.assertGreaterEqual(rank1, rank2)

    def test_torrent_rank_position(self) -> None:
        """
        Test if word matches are preferred close to the start.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny")  # Exact
        rank2 = torrent_rank("Big Buck Bunny", "Big Buck Bunny II")
        rank3 = torrent_rank("Big Buck Bunny", "Big Buck Brown Bunny")
        rank4 = torrent_rank("Big Buck Bunny", "Big Bad Buck Bunny")
        rank5 = torrent_rank("Big Buck Bunny", "Boring Big Buck Bunny")

        self.assertGreaterEqual(rank1, rank2)
        self.assertGreaterEqual(rank2, rank3)
        self.assertGreaterEqual(rank3, rank4)
        self.assertGreaterEqual(rank4, rank5)

    def test_torrent_rank_intermediate(self) -> None:
        """
        Test if word matches are preferred with less words in between.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny")  # Exact
        rank2 = torrent_rank("Big Buck Bunny", "Big Buck A Bunny")
        rank3 = torrent_rank("Big Buck Bunny", "Big Buck A B Bunny")
        rank4 = torrent_rank("Big Buck Bunny", "Big Buck A B C Bunny")

        self.assertGreaterEqual(rank1, rank2)
        self.assertGreaterEqual(rank2, rank3)
        self.assertGreaterEqual(rank3, rank4)

    def test_torrent_rank_mis_position_one(self) -> None:
        """
        Test if word matches are preferred with mismatches further on in the item.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big A Buck Bunny")
        rank2 = torrent_rank("Big Buck Bunny", "A Big Buck Bunny")

        self.assertGreaterEqual(rank1, rank2)

    def test_torrent_rank_mis_position_many(self) -> None:
        """
        Test if word group matches are preferred with mismatches further on in the item.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big A B C Buck Bunny")
        rank2 = torrent_rank("Big Buck Bunny", "A B C Big Buck Bunny")

        self.assertGreaterEqual(rank1, rank2)

    def test_torrent_rank_reorder(self) -> None:
        """
        Test if wrong order of words in the title imposes a penalty to the rank.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny")  # Exact
        rank2 = torrent_rank("Big Buck Bunny", "Big Bunny Buck")

        self.assertGreaterEqual(rank1, rank2)

    def test_torrent_rank_miss(self) -> None:
        """
        Test if missed words in the title imposes a penalty to the rank.
        """
        rank1 = torrent_rank("Big Buck Bunny", "Big Buck Bunny")  # Exact
        rank2 = torrent_rank("Big Buck Bunny", "Big Buck")
        rank3 = torrent_rank("Big Buck Bunny", "Big Bunny")
        rank4 = torrent_rank("Big Buck Bunny", "Buck Bunny")

        self.assertGreaterEqual(rank1, rank2)
        self.assertGreaterEqual(rank2, rank3)
        self.assertGreaterEqual(rank3, rank4)

    def test_find_word_first(self) -> None:
        """
        Test if a matched first word gets popped from the queue.
        """
        title = deque(["A", "B", "C"])

        self.assertEqual((True, 0), find_word_and_rotate_title("A", title))
        self.assertEqual(deque(["B", "C"]), title)

    def test_find_word_skip_one(self) -> None:
        """
        Test if the number of skipped words is returned correctly when skipping over one.
        """
        title = deque(["A", "B", "C"])

        self.assertEqual((True, 1), find_word_and_rotate_title("B", title))
        self.assertEqual(deque(["C", "A"]), title)

    def test_find_word_skip_many(self) -> None:
        """
        Test if the number of skipped words is returned correctly when skipping over many.
        """
        title = deque(["A", "B", "X", "Y", "C"])

        self.assertEqual((True, 4), find_word_and_rotate_title("C", title))
        self.assertEqual(deque(["A", "B", "X", "Y"]), title)

    def test_find_word_not_found(self) -> None:
        """
        Test if the False is returned when a word is not found.
        """
        title = deque(["A", "C", "X"])

        self.assertEqual((False, 0), find_word_and_rotate_title("B", title))
        self.assertEqual(deque(["A", "C", "X"]), title)
