# written by Nicolas Neubauer
# see LICENSE.txt for license information

import sys, time

DEBUG = False

class Reranker:
    def getID(self):
        """the ID that is stored in the clicklog 'reranking_strategy' field for later comparison"""
        return 0
    
    def rerank(self, hits, keywords, torrent_db, pref_db, mypref_db, search_db):
        """takes hits and reorders them given the current keywords"""
        return hits
    
class DefaultTorrentReranker(Reranker):
    """ just leave the hits alone """
    def getID(self):
        return 1
    def rerank(self, hits, keywords, torrent_db, pref_db, mypref_db, search_db):
        return hits    
    
class TestReranker(Reranker):
    """ for testing purposes only """
    def getID(self):
        return 2
    def rerank(self, hits, keywords, torrent_db, pref_db, mypref_db, search_db):
        if len(hits)>1:
            h = hits[0]
            hits[0] = hits[1]
            hits[1] = h
        return hits  
    
class SwapFirstTwoReranker(Reranker):
    """ swaps first and second place if second place has been frequently selected from bad position """
    
    def __init__(self):
        self.MAX_SEEN_BEFORE_RERANK = 5
        self.MAX_POPULAR_RATIO = 5
    
    def getID(self):
        return 2
    
    def rerank(self, hits, keywords, torrent_db, pref_db, mypref_db, search_db):
        if len(hits)<2:
            return hits
        
        torrent_id_0 = hits[0].get('torrent_id',None)
        torrent_id_1 = hits[1].get('torrent_id',None)
        if not torrent_id_0 or not torrent_id_1:
            if DEBUG:
                print >> sys.stderr, "reranking: torrent_id=0 in hits, exiting"
            # we got some problems elsewhere, don't add to it
            return hits
        
        (num_hits_0, position_score_0) = pref_db.getPositionScore(torrent_id_0, keywords)
        (num_hits_1, position_score_1) = pref_db.getPositionScore(torrent_id_1, keywords)
        if DEBUG:
            print >> sys.stderr, "reranking:  first torrent (%d): (num, score)= (%s, %s)" % (torrent_id_0, num_hits_0, position_score_0)
            print >> sys.stderr, "reranking: second torrent (%d): (num, score)= (%s, %s)" % (torrent_id_1, num_hits_1, position_score_1)
             
        if (num_hits_0 < self.MAX_SEEN_BEFORE_RERANK or num_hits_1 < self.MAX_SEEN_BEFORE_RERANK):
            # only start thinking about reranking if we have seen enough samples
            if DEBUG:
                print >> sys.stderr, "reranking: not enough samples, not reranking"
            return hits
        
        if (num_hits_0/num_hits_1 > self.MAX_POPULAR_RATIO):
            # if number one is much more popular, keep everything as it is
            if DEBUG:
                print >> sys.stderr, "reranking: first torrent is too popular, not reranking"            
            return hits
        
        # if all these tests are successful, we may swap first and second if second 
        # has gotten hits from worse positions than first
        
        if position_score_0<position_score_1:
            if DEBUG:
                print >> sys.stderr, "reranking: second torrent has better position score, reranking!"                        
            h = hits[0]
            hits[0] = hits[1]
            hits[1] = h
        else:
            if DEBUG:
                print >> sys.stderr, "reranking: second torrent does not have better position score, reranking!"                        
            
        return hits      
    
_rerankers = [DefaultTorrentReranker(), SwapFirstTwoReranker()]


def getTorrentReranker():
    global _rerankers
    index = int(time.strftime("%H")) % (len(_rerankers))
    return _rerankers[index]
 
