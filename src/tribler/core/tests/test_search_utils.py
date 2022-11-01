import pytest

from tribler.core.utilities.search_utils import filter_keywords, item_rank, split_into_keywords, torrent_rank, \
    title_rank


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
    item = dict(name="abc", num_seeders=10, num_leechers=20)
    assert item_rank("abc", item) == pytest.approx(0.81978445)
