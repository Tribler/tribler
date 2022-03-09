"""
Search utilities.

Author(s): Jelle Roozenburg, Arno Bakker
"""
import re

RE_KEYWORD_SPLIT = re.compile(r"[\W_]", re.UNICODE)
DIALOG_STOPWORDS = {'an', 'and', 'by', 'for', 'from', 'of', 'the', 'to', 'with'}


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
