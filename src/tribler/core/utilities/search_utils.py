"""
Search utilities.

Author(s): Jelle Roozenburg, Arno Bakker, Alexander Kozlovsky
"""
import re
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

RE_KEYWORD_SPLIT = re.compile(r"[\W_]", re.UNICODE)
DIALOG_STOPWORDS = {'an', 'and', 'by', 'for', 'from', 'of', 'the', 'to', 'with'}

SECONDS_IN_DAY = 60 * 60 * 24


def split_into_keywords(string, to_filter_stopwords=False):
    """
    Takes a (unicode) string and returns a list of (unicode) lowercase
    strings.  No empty strings are returned.

    We currently split on non-alphanumeric characters and the
    underscore.

    If to_filter_stopwords is True a small stopword filter is using to reduce the number of keywords
    """
    if to_filter_stopwords:
        return [kw for kw in RE_KEYWORD_SPLIT.split(string.lower()) if len(kw) > 0 and kw not in DIALOG_STOPWORDS]
    else:
        return [kw for kw in RE_KEYWORD_SPLIT.split(string.lower()) if len(kw) > 0]


def filter_keywords(keywords):
    return [kw for kw in keywords if len(kw) > 0 and kw not in DIALOG_STOPWORDS]


def item_rank(query: str, item: dict) -> float:
    """
    Calculates the torrent rank for item received from remote query. Returns the torrent rank value in range [0, 1].

    :param query: a user-defined query string
    :param item: a dict with torrent info.
                 Should include key `name`, can include `num_seeders`, `num_leechers`, `created`
    :return: the torrent rank value in range [0, 1]
    """

    title = item['name']
    seeders = item.get('num_seeders', 0)
    leechers = item.get('num_leechers', 0)
    created = item.get('created', 0)
    freshness = None if created <= 0 else time.time() - created
    return torrent_rank(query, title, seeders, leechers, freshness)


