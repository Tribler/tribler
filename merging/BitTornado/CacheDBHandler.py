from cachedb2 import *


class MyDBHandler:
    def __init__(self):
        self.mydb = MyDB.getInstance()
        self.peers = PeerDB.getInstance()
    
    def printAll(self):
        data = self.mydb._getall()
        print data
    
    def getSuperpeers(self):
        return self.mydb._get('superpeers', [])

    def addSuperpeer(self, permid):
        if id in self.mydb._get['superpeers']:
            return
        if self.peers.hasPeerID(permid):
            id = self.mydb.peers.getID(permid)
            superpeers = self.mydb.getSuperpeers()
            superpeers.append(id)
            self.mydb._update('superpeers', superpeers)

    def removeSuperpeer(self, permid):
        id = self.peers.getID(permid)
        try:
            superpeers = self.mydb.getSuperpeers()
            superpeers.remove(id)
            self._update('superpeers', superpeers)
        except:
            pass

            
class PeerDBHandler:
    def __init__(self):
        self.peers = PeerDB.getInstance()
        
    def getAllPeers(self):
        res = self._data.values()
    
    def printAll(self):
        records = self._getall()
        print "========== all records in peer table ==========", len(records)
        for record in records.values:
            print record
        
    def getPeer(self, permid):
        return self.peers.get(permid)
        
    def hasPeer(self, peer):
        if not validPeer(peer):
            return False
        permid = peer['permid']
        return self.peers.find(permid)
        
    def findPeer(self, key, value):
        res = []
        if key not in self.peers.default_peer:
            return res
        if key is 'permid':
            peer = self.getPeer(value)
            if peer:
                res.append(peer)
        else:
            try:
                for peer in self._getall():
                    if peer[key] == value:
                        res.append(peer)
            except KeyError:
                pass
        return res
        