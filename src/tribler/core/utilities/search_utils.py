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
    Calculate the similarity of the title to the query as a float value in range [0, 1].
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

        # Read the description of the `find_word` function to understand what is going on. Basically, we are trying
        # to find each query word in the title words, calculate the penalty if the query word is not found or if there
        # are some title words before it, and then rotate the skipped title words to the end of the title. This way,
        # the least penalty got a title that has query words in the proper order at the beginning of the title.
        found, skipped = find_word(word, title)
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


def find_word(word: str, title: Deque[str]) -> Tuple[bool, int]:
    """
    Finds the query word in the title.
    Returns whether it was found or not and the number of skipped words in the title.

    This is a helper function to efficiently answer a question of how close a query string and a title string are,
    taking into account the ordering of words in both strings.

    The `word` parameter is a word from a search string.

    The `title` parameter is a deque of words from the torrent title. It also can be a deque of stemmed words
    if the `torrent_rank` function supports stemming.

    The `find_word` function returns the boolean value of whether the word was found in the title deque or not and
    the number of the skipped leading words in the `title` deque. Also, it modifies the `title` deque in place by
    removing the first entrance of the found word and rotating all leading non-matching words to the end of the deque.

    An example: find_word('A', deque(['X', 'Y', 'A', 'B', 'C'])) returns `(True, 2)`, where True means that
    the word 'A' was found in the `title` deque, and 2 is the number of skipped words ('X', 'Y'). Also, it modifies
    the `title` deque, so it starts looking like deque(['B', 'C', 'X', 'Y']). The found word 'A' was removed, and
    the leading non-matching words ('X', 'Y') was moved to the end of the deque.

    Now some examples of how the function can be used. To use the function, you can call it one time for each word
    from the query and see:
    - how many query words are missed in the title;
    - how many excess or out-of-place title words are found before each query word;
    - and how many title words are not mentioned in the query.

    Example 1, query "A B C", title "A B C":
    find_word("A", deque(["A", "B", "C"])) -> (found=True, skipped=0, rest=deque(["B", "C"]))
    find_word("B", deque(["B", "C"])) -> (found=True, skipped=0, rest=deque(["C"]))
    find_word("C", deque(["C"])) -> (found=True, skipped=0, rest=deque([]))
    Conclusion: exact match.

    Example 2, query "A B C", title "A B C D":
    find_word("A", deque(["A", "B", "C", "D"])) -> (found=True, skipped=0, rest=deque(["B", "C", "D"]))
    find_word("B", deque(["B", "C", "D"])) -> (found=True, skipped=0, rest=deque(["C", "D"]))
    find_word("C", deque(["C", "D"])) -> (found=True, skipped=0, rest=deque(["D"]))
    Conclusion: minor penalty for one excess word in the title that is not in the query.

    Example 3, query "A B C", title "X Y A B C":
    find_word("A", deque(["X", "Y", "A", "B", "C"])) -> (found=True, skipped=2, rest=deque(["B", "C", "X", "Y"]))
    find_word("B", deque(["B", "C", "X", "Y"])) -> (found=True, skipped=0, rest=deque(["C", "X", "Y"]))
    find_word("C", deque(["C", "X", "Y"])) -> (found=True, skipped=0, rest=deque(["X", "Y"]))
    Conclusion: major penalty for skipping two words at the beginning of the title plus a minor penalty for two
    excess words in the title that are not in the query.

    Example 4, query "A B C", title "A B X Y C":
    find_word("A", deque(["A", "B", "X", "Y", "C"])) -> (found=True, skipped=0, rest=deque(["B", "X", "Y", "C"]))
    find_word("B", deque(["B", "X", "Y", "C"])) -> (found=True, skipped=0, rest=deque(["X", "Y", "C"]))
    find_word("C", deque(["X", "Y", "C"])) -> (found=True, skipped=2, rest=deque(["X", "Y"]))
    Conclusion: average penalty for skipping two words in the middle of the title plus a minor penalty for two
    excess words in the title that are not in the query.

    Example 5, query "A B C", title "A C B":
    find_word("A", deque(["A", "C", "B"])) -> (found=True, skipped=0, rest=deque(["C", "B"]))
    find_word("B", deque(["C", "B"])) -> (found=True, skipped=1, rest=deque(["C"]))
    find_word("C", deque(["C"])) -> (found=True, skipped=0, rest=deque(["C"]))
    Conclusion: average penalty for skipping one word in the middle of the title.

    Example 6, query "A B C", title "A C X":
    find_word("A", deque(["A", "C", "X"])) -> (found=True, skipped=0, rest=deque(["C", "X"]))
    find_word("B", deque(["C", "X"])) -> (found=False, skipped=0, rest=deque(["C", "X"]))
    find_word("C", deque(["C", "X"])) -> (found=True, skipped=0, rest=deque(["X"]))
    Conclusion: huge penalty for missing one query word plus a minor penalty for one excess title word.
    """
    try:
        skipped = title.index(word)
    except ValueError:
        return False, 0

    title.rotate(-skipped)  # rotate skipped words to the end
    title.popleft()  # remove found word
    return True, skipped
