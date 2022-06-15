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


def item_rank(query: str, item: dict):
    title = item['name']
    seeders = item.get('num_seeders', 0)
    leechers = item.get('num_leechers', 0)
    freshness = time.time() - item.get('updated', 0)
    return torrent_rank(query, title, seeders + leechers * 0.1, freshness)


def torrent_rank(query: str, title: str, seeders: int = 0, freshness: Optional[float] = 0) -> float:
    """
    Calculates search rank for a torrent.
    Takes into account:
      - similarity of the title to the query string;
      - the reported number of seeders;
      - how long ago the torrent file was created.
    """
    freshness = max(0, freshness or 0)
    tr = title_rank(query or '', title or '')
    sr = (seeders_rank(seeders or 0) + 9) / 10  # range [0.9, 1]
    fr = (freshness_rank(freshness) + 9) / 10  # range [0.9, 1]
    result = tr * sr * fr
    # uncomment the next line to debug the function inside an SQL query:
    # print(f'*** {result} : {seeders}/{freshness} ({freshness / SECONDS_IN_DAY} days)/{title} | {query}')
    return result


def seeders_rank(seeders: float) -> float:
    """
    Calculates rank based on the number of seeders. The result is normalized to the range [0, 1]
    """
    return seeders / (100 + seeders)  # inf seeders -> 1; 100 seeders -> 0.5; 10 seeders -> approx 0.1


def freshness_rank(freshness: Optional[float] = 0):
    """
    Calculates rank based on the torrent freshness. The result is normalized to the range [0, 1]
    """
    if not freshness:
        return 0

    days = (freshness or 0) / SECONDS_IN_DAY

    return 1 / (1 + days / 30)  # 2x drop per 30 days


word_re = re.compile(r'\w+', re.UNICODE)


def title_rank(query: str, title: str) -> float:
    """
    Calculate the similarity of the title string to a query string, with or without stemming.
    """
    query = word_re.findall(query.lower())
    title = word_re.findall(title.lower())
    return calculate_rank(query, title)


def calculate_rank(query: List[str], title: List[str]) -> float:
    """
    Calculate the similarity of the title to the query as a float value in range [0, 1].
    """
    if not query:
        return 1.0

    if not title:
        return 0.0

    title = deque(title)
    total_error = 0
    for i, term in enumerate(query):
        # The first word is more important than the second word, and so on
        term_weight = 5 / (5 + i)

        found, skipped = find_term(term, title)
        if found:
            # if the query word is found in the title, add penalty for skipped words in title before it
            total_error += skipped * term_weight
        else:
            # if the query word is not found in the title, add a big penalty for it
            total_error += 10 * term_weight

    # a small penalty for excess words in the title that was not mentioned in the search phrase
    remainder_weight = 1 / (10 + len(query))
    remained_words_error = len(title) * remainder_weight
    total_error += remained_words_error

    # a search rank should be between 1 and 0
    return 10 / (10 + total_error)


def find_term(term: str, title: Deque[str]) -> Tuple[bool, int]:
    """
    Finds the query word in the title.
    Returns whether it was found or not and the number of skipped words in the title.
    """
    try:
        skipped = title.index(term)
    except ValueError:
        return False, 0

    title.rotate(-skipped)  # rotate skipped words to the end
    title.popleft()  # remove found word
    return True, skipped
