# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

# ARNOCOMMENT: remove this now it doesn't use KeywordSearch anymore?

import sys

#from Tribler.Core.Search.KeywordSearch import KeywordSearch

DEBUG = False

KEYWORDSPLIT_RE = r'[\W_]+' # i.e. split on alnum, not alnum+underscore


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


