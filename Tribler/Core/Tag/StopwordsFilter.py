# Written by Raynor Vliegendhart
# see LICENSE.txt for license information
"""
This module contains a class to read stopwords from files in the Snowball format.
"""

import os

# For some reason, this sometimes fails on my machine:
# from Tribler.__init__ import LIBRARYNAME
# DEFAULT_STOPWORDS_FILE = os.path.join(LIBRARYNAME, 'Core', 'Tag', 'stop_snowball.filter')

# Workaround for now:
DEFAULT_STOPWORDS_FILE = os.path.join(os.path.dirname(__file__), 'stop_snowball.filter')
# TODO: Improve this code ^


class StopwordsFilter:

    def __init__(self, stopwordsfilename=DEFAULT_STOPWORDS_FILE):
        self.stopwords = self._readStopwordsList(stopwordsfilename)

    def _readStopwordsList(self, filename):
        f = open(filename, 'r')
        stopwords = set()
        for line in f:
            word = line.split('|')[0].rstrip()
            if word and not word[0].isspace():
                stopwords.add(word)
        f.close()
        return stopwords

    def isStopWord(self, word):
        return word in self.stopwords

    def getStopWords(self):
        return set(self.stopwords)  # return a copy
