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
    assert torrent_rank(query, 'Big Buck Bunny') == pytest.approx(0.81)

    # Seeders are good for the rank
    assert torrent_rank(query, 'Big Buck Bunny', seeders=100, freshness=100 * DAY) == pytest.approx(0.876923)

    # The more seeders the better
    assert torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=100 * DAY) == pytest.approx(0.9146853)

    # The fewer days have passed since the creation of the torrent, the higher its rank
    assert torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=1 * DAY) == pytest.approx(0.9877126)

    # If a title contains non-matching words missed in the query string it is not as good as the exact match
    assert torrent_rank(query, 'Big Buck Bunny II') == pytest.approx(0.80381679)

    # The closer to the start of the string non-matching words are placed in the title, the worse is rank
    assert torrent_rank(query, 'Big Buck Brown Bunny') == pytest.approx(0.75061099)
    assert torrent_rank(query, 'Big Bad Buck Bunny') == pytest.approx(0.74242068)
    assert torrent_rank(query, 'Boring Big Buck Bunny') == pytest.approx(0.73125)

    # The more non-matching words are in the title, the worse is rank
    assert torrent_rank(query, 'Big Buck A Bunny') == pytest.approx(0.75061099)
    assert torrent_rank(query, 'Big Buck A B Bunny') == pytest.approx(0.699335863)
    assert torrent_rank(query, 'Big Buck A B C Bunny') == pytest.approx(0.6546181)

    # Non-matching words close to the beginning of the title give a bigger penalty
    assert torrent_rank(query, 'Big A Buck Bunny') == pytest.approx(0.742420681)
    assert torrent_rank(query, 'Big A B Buck Bunny') == pytest.approx(0.6852494577)
    assert torrent_rank(query, 'Big A B C Buck Bunny') == pytest.approx(0.636253776)

    assert torrent_rank(query, 'A Big Buck Bunny') == pytest.approx(0.73125)
    assert torrent_rank(query, 'A B Big Buck Bunny') == pytest.approx(0.66645569)
    assert torrent_rank(query, 'A B C Big Buck Bunny') == pytest.approx(0.6122093)

    # Wrong order of words in the title imposes a penalty to the rank
    assert torrent_rank(query, 'Big Bunny Buck') == pytest.approx(0.7476923)

    # Missed query words imposes a really big penalty
    assert torrent_rank(query, 'Big Buck') == pytest.approx(0.4725)

    # The close the missed words to the beginning of the query, the worse
    assert torrent_rank(query, 'Big Bunny') == pytest.approx(0.441818181)
    assert torrent_rank(query, 'Buck Bunny') == pytest.approx(0.405)

    # The more seeders is still better, the more days from the check the less relevant the number of seeders is
    assert torrent_rank(query, 'Buck Bunny', seeders=10, freshness=5 * DAY) == pytest.approx(0.44805194)
    assert torrent_rank(query, 'Buck Bunny', seeders=100, freshness=5 * DAY) == pytest.approx(0.46821428)
    assert torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=5 * DAY) == pytest.approx(0.4883766)
    assert torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=10 * DAY) == pytest.approx(0.48306818)
    assert torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=20 * DAY) == pytest.approx(0.47563636)

    # The exact match
    assert torrent_rank('Sintel', 'Sintel') == pytest.approx(0.81)
    # Non-matching words at the end of the title give slightly worse results
    assert torrent_rank('Sintel', 'Sintel Part II') == pytest.approx(0.79553571)
    # Non-matching words at the beginning of the title are much worse
    assert torrent_rank('Sintel', 'Part of Sintel') == pytest.approx(0.664925373)
    # Too many non-matching words give a bigger penalty
    assert torrent_rank('Sintel', 'the.script.from.the.movie.Sintel.pdf') == pytest.approx(0.52105263)

    # Some more examples
    assert torrent_rank("Internet's Own Boy", "Internet's Own Boy") == pytest.approx(0.81)
    assert torrent_rank("Internet's Own Boy", "Internet's very Own Boy") == pytest.approx(0.75099337)
    assert torrent_rank("Internet's Own Boy", "Internet's very special Boy person") == pytest.approx(0.4353166986)


def test_title_rank():
    # tests for better covarage of corner cases
    assert title_rank("", "title") == pytest.approx(1.0)
    assert title_rank("query", "") == pytest.approx(0.0)


def test_item_rank():
    item = dict(name="abc", num_seeders=10, num_leechers=20)
    assert item_rank("abc", item) == pytest.approx(0.81978445)
