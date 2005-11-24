import time

from BitTornado.cachedb import PreferenceTable


class PrefCacheHandler:
    """ The peers you have seen or imported from your friends """
    
    def __init__(self):
        self.preferences = PreferenceTable.getInstance()
        self.peers = self.preferences.peers
        self.torrents = self.preferences.torrents
        
    def getPrefByPermID(self, permid):
        return self.preferences.findPrefByPermID(permid)
        
    def getPrefByID(self, id):
        return self.preferences.findPrefByID(id)
    
    def getPrefListByID(self, id):
        prefs = self.getPrefByID(id)
        preflist = []
        for pref in prefs:
            preflist.append(pref['torrent_hash'])
        return preflist
    
    def addPreference(self, peer, torrent_hash, have):
        if not isinstance(peer, dict) or not peer.has_key('permid'):
            return
        peer['torrent_hash'] = torrent_hash
        self.peers.addPeer(peer)
        self.peers.add
        
    
    