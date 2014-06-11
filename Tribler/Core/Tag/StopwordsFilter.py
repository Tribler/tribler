# Written by Raynor Vliegendhart
# see LICENSE.txt for license information
"""
This module contains a class to read stopwords from files in the Snowball format.
"""

import os

from Tribler import LIBRARYPATH
DEFAULT_STOPWORDS_FILE = os.path.join(LIBRARYPATH, 'Core', 'Tag', 'stop_snowball.filter')


class StopwordsFilter:

    def __init__(self, stopwordsfilename=DEFAULT_STOPWORDS_FILE):
        file_stream = open(stopwordsfilename, 'r')
        self._stopwords = set()
        for line in file_stream:
            word = line.split('|')[0].rstrip()
            if word and not word[0].isspace():
                self._stopwords.add(word)
        file_stream.close()

    def isStopWord(self, word):
        return word in self._stopwords

    def getStopWords(self):
        return set(self._stopwords)  # return a copy
