# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

from Tribler.Core.Search.KeywordSearch import KeywordSearch


class SearchManager:
    
    def __init__(self,torrent_db):
        self.torrent_db = torrent_db
        self.keywordsearch = KeywordSearch()
    
    def search(self,kws,maxhits=None):
        """ Called by any thread """
        if DEBUG:
            print >>sys.stderr,"SearchManager: search",kws
            
        torrentrecs = self.torrent_db.searchNames(kws)    
        
        hits = self.keywordsearch.search(torrentrecs,kws)
        if maxhits is None:
            return hits
        else:
            return hits[:maxhits]

