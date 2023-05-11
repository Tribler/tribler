import time
from collections import deque

import pytest

from tribler.core.utilities.search_utils import filter_keywords, find_word_and_rotate_title, freshness_rank, \
    item_rank, seeders_rank, split_into_keywords, title_rank, torrent_rank

DAY = 60 * 60 * 24


def test_split_into_keywords():
    result = split_into_keywords("to be or not to be")
    assert isinstance(result, list)
    assert len(result) == 6

    result = split_into_keywords("to be or not to be", True)
    assert isinstance(result, list)
    assert len(result) == 4


def test_filter_keywords():
    result = filter_keywords(["to", "be", "or", "not", "to", "be"])
    assert isinstance(result, list)
    assert len(result) == 4


def test_title_rank_range():
    assert title_rank('Big Buck Bunny', 'Big Buck Bunny') == 1

    long_query = ' '.join(['foo'] * 1000)
    long_title = ' '.join(['bar'] * 1000)
    assert title_rank(long_query, long_title) == pytest.approx(0.03554968)


def test_freshness_rank_range():
    assert freshness_rank(-1) == freshness_rank(None) == 0  # Invalid or unknown freshness has the lowest rank
    assert freshness_rank(0) == 1  # Maximum freshness has the highest rank
    assert freshness_rank(0.001) == pytest.approx(1.0)  # Very fresh torrent
    assert freshness_rank(1000000000) == pytest.approx(0.0025852989)  # Very old torrent


def test_seeders_rank_range():
    assert seeders_rank(0) == 0
    assert seeders_rank(1000000) == pytest.approx(0.9999)


def test_torrent_rank_range():
    assert torrent_rank('Big Buck Bunny', 'Big Buck Bunny', seeders=1000000, freshness=0.01) == pytest.approx(0.99999)

    long_query = ' '.join(['foo'] * 1000)
    long_title = ' '.join(['bar'] * 1000)
    assert torrent_rank(long_query, long_title, freshness=1000000 * 365 * DAY) == pytest.approx(+0.02879524)


def test_torrent_rank():
    query = 'Big Buck Bunny'
    # The exact match ranked as pretty high
    title_match = torrent_rank(query, 'Big Buck Bunny')  # 0.81
    assert title_match > 0.8

    # Seeders are good for the rank
    # The more seeders the better
    # The fewer days have passed since the creation of the torrent, the higher its rank
    assert torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=1 * DAY) > \
           torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=100 * DAY) > \
           torrent_rank(query, 'Big Buck Bunny', seeders=100, freshness=100 * DAY) > \
           title_match

    # If a title contains non-matching words missed in the query string it is not as good as the exact match
    # The closer to the start of the string non-matching words are placed in the title, the worse is rank
    assert title_match > \
           torrent_rank(query, 'Big Buck Bunny II') > \
           torrent_rank(query, 'Big Buck Brown Bunny') > \
           torrent_rank(query, 'Big Bad Buck Bunny') > \
           torrent_rank(query, 'Boring Big Buck Bunny')

    # The more non-matching words are in the title, the worse is rank
    assert title_match > \
           torrent_rank(query, 'Big Buck A Bunny') > \
           torrent_rank(query, 'Big Buck A B Bunny') > \
           torrent_rank(query, 'Big Buck A B C Bunny')

    # Non-matching words close to the beginning of the title give a bigger penalty
    assert title_match > \
           torrent_rank(query, 'Big A Buck Bunny') > \
           torrent_rank(query, 'Big A B Buck Bunny') > \
           torrent_rank(query, 'Big A B C Buck Bunny')

    assert title_match > \
           torrent_rank(query, 'A Big Buck Bunny') > \
           torrent_rank(query, 'A B Big Buck Bunny') > \
           torrent_rank(query, 'A B C Big Buck Bunny')

    assert torrent_rank(query, 'Big A Buck Bunny') > \
           torrent_rank(query, 'A Big Buck Bunny')

    assert torrent_rank(query, 'Big A B Buck Bunny') > \
           torrent_rank(query, 'A B Big Buck Bunny')

    assert torrent_rank(query, 'Big A B C Buck Bunny') > \
           torrent_rank(query, 'A B C Big Buck Bunny')

    # Wrong order of words in the title imposes a penalty to the rank
    assert title_match > \
           torrent_rank(query, 'Big Bunny Buck')

    # Missed query words imposes a really big penalty
    assert torrent_rank(query, 'Big Buck') < 0.5

    # The close the missed words to the beginning of the query, the worse
    assert torrent_rank(query, 'Big Buck') > \
           torrent_rank(query, 'Big Bunny') > \
           torrent_rank(query, 'Buck Bunny')

    # The more seeders is still better
    assert torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=5 * DAY) > \
           torrent_rank(query, 'Buck Bunny', seeders=100, freshness=5 * DAY) > \
           torrent_rank(query, 'Buck Bunny', seeders=10, freshness=5 * DAY) > \
           torrent_rank(query, 'Buck Bunny')

    # The more days from the check the less relevant the number of seeders is
    assert torrent_rank(query, 'Buck Bunny', freshness=5 * DAY) > \
           torrent_rank(query, 'Buck Bunny', freshness=10 * DAY) > \
           torrent_rank(query, 'Buck Bunny', freshness=20 * DAY)

    # The exact match has a good rank
    assert torrent_rank('Sintel', 'Sintel') > 0.8

    # Non-matching words at the end of the title give slightly worse results
    # Non-matching words at the beginning of the title are much worse
    # Too many non-matching words give a bigger penalty
    assert torrent_rank('Sintel', 'Sintel') > \
           torrent_rank('Sintel', 'Sintel Part II') > \
           torrent_rank('Sintel', 'Part of Sintel') > \
           torrent_rank('Sintel', 'the.script.from.the.movie.Sintel.pdf')

    # Some more examples
    assert torrent_rank("Internet's Own Boy", "Internet's Own Boy") > \
           torrent_rank("Internet's Own Boy", "Internet's very Own Boy") > \
           torrent_rank("Internet's Own Boy", "Internet's very special Boy person")


