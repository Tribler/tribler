# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
import time
from Tribler.Core.Subtitles.MetadataDomainObjects import Languages
import threading



PEERS_RESULT_LIMIT = 5
HAVE_VALIDITY_TIME = 7*86400 # one week (too big? to small?)

# how often (in seconds) old have messages will be removed from the database
# -1 means that they will be cleaned up only at Tribler's startup
CLEANUP_PERIOD = -1

class PeersHaveManager(object):
    '''
    Manages the insertion, retrieval and manipulation of 
    subtitle have messages from other peers.
    
    The public interface consists only of the two methods:
    
    + getPeersHaving(channel, infohash, bitmask)
    + newHaveReceived(channel, infohash, peer_id, havemask)
    
    See method descriptions for further details
    '''
    
    __single = None
    _singletonLock = threading.RLock()
    def __init__(self):
        
        with PeersHaveManager._singletonLock:
            #Singleton pattern not enforced: this makes testing easier
            PeersHaveManager.__single = self
            
        self._haveDb = None
        self._olBridge = None
        self._cleanupPeriod = CLEANUP_PERIOD
        self._haveValidityTime = HAVE_VALIDITY_TIME
        self._langsUtility = Languages.LanguagesProvider.getLanguagesInstance()
        self._firstCleanedUp = False
        
        self._registered = False
        
    @staticmethod
    def getInstance():
        with PeersHaveManager._singletonLock:
            if PeersHaveManager.__single == None:
                PeersHaveManager()
        
        return PeersHaveManager.__single
        
    def register(self, haveDb, olBridge):
        '''
        Inject dependencies
        
        @type haveDb: Tribler.Core.CacheDB.MetadataDBHandler
        @type olBridge: OverlayBridge

        '''
        assert haveDb is not None
        assert olBridge is not None
        
        self._haveDb = haveDb
        self._olBridge = olBridge
        
        self._registered = True
        
    def isRegistered(self):
        return self._registered
    
    
    def getPeersHaving(self, channel, infohash, bitmask, limit=PEERS_RESULT_LIMIT):
        '''
        Returns a list of permids of peers having all the subtitles for
        (channel, infohash) specified in the bitmask
        
        Notice that if there exist a peer that has only some of the subtitles
        specified in the bitmask, that peer will not be included
        in the returned list.
        
        This implementation returns the peers sorted by most recently received
        have message first.
        
        @type channel: str
        @param channel: binary channel_id
        
        @type infohash: str
        @param infohash: binary infohash
        
        @type bitmask: int
        @param bitmask: a 32 bit bitmask specifieng the desired subtitles languages
                        for returned peers to have.
                        
        @type limit: int
        @param limit: an upper bound on the size of the returned list. Notice
                      that anyway the returned list may be smaller then limit
                      (Default 5)
                      
        @rtype: list
        @return: a list of binary permids of peers that have all the subitles
                 specified by the bitmask. If there is no suitable entry the returned
                 list will be empty
        '''
        
        # results are already ordered by timestamp due the current
        # MetadataDBHandler implementation
        peersTuples = self._haveDb.getHaveEntries(channel, infohash)
        peers_length = len(peersTuples)
        length = peers_length if peers_length < limit else limit
        
        results = list()
        
        for i in range(length):
            peer_id, havemask, timestamp = peersTuples[i]
            if havemask & bitmask == bitmask:
                results.append(peer_id)
                
        if len(results) == 0:
            #if no results, and if the channel owner was not in the initial
            #list, consider him always as a valid source
            results.append(channel)
                
        return results
        
    
    def newHaveReceived(self, channel, infohash, peer_id, havemask):
        '''
        Notify the PeerHaveManager that a new SUBTITLE HAVE announcement has been
        received.
        
        @type channel: str
        @param channel: binary channel_id 
        
        @type infohash: str
        @param infohash: binary infohash
        
        @type peer_id: str
        @param channel: binary permid of the peer that sent
                        this havemask
                        
        @type havemask: int
        @param havemask: integer bitmask representing which combination of subtitles
                         peer_id has for the given (channel, infohash) pair
        '''
        
        
        timestamp = int(time.time())
        self._haveDb.insertOrUpdateHave(channel, infohash, peer_id, havemask, timestamp)
        
    
    def retrieveMyHaveMask(self, channel, infohash):
        '''
        Creates the havemask for locally available subtitles for channel,infohash
        
        @type channel: str
        @param channel: a channelid to retrieve the local availability mask for (binary)
        @type infohash: str
        @param infohash: the infohash of the torrent to retrieve to local availability mask
                        for (binary)
        
        @rtype: int
        @return: a bitmask reprsenting wich subtitles languages are locally available
                 for the given (channel, infohash) pair. If no one is available, or even
                 if no rich metadata has been ever received for that pair, a zero bitmask
                 will be returned. (i.e. this method should never thorow an exception if the
                 passed parametrers are formally valid)
        '''
        
        localSubtitlesDict = self._haveDb.getLocalSubtitles(channel, infohash)
        
        havemask = self._langsUtility.langCodesToMask(localSubtitlesDict.keys())
        
        return havemask
    
    def startupCleanup(self):
        '''
        Cleanup old entries in the have database.
        
        This method is meant to be called only one time in PeersManager instance lifetime,
        i.e. at Tribler's startup. Successive calls will have no effect.
        
        If CLEANUP_PERIOD is set to a positive value, period cleanups actions will be
        scheduled.
        '''
        if not self._firstCleanedUp:
            self._firstCleanedUp = True
            self._schedulePeriodicCleanup()
        
    def _schedulePeriodicCleanup(self):
        
        minimumAllowedTS = int(time.time()) - self._haveValidityTime
        self._haveDb.cleanupOldHave(minimumAllowedTS)
        
        if self._cleanupPeriod > 0:
            self._olBridge.add_task(self._schedulePeriodicCleanup, self._cleanupPeriod)
            
        


        