""" Peer Cache, Friend Cache and BarterBuddy Cache"""

import time

from BitTornado.cachedb import PeerTable, string, friendly_time


class PeerCacheHandler:
    """ The peers you have seen or imported from your friends """
    
    def __init__(self):
        self.peers = PeerTable.getInstance()
        self.preferences = self.peers.preferences
        self.torrents = self.peers.torrents
        
    def updatePeer(self, torrent_hash, peer):
        if not peer.has_key('torrent_hash'):
            peer.update({'torrent_hash':torrent_hash})
        self.peers.addPeer(peer)
        
    def addPeer(self, peer):
        self.peers.addPeer(peer)
            
    def updateSpew(self, torrent_hash, spew):
        if spew is None:
            return
        for peer in spew:
            if not peer.has_key('torrent_hash'):
                peer.update({'torrent_hash':torrent_hash})
            self.peers.addPeer(peer)
    
    def updatePeerTrust(self, peer_id, trust):
        self.peers.updatePeerTrust(peer_id, trust)
        
    def addFriend(self, peer_id):
        self.peers.addFriend(peer_id)
        
    def removeFriend(self, peer_id):
        self.peers.removeFriend(peer_id)
        
    def getBuddies(self, last_file=True):
        peers = self.getPeers(last_file)
        buddies = []
        for peer in peers:
            if peer['permid'] and peer['friend'] != 1:
                buddies.append(peer)

        return buddies
    
    def getFriends(self, last_file=True):
        peers = self.getPeers(last_file)
        friends = []
        for peer in peers:
            if peer['permid'] and peer['friend'] == 1:
                friends.append(peer)
            
        return friends
    
    def getPeers(self, last_file=True, show_friendly_time=True):    # only used for 
        peers = self.peers.getRecords()
        for peer in peers:
            peer['created_time'] = time.ctime(peer['created_time'])
            if show_friendly_time:
                peer['last_seen'] = friendly_time(peer['last_seen'])
            if last_file:
                peer['last_file'] = ''
                pres = self.preferences.findPreference(peer_id = peer['id'])
                if pres:
                    pres.sort()    #TODO: sort by time
                    tid = pres[0]['torrent_id']
                    torrents = self.torrents.findTorrent(torrent_id=tid)
                    if torrents:
                        torrent = torrents[0]
                        peer['last_file'] = torrent['content_name']
            #string(peer)
            
        return peers
    
