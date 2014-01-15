# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

# ARNOCOMMENT: remove this now it doesn't use KeywordSearch anymore?

import re
import sys
import logging

# from Tribler.Core.Search.KeywordSearch import KeywordSearch

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


def fts3_preprocess(keywords):
    fts3_only = []
    normal_keywords = []

    keywords = keywords.split()
    for keyword in keywords:
        if keyword[0] == '-':
            fts3_only.append(keyword)
        elif keyword[0] == '*' or keyword[-1] == "*":
            fts3_only.append(keyword)
        elif keyword.find(':') != -1:
            fts3_only.append(keyword)
        else:
            normal_keywords.append(keyword)

    return fts3_only, " ".join(normal_keywords)


class SearchManager:

    """ Arno: This is DB neutral. All it assumes is a DBHandler with
    a searchNames() method that returns records with at least a 'name' field
    in them.
    """

    def __init__(self, dbhandler):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.dbhandler = dbhandler
        # self.keywordsearch = KeywordSearch()

    def search(self, kws, maxhits=None):
        """ Called by any thread """
        self._logger.debug("SearchManager: search %s", kws)

        hits = self.dbhandler.searchNames(kws)
        if maxhits is None:
            return hits
        else:
            return hits[:maxhits]

    def searchLibrary(self):
        return self.dbhandler.getTorrents(sort="name", library= True)

    def searchChannels(self, query):
        data = self.dbhandler.searchChannels(query)
        return data
