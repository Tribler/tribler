# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

# ARNOCOMMENT: remove this now it doesn't use KeywordSearch anymore?

import re
import sys

#from Tribler.Core.Search.KeywordSearch import KeywordSearch

DEBUG = False

re_keywordsplit = re.compile(r"[\W_]", re.UNICODE)
def split_into_keywords(string):
    """
    Takes a (unicode) string and returns a list of (unicode) lowercase
    strings.  No empty strings are returned.

    We currently split on non-alphanumeric characters and the
    underscore.  This ensures that the keywords are SQL insertion
    proof.
    """
    return [keyword for keyword in re_keywordsplit.split(string.lower()) if len(keyword) > 0]


class SearchManager:
    """ Arno: This is DB neutral. All it assumes is a DBHandler with
    a searchNames() method that returns records with at least a 'name' field
    in them.
    """
    
    def __init__(self,dbhandler):
        self.dbhandler = dbhandler
        # self.keywordsearch = KeywordSearch()
    
    def search(self,kws,maxhits=None):
        """ Called by any thread """
        if DEBUG:
            print >>sys.stderr,"SearchManager: search",kws
            
        hits = self.dbhandler.searchNames(kws)
        if maxhits is None:
            return hits
        else:
            return hits[:maxhits]

    def searchChannels(self, query): ##
        data = self.dbhandler.searchChannels(query) 
        return data


