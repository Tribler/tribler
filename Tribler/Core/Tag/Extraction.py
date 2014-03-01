# Written by Raynor Vliegendhart
# see LICENSE.txt for license information

import os
import re

from Tribler import LIBRARYNAME
from Tribler.Core.Misc.Singleton import ThreadSafeSingleton
from Tribler.Core.Search.SearchManager import split_into_keywords
from Tribler.Core.Tag.StopwordsFilter import StopwordsFilter


class TermExtraction(ThreadSafeSingleton):

    def __init__(self, install_dir='.'):
        super(TermExtraction, self).__init__()

        filterfn = os.path.join(install_dir, LIBRARYNAME, 'Core', 'Tag', 'stop_snowball.filter')
        self.stopwords_filter = StopwordsFilter(stopwordsfilename=filterfn)

        self.containsdigits_filter = re.compile(r'\d', re.UNICODE)
        self.alldigits_filter = re.compile(r'^\d*$', re.UNICODE)
        self.isepisode_filter = re.compile(r'^s\d{2}e\d{2}', re.UNICODE)

        self.domain_terms = set('www net com org'.split())

    def extractTerms(self, name_or_keywords):
        """
        Extracts the terms from a torrent name.

        @param name_or_keywords The name of the torrent. Alternatively, you may
        pass a list of keywords (i.e., the name split into words using split_into_keywords).
        @return A list of extracted terms in order of occurence. The list may contain duplicates
        if a term occurs multiple times in the name.
        """
        if isinstance(name_or_keywords, basestring):
            keywords = split_into_keywords(name_or_keywords)
        else:
            keywords = name_or_keywords

        return [term for term in keywords if self.isSuitableTerm(term)]

    def extractBiTermPhrase(self, name_or_keywords):
        """
        Extracts a bi-term phrase from a torrent name. Currently, this phrase consists
        of the first two terms extracted from it.

        @param name_or_keywords The name of the torrent. Alternatively, you may
        pass a list of keywords (i.e., the name split into words using split_into_keywords).
        @return A tuple containing the two terms of the bi-term phrase. If there is no bi-term,
        i.e. less than two terms were extracted, None is returned.
        """
        terms = [term for term in self.extractTerms(name_or_keywords)
                 if self.containsdigits_filter.search(term) is None]
        if len(terms) > 1:
            return tuple(terms[:2])
        else:
            return None

    def isSuitableTerm(self, term):
        """
        Determines if a term is "suitable". Current rules are:
            1. Length of term is at least 3 characters.
            2. Term is not a stopword.
            3. Fully numeric terms are not suitable, except when they
               describe a year from the 20th or 21st century.
            4. Does not describe an episode (s##e##).
            5. Term is not equal to www, net, com, or org.

        @return True iff a term is suitable.
        """
        if len(term) < 3:
            return False
        elif self.stopwords_filter.isStopWord(term):
            return False
        elif self.alldigits_filter.match(term) is not None:
            if len(term) == 4:
                if term.startswith('19') or term.startswith('20'):
                    return True
            return False
        elif self.isepisode_filter.match(term) is not None:
            return False
        elif term in self.domain_terms:
            return False
        else:
            return True
