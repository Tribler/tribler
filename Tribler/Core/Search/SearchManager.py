# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

# ARNOCOMMENT: remove this now it doesn't use KeywordSearch anymore?

import re

re_keywordsplit = re.compile(r"[\W_]", re.UNICODE)
dialog_stopwords = set(['an', 'and', 'by', 'for', 'from', 'of', 'the', 'to', 'with'])


def split_into_keywords(string, filterStopwords=False):
    """
    Takes a (unicode) string and returns a list of (unicode) lowercase
    strings.  No empty strings are returned.

    We currently split on non-alphanumeric characters and the
    underscore.

    If filterStopwords is True a small stopword filter is using to reduce the number of keywords
    """
    if filterStopwords:
        return [keyword for keyword in re_keywordsplit.split(string.lower()) if len(keyword) > 0 and keyword not in dialog_stopwords]

    return [keyword for keyword in re_keywordsplit.split(string.lower()) if len(keyword) > 0]


def filter_keywords(keywords):
    return [keyword for keyword in keywords if len(keyword) > 0 and keyword not in dialog_stopwords]
