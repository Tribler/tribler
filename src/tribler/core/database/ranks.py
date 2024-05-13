"""
Search utilities.

Author(s): Jelle Roozenburg, Arno Bakker, Alexander Kozlovsky
"""
from __future__ import annotations

import re
import time
from collections import deque

SECONDS_IN_DAY = 60 * 60 * 24


def item_rank(query: str, item: dict) -> float:
    """
    Calculates the torrent rank for item received from remote query. Returns the torrent rank value in range [0, 1].

    :param query: a user-defined query string
    :param item: a dict with torrent info.
                 Should include key `name`, can include `num_seeders`, `num_leechers`, `created`
    :return: the torrent rank value in range [0, 1]
    """
    title = item["name"]
    seeders = item.get("num_seeders", 0)
    leechers = item.get("num_leechers", 0)
    created = item.get("created", 0)
    freshness = None if created <= 0 else time.time() - created
    return torrent_rank(query, title, seeders, leechers, freshness)


def torrent_rank(query: str, title: str, seeders: int = 0, leechers: int = 0, freshness: float | None = None) -> float:
    """
    Calculates search rank for a torrent.

    :param query: a user-defined query string
    :param title: a torrent name
    :param seeders: the number of seeders
    :param leechers: the number of leechers
    :param freshness: the number of seconds since the torrent creation. Zero or negative value means the torrent
                      creation date is unknown. It is more convenient to use comparing to a timestamp, as it avoids
                      using the `time()` function call and simplifies testing.
    :return: the torrent rank value in range [0, 1]
    """
    tr = title_rank(query or '', title or '')
    sr = (seeders_rank(seeders or 0, leechers or 0) + 9) / 10  # range [0.9, 1]
    fr = (freshness_rank(freshness) + 9) / 10  # range [0.9, 1]
    return tr * sr * fr



def seeders_rank(seeders: int, leechers: int = 0) -> float:
    """
    Calculates rank based on the number of torrent's seeders and leechers.

    :param seeders: the number of seeders for the torrent.
    :param leechers: the number of leechers for the torrent.
    :return: the torrent rank based on seeders and leechers, normalized to the range [0, 1]
    """
    sl = seeders + leechers * 0.1
    return sl / (100 + sl)


def freshness_rank(freshness: float | None) -> float:
    """
    Calculates a rank value based on the torrent freshness. The result is normalized to the range [0, 1].

    :param freshness: number of seconds since the torrent creation.
                      None means the actual torrent creation date is unknown.
                      Negative values treated as invalid values and give the same result as None
    :return: the torrent rank based on freshness. The result is normalized to the range [0, 1]
    """
    if freshness is None or freshness < 0:
        return 0

    days = freshness / SECONDS_IN_DAY
    return 1 / (1 + days / 30)


word_re = re.compile(r'\w+', re.UNICODE)


def title_rank(query: str, title: str) -> float:
    """
    Calculate the similarity of the title string to a query string as a float value in range [0, 1].

    :param query: a user-defined query string
    :param title: a torrent name
    :return: the similarity of the title string to a query string as a float value in range [0, 1]
    """
    pat_query = word_re.findall(query.lower())
    pat_title = word_re.findall(title.lower())
    return calculate_rank(pat_query, pat_title)


# These coefficients are found empirically. Their exact values are not very important for a relative ranking of results

# The first word in a query is considered as a more important than the next one and so on,
# 5 means the 5th word in a query is twice as less important as the first one
POSITION_COEFF = 5

# Some big value for a penalty if a query word is totally missed from a torrent title
MISSED_WORD_PENALTY = 10

# If a torrent title contains some words at the very end that are not mentioned in a query, we add a very slight
# penalty for them. The *bigger* the REMAINDER_COEFF is, the *smaller* penalty we add for this excess words
REMAINDER_COEFF = 10

# The exact value of this coefficient is not important. It is used to convert total_error value to a rank value.
# The total_error value is some positive number. We want to have the resulted rank in range [0, 1].
RANK_NORMALIZATION_COEFF = 10


def calculate_rank(query: list[str], title: list[str]) -> float:
    """
    Calculates the similarity of the title to the query as a float value in range [0, 1].

    :param query: list of query words
    :param title: list of title words
    :return: the similarity of the title to the query as a float value in range [0, 1]
    """
    if not query:
        return 1.0

    if not title:
        return 0.0

    q_title = deque(title)
    total_error = 0.0
    for i, word in enumerate(query):
        # The first word is more important than the second word, and so on
        word_weight = POSITION_COEFF / (POSITION_COEFF + i)

        found, skipped = find_word_and_rotate_title(word, q_title)
        if found:
            # if the query word is found in the title, add penalty for skipped words in title before it
            total_error += skipped * word_weight
        else:
            # if the query word is not found in the title, add a big penalty for it
            total_error += MISSED_WORD_PENALTY * word_weight

    # a small penalty for excess words in the title that was not mentioned in the search phrase
    remainder_weight = 1 / (REMAINDER_COEFF + len(query))
    remained_words_error = len(q_title) * remainder_weight
    total_error += remained_words_error

    # a search rank should be between 1 and 0
    return RANK_NORMALIZATION_COEFF / (RANK_NORMALIZATION_COEFF + total_error)


def find_word_and_rotate_title(word: str, title: deque[str]) -> tuple[bool, int]:
    """
    Finds the query word in the title. Returns whether it was found or not and the number of skipped words in the title.

    This is a helper function to efficiently answer a question of how close a query string and a title string are,
    taking into account the ordering of words in both strings.

    For efficiency reasons, the function modifies the `title` deque in place by removing the first entrance
    of the found word and rotating all leading non-matching words to the end of the deque. It allows to efficiently
    perform multiple calls of the `find_word_and_rotate_title` function for subsequent words from the same query string.

    An example: find_word_and_rotate_title('A', deque(['X', 'Y', 'A', 'B', 'C'])) returns `(True, 2)`, where True means
    that the word 'A' was found in the `title` deque, and 2 is the number of skipped words ('X', 'Y'). Also, it modifies
    the `title` deque, so it starts looking like deque(['B', 'C', 'X', 'Y']). The found word 'A' was removed, and
    the leading non-matching words ('X', 'Y') were moved to the end of the deque.

    :param word: a word from the user-defined query string
    :param title: a deque of words in the title
    :return: a two-elements tuple, whether the word was found in the title and the number of skipped words
    """
    try:
        skipped = title.index(word)  # find the query word placement in the title and the number of preceding words
    except ValueError:
        return False, 0

    title.rotate(-skipped)  # rotate skipped words to the end
    title.popleft()  # remove found word
    return True, skipped
