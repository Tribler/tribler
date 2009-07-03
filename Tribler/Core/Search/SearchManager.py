# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information
import sys

from Tribler.Core.Search.KeywordSearch import KeywordSearch

DEBUG = False

class SearchManager:
    """ Arno: This is DB neutral. All it assumes is a DBHandler with
    a searchNames() method that returns records with at least a 'name' field
    in them.
    """
    
    def __init__(self,dbhandler):
        self.dbhandler = dbhandler
        self.keywordsearch = KeywordSearch()
    
    def search(self,kws,maxhits=None):
        """ Called by any thread """
        if DEBUG:
            print >>sys.stderr,"SearchManager: search",kws
            
        namerecs = self.dbhandler.searchNames(kws)    

        if DEBUG:
            print >>sys.stderr,"SearchManager: search: Got namerecs",len(namerecs),`namerecs`
        
        hits = self.keywordsearch.search(namerecs,kws)
        
        if DEBUG:
            print >>sys.stderr,"SearchManager: search: Filtered namerecs",len(hits)
        
        if maxhits is None:
            return hits
        else:
            return hits[:maxhits]

