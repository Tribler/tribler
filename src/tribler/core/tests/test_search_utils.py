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

    r1 = torrent_rank(query, 'Big Buck Bunny')  # 0.81
    assert r1 > 0.8

    # Seeders are good for the rank

    r2 = torrent_rank(query, 'Big Buck Bunny', seeders=100, freshness=100 * DAY)  # 0.876923

    # The more seeders the better

    r3 = torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=100 * DAY)  # 0.9146853

    # The fewer days have passed since the creation of the torrent, the higher its rank

    r4 = torrent_rank(query, 'Big Buck Bunny', seeders=1000, freshness=1 * DAY)  # 0.9877126

    assert r1 < r2 < r3 < r4

    # If a title contains non-matching words missed in the query string it is not as good as the exact match

    r5 = torrent_rank(query, 'Big Buck Bunny II')  # 0.80381679

    # The closer to the start of the string non-matching words are placed in the title, the worse is rank

    r6 = torrent_rank(query, 'Big Buck Brown Bunny')  # 0.75061099
    r7 = torrent_rank(query, 'Big Bad Buck Bunny')  # 0.74242068
    r8 = torrent_rank(query, 'Boring Big Buck Bunny')  # 0.73125

    assert r8 < r7 < r6 < r5 < r1

    # The more non-matching words are in the title, the worse is rank

    r9 = torrent_rank(query, 'Big Buck A Bunny')  # 0.75061099
    r10 = torrent_rank(query, 'Big Buck A B Bunny')  # 0.699335863
    r11 = torrent_rank(query, 'Big Buck A B C Bunny')  # 0.6546181

    assert r11 < r10 < r9 < r1

    # Non-matching words close to the beginning of the title give a bigger penalty

    r12 = torrent_rank(query, 'Big A Buck Bunny')  # 0.742420681
    r13 = torrent_rank(query, 'Big A B Buck Bunny')  # 0.6852494577
    r14 = torrent_rank(query, 'Big A B C Buck Bunny')  # 0.636253776

    assert r14 < r13 < r12 < r1

    r15 = torrent_rank(query, 'A Big Buck Bunny')  # 0.73125
    r16 = torrent_rank(query, 'A B Big Buck Bunny')  # 0.66645569
    r17 = torrent_rank(query, 'A B C Big Buck Bunny')  # 0.6122093

    assert r17 < r16 < r15 < r1
    assert r15 < r12 and r16 < r13 and r17 < r14

    # Wrong order of words in the title imposes a penalty to the rank

    r18 = torrent_rank(query, 'Big Bunny Buck')  # 0.7476923

    assert r18 < r1

    # Missed query words imposes a really big penalty

    r19 = torrent_rank(query, 'Big Buck')  # 0.4725

    assert r19 < 0.5

    # The close the missed words to the beginning of the query, the worse

    r20 = torrent_rank(query, 'Big Bunny')  # 0.441818181
    r21 = torrent_rank(query, 'Buck Bunny')  # 0.405

    assert r21 < r20 < r19

    # The more seeders is still better

    r22 = torrent_rank(query, 'Buck Bunny', seeders=10, freshness=5 * DAY)  # 0.44805194
    r23 = torrent_rank(query, 'Buck Bunny', seeders=100, freshness=5 * DAY)  # 0.46821428
    r24 = torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=5 * DAY)  # 0.4883766

    assert r21 < r22 < r23 < r24

    # The more days from the check the less relevant the number of seeders is

    r25 = torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=10 * DAY)  # 0.48306818
    r26 = torrent_rank(query, 'Buck Bunny', seeders=1000, freshness=20 * DAY)  # 0.47563636

    assert r26 < r25 < r24

    # The exact match has a good rank
    r27 = torrent_rank('Sintel', 'Sintel')  # 0.81
    assert r27 > 0.8

    # Non-matching words at the end of the title give slightly worse results
    r28 = torrent_rank('Sintel', 'Sintel Part II')  # 0.79553571

    # Non-matching words at the beginning of the title are much worse
    r29 = torrent_rank('Sintel', 'Part of Sintel')  # 0.664925373

    # Too many non-matching words give a bigger penalty
    r30 = torrent_rank('Sintel', 'the.script.from.the.movie.Sintel.pdf')  # 0.52105263

    assert r30 < r29 < r28 < r27

    # Some more examples

    r31 = torrent_rank("Internet's Own Boy", "Internet's Own Boy")  # 0.81
    r32 = torrent_rank("Internet's Own Boy", "Internet's very Own Boy")  # 0.75099337
    r33 = torrent_rank("Internet's Own Boy", "Internet's very special Boy person")  # 0.4353166986

    assert r33 < r32 < r31


def test_title_rank():
    # tests for better covarage of corner cases
    assert title_rank("", "title") == pytest.approx(1.0)
    assert title_rank("query", "") == pytest.approx(0.0)


def test_item_rank():
    item = dict(name="abc", num_seeders=10, num_leechers=20)
    assert item_rank("abc", item) == pytest.approx(0.81978445)
