from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from itertools import chain
from typing import Dict, Iterable, TypedDict, cast

logger = logging.getLogger(__name__)


class DictWithName(TypedDict):
    """
    A dictionary that has a "name" key.
    """

    name: str


def _words_pattern(min_word_length: int = 3) -> str:
    return r"[^\W\d_]{" + str(min_word_length) + ",}"


def _create_name(content_list: list[DictWithName], number: str, min_word_length: int = 4) -> str:
    """
    Create a name for a group of content items based on the most common word in the title.
    If several most frequently occurring words are found, preference is given to the longest word.

    :param content_list: list of content items
    :param number: group number
    :param min_word_length: minimum word length to be considered as a candidate for the group name
    :returns: created group name. The name is capitalized.
    """
    words: defaultdict[str, int] = defaultdict(int)
    for item in content_list:
        pattern = _words_pattern(min_word_length)
        title_words = {w.lower() for w in re.findall(pattern, item["name"]) if w}
        for word in title_words:
            words[word] += 1
    if not words:
        return number
    m = max(words.values())
    candidates = (k for k, v in words.items() if v == m)
    longest_word = max(candidates, key=len)
    name = f"{longest_word} {number}"
    return name[0].capitalize() + name[1:]


def calculate_diversity(content_list: Iterable[DictWithName], min_word_length: int = 4) -> float:
    """
    Calculate the diversity of words in the titles of the content list.
    The diversity calculation based on Corrected Type-Token Ratio (CTTR) formula.

    :param content_list: list of content items. Each item should have a "name" key with a title.
    :param min_word_length: minimum word length to be considered as a word in the title.
    :returns: diversity of words in the titles
    """
    pattern = _words_pattern(min_word_length)
    titles = (item["name"] for item in content_list)
    words_in_titles = (re.findall(pattern, title) for title in titles)
    words = [w.lower() for w in chain.from_iterable(words_in_titles) if w]
    total_words = len(words)
    if total_words == 0:
        return 0
    unique_words = set(words)

    return len(unique_words) / math.sqrt(2 * total_words)


def group_content_by_number(content_list: Iterable[dict],
                            min_group_size: int = 2) -> Dict[str, list[DictWithName]]:
    """
    Group content by the first number in the title. Returned groups keep the order in which it was found in the input.

    :param content_list: list of content items. Each item should have a "name" key with a title.
    :param min_group_size: minimum number of content items in a group. In the case of a group with fewer items, it will
                           not be included in the result.
    :returns: group number as key and list of content items as value
    """
    groups: defaultdict[str, list[DictWithName]] = defaultdict(list)
    for item in content_list:
        if "name" in item and (m := re.search(r"\d+", item["name"])):
            first_number = m.group(0).lstrip("0") or "0"
            groups[first_number].append(cast(DictWithName, item))

    filtered_groups = ((k, v) for k, v in groups.items() if len(v) >= min_group_size)
    return {_create_name(v, k): v for k, v in filtered_groups}