def test_title_rank():
    # tests for better covarage of corner cases
    assert title_rank("", "title") == pytest.approx(1.0)
    assert title_rank("query", "") == pytest.approx(0.0)


def test_item_rank():
    item = dict(name="abc", num_seeders=10, num_leechers=20, created=time.time() - 10 * DAY)
    assert item_rank("abc", item) == pytest.approx(0.88794642)  # Torrent created ten days ago

    item = dict(name="abc", num_seeders=10, num_leechers=20, created=0)
    assert item_rank("abc", item) == pytest.approx(0.81964285)  # Torrent creation date is unknown

    item = dict(name="abc", num_seeders=10, num_leechers=20)
    assert item_rank("abc", item) == pytest.approx(0.81964285)  # Torrent creation date is unknown


def test_find_word():
    # To use the find_word_and_rotate_title function, you can call it one time for each word from the query and see:
    # - how many query words are missed in the title;
    # - how many excess or out-of-place title words are found before each query word;
    # - and how many title words are not mentioned in the query.

    # Example 1, query "A B C", title "A B C"
    title = deque(["A", "B", "C"])
    assert find_word_and_rotate_title("A", title) == (True, 0) and title == deque(["B", "C"])
    assert find_word_and_rotate_title("B", title) == (True, 0) and title == deque(["C"])
    assert find_word_and_rotate_title("C", title) == (True, 0) and title == deque([])
    # Conclusion: exact match.

    # Example 2, query "A B C", title "A B C D"
    title = deque(["A", "B", "C", "D"])
    assert find_word_and_rotate_title("A", title) == (True, 0) and title == deque(["B", "C", "D"])
    assert find_word_and_rotate_title("B", title) == (True, 0) and title == deque(["C", "D"])
    assert find_word_and_rotate_title("C", title) == (True, 0) and title == deque(["D"])
    # Conclusion: minor penalty for one excess word in the title that is not in the query.

    # Example 3, query "A B C", title "X Y A B C"
    title = deque(["X", "Y", "A", "B", "C"])
    assert find_word_and_rotate_title("A", title) == (True, 2) and title == deque(["B", "C", "X", "Y"])
    assert find_word_and_rotate_title("B", title) == (True, 0) and title == deque(["C", "X", "Y"])
    assert find_word_and_rotate_title("C", title) == (True, 0) and title == deque(["X", "Y"])
    # Conclusion: major penalty for skipping two words at the beginning of the title plus a minor penalty for two
    # excess words in the title that are not in the query.

    # Example 4, query "A B C", title "A B X Y C"
    title = deque(["A", "B", "X", "Y", "C"])
    assert find_word_and_rotate_title("A", title) == (True, 0) and title == deque(["B", "X", "Y", "C"])
    assert find_word_and_rotate_title("B", title) == (True, 0) and title == deque(["X", "Y", "C"])
    assert find_word_and_rotate_title("C", title) == (True, 2) and title == deque(["X", "Y"])
    # Conclusion: average penalty for skipping two words in the middle of the title plus a minor penalty for two
    # excess words in the title that are not in the query.

    # Example 5, query "A B C", title "A C B"
    title = deque(["A", "C", "B"])
    assert find_word_and_rotate_title("A", title) == (True, 0) and title == deque(["C", "B"])
    assert find_word_and_rotate_title("B", title) == (True, 1) and title == deque(["C"])
    assert find_word_and_rotate_title("C", title) == (True, 0) and title == deque([])
    # Conclusion: average penalty for skipping one word in the middle of the title.

    # Example 6, query "A B C", title "A C X"
    title = deque(["A", "C", "X"])
    assert find_word_and_rotate_title("A", title) == (True, 0) and title == deque(["C", "X"])
    assert find_word_and_rotate_title("B", title) == (False, 0) and title == deque(["C", "X"])
    assert find_word_and_rotate_title("C", title) == (True, 0) and title == deque(["X"])
    # Conclusion: huge penalty for missing one query word plus a minor penalty for one excess title word.
