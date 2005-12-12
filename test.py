from BitTornado.cachedb import SuperPeerTable, PeerTable, TorrentTable, PreferenceTable, dropTables
from BitTornado.CacheDBHandler import *

if __name__ == "__main1__":
    spew = [{'ip':'202.115.39.6', 'permid':'2', 'torrent_hash':'a'}, # ip, permid, infohash
            {'ip':'211.156.43.12', 'permid':None, 'torrent_hash':'b', 'name':'Jie'},
            {'ip':'101.145.163.41', 'permid':None, 'torrent_hash':'a'},
            {'ip':'221.155.211.12', 'permid':'99', 'torrent_hash':'b'},
            {'ip':'221.15.21.11', 'permid':'2', 'torrent_hash':'c'}
            ]
    #dropTables()
    print "create PeerList"
    peers = PeerTable.getInstance()
    print "add test data"
    for item in spew:
        print "add", item
        peers.addPeer(item)
        records = peers.printRecords()
        
#    print "remove", '2'
#    peers.removePeer(None, '2')
#    peers.printRecords()
#    
#    print "remove", '221.155.211.12'
#    peers.removePeer(None, None, '221.155.211.12')
#    peers.printRecords()
#    
#    print "remove", '221.15.21.11'
#    peers.removePeer(None, None, '221.15.21.11')
#    peers.printRecords()
#    print
    
    torrents = peers.torrents
    preferences = peers.preferences
    torrents.printRecords()
    preferences.printRecords()

def printOld():
    peers = PeerTable.getInstance()
    torrents = TorrentTable.getInstance()
    preferences = PreferenceTable.getInstance()
    superpeers = SuperPeerTable.getInstance()
    
    print "print records"
    
    peers.printRecords()
    torrents.printRecords()
    preferences.printRecords()
    superpeers.printRecords()
    
    
def printNew():
    mydb = MyDBHandler()
    mydb.printAll()
    
    
if __name__ == "__main__":
    printNew()
    #printOld()
    