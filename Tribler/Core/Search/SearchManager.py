# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

# ARNOCOMMENT: remove this now it doesn't use KeywordSearch anymore?

import re

# from Tribler.Core.Search.KeywordSearch import KeywordSearch

RE_KEYWORDSPLIT = re.compile(r"[\W_]", re.UNICODE)
DIALOG_STOPWORDS = set(['an', 'and', 'by', 'for', 'from', 'of', 'the', 'to', 'with'])


def split_into_keywords(string, filter_stopwords=False):
    """
    Takes a (unicode) string and returns a list of (unicode) lowercase
    strings.  No empty strings are returned.

    We currently split on non-alphanumeric characters and the
    underscore.

    If filter_stopwords is True a small stopword filter is using to reduce the number of keywords
    """
    if filter_stopwords:
        return [keyword for keyword in RE_KEYWORDSPLIT.split(string.lower())
                if len(keyword) > 0 and keyword not in DIALOG_STOPWORDS]

    return [keyword for keyword in RE_KEYWORDSPLIT.split(string.lower()) if len(keyword) > 0]


def filter_keywords(keywords):
    return [keyword for keyword in keywords if len(keyword) > 0 and keyword not in DIALOG_STOPWORDS]