def torrent_rank(query: str, title: str, seeders: int = 0, leechers: int = 0,
                 freshness: Optional[float] = None) -> float:
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

    Takes into account:
      - similarity of the title to the query string;
      - the reported number of seeders;
      - how long ago the torrent file was created.
    """
    tr = title_rank(query or '', title or '')
    sr = (seeders_rank(seeders or 0, leechers or 0) + 9) / 10  # range [0.9, 1]
    fr = (freshness_rank(freshness) + 9) / 10  # range [0.9, 1]
    result = tr * sr * fr

    # uncomment the next line to debug the function inside an SQL query:
    # print(f'*** {result} : {seeders}/{freshness} ({freshness / SECONDS_IN_DAY} days)/{title} | {query}')

    return result


LEECHERS_COEFF = 0.1  # How much leechers are less important compared to seeders (ten times less important)
SEEDERS_HALF_RANK = 100  # The number of seeders at which the seeders rank is 0.5


def seeders_rank(seeders: int, leechers: int = 0) -> float:
    """
    Calculates rank based on the number of torrent's seeders and leechers

    :param seeders: the number of seeders for the torrent. It is a positive value, usually in the range [0, 1000]
    :param leechers: the number of leechers for the torrent. It is a positive value, usually in the range [0, 1000]
    :return: the torrent rank based on seeders and leechers, normalized to the range [0, 1]
    """

    # The leechers are treated as less capable seeders
    sl = seeders + leechers * LEECHERS_COEFF  # Seeders and leechers combined

    # The function result has desired properties:
    #   *  zero rank for zero seeders;
    #   *  0.5 rating for SEEDERS_HALF_RANK seeders;
    #   *  1.0 rating for an infinite number of seeders;
    #   *  soft curve.
    # It is possible to use different curves with the similar shape, for example:
    #   *  2 * arctan(x / SEEDERS_HALF_RANK) / PI,
    #   *  1 - exp(x * ln(0.5) / SEEDERS_HALF_RANK)
    # but it does not actually matter in practice
    return sl / (100 + sl)


def freshness_rank(freshness: Optional[float]) -> float:
    """
    Calculates a rank value based on the torrent freshness. The result is normalized to the range [0, 1]

    :param freshness: number of seconds since the torrent creation.
                      None means the actual torrent creation date is unknown.
                      Negative values treated as invalid values and give the same result as None
    :return: the torrent rank based on freshness. The result is normalized to the range [0, 1]

    Example results:
    0 seconds since torrent creation -> the actual torrent creation date is unknown, freshness rank 0
    1 second since torrent creation -> freshness rank 0.999
    1 day since torrent creation -> freshness rank 0.967
    30 days since torrent creation -> freshness rank 0.5
    1 year since torrent creation -> freshness rank 0.0759
    """
    if freshness is None or freshness < 0:
        # for freshness <= 0 the rank value is 0 because of an incorrect freshness value
        return 0

    # The function declines from 1.0 to 0.0 on range (0..Infinity], with the following properties:
    #   *  for just created torrents the rank value is close to 1.0
    #   *  for 30-days old torrents the rank value is 0.5
    #   *  for very old torrens the rank value is going to zero
    # It was possible to use another formulas with the same properties (for example, exponent-based),
    # the exact curve shape is not really important.
    days = (freshness or 0) / SECONDS_IN_DAY
    return 1 / (1 + days / 30)


word_re = re.compile(r'\w+', re.UNICODE)


def title_rank(query: str, title: str) -> float:
    """
    Calculate the similarity of the title string to a query string as a float value in range [0, 1]

    :param query: a user-defined query string
    :param title: a torrent name
    :return: the similarity of the title string to a query string as a float value in range [0, 1]
    """
    query = word_re.findall(query.lower())
    title = word_re.findall(title.lower())
    return calculate_rank(query, title)


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


def calculate_rank(query: List[str], title: List[str]) -> float:
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

    title = deque(title)
    total_error = 0
    for i, word in enumerate(query):
        # The first word is more important than the second word, and so on
        word_weight = POSITION_COEFF / (POSITION_COEFF + i)

        # Read the description of the `find_word_and_rotate_title` function to understand what is going on.
        # Basically, we are trying to find each query word in the title words, calculate the penalty if the query word
        # is not found or if there are some title words before it, and then rotate the skipped title words to the end
        # of the title. This way, the least penalty got a title that has query words in the proper order at the
        # beginning of the title.
        found, skipped = find_word_and_rotate_title(word, title)
        if found:
            # if the query word is found in the title, add penalty for skipped words in title before it
            total_error += skipped * word_weight
        else:
            # if the query word is not found in the title, add a big penalty for it
            total_error += MISSED_WORD_PENALTY * word_weight

    # a small penalty for excess words in the title that was not mentioned in the search phrase
    remainder_weight = 1 / (REMAINDER_COEFF + len(query))
    remained_words_error = len(title) * remainder_weight
    total_error += remained_words_error

    # a search rank should be between 1 and 0
    return RANK_NORMALIZATION_COEFF / (RANK_NORMALIZATION_COEFF + total_error)


def find_word_and_rotate_title(word: str, title: Deque[str]) -> Tuple[bool, int]:
    """
    Finds the query word in the title. Returns whether it was found or not and the number of skipped words in the title.

    :param word: a word from the user-defined query string
    :param title: a deque of words in the title
    :return: a two-elements tuple, whether the word was found in the title and the number of skipped words

    This is a helper function to efficiently answer a question of how close a query string and a title string are,
    taking into account the ordering of words in both strings.

    For efficiency reasons, the function modifies the `title` deque in place by removing the first entrance
    of the found word and rotating all leading non-matching words to the end of the deque. It allows to efficiently
    perform multiple calls of the `find_word_and_rotate_title` function for subsequent words from the same query string.

    An example: find_word_and_rotate_title('A', deque(['X', 'Y', 'A', 'B', 'C'])) returns `(True, 2)`, where True means
    that the word 'A' was found in the `title` deque, and 2 is the number of skipped words ('X', 'Y'). Also, it modifies
    the `title` deque, so it starts looking like deque(['B', 'C', 'X', 'Y']). The found word 'A' was removed, and
    the leading non-matching words ('X', 'Y') were moved to the end of the deque.
    """
    try:
        skipped = title.index(word)  # find the query word placement in the title and the number of preceding words
    except ValueError:
        return False, 0

    title.rotate(-skipped)  # rotate skipped words to the end
    title.popleft()  # remove found word
    return True, skipped
