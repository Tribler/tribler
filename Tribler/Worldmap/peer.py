# Written by Jie Yang
# see LICENSE.txt for license information

import socket
import sys
import cPickle

from ipinfo import IPInfo

class MyPeer:
    """ This class presents the user himself """
    
    def __init__(self, ABCTorrent):
        self.torrent = ABCTorrent
        self.statistics = None
        self.ip = str(socket.gethostbyname(socket.gethostname()))
        self.ip_info = IPInfo.lookupIPInfo(self.ip)
        self.display = False
        print "create my peer"

    def updateStatistics(self, statistics):
        self.statistics = statistics
        

class BTPeer:
    """ This class presents an actived peer. It contains all information about this peer,
    displays this peer in the world map, and manages the popup info window
    """
    
    def __init__(self, bt_info, ABCTorrent, rawserver = None, permid=''):
        self.torrent = ABCTorrent
        self.bt_info = bt_info
        self.active = True
        self.ip = bt_info['ip']
        self.permid = permid    # When a peer comes can I get its PermID??
        if self.permid:        # Use PermID by default
            self.id_type = 'permid'
        else:
            self.id_type = 'ip'
            self.id = self.ip
        self.ip_info = None
        self.torrent.peer_swarm[self.ip] = self
        rawserver.add_task(self.lookupIPInfo, 0)

    def updateBTInfo(self, bt_info):
        self.bt_info.update(bt_info)
        
    def lookupIPInfo(self):
        self.ip_info = IPInfo.lookupIPInfo(self.ip)   

class BTBuddy:
    """ This class presents a bater buddy who used/is using a same bittorrent file as you
    and was seen by you. 
    """
    
#    Buddy_swarm = {}      # all the buddies which the user has ever seen
    
    def __init__(self):
        self.peer = {}
        self.peer['peer_id'] = btpeer.id
        self.peer['contact'] = {}    # msn:'', skype:'', email:[], phone:[] etc.
        self.peer['dtotal'] = 0
        self.peer['utotal'] = 0
        self.peer['max_uprate'] = 0
        self.peer['max_downrate'] = 0
        self.peer['max_speed'] = 0
        self.peer['meet_times'] = 0    # Times we meet again
        self.peer['friend_layer'] = 0    # 0: not friend, 1: your friend, 2: friend of your friend, etc.
        self.peer['torrents'] = self.torrents = []   # All torrents this buddy ever used
        self.peer['lastfile'] = ''   # All files this buddy ever downloaded 
        self.dtotal = {}    # total download, each item is a torrent
        self.utotal = {}
        self.old_dtotal = 0
        self.old_utotal = 0
        PeerList.append(self.peer)
        
    def updateByOpen(self, record):
        """ restore the buddy's values by reading saved file """
        
        self.peer_id = record['peer_id']
        self.peer['contact'] = record['contact']
        self.old_dtotal = self.peer['dtotal'] = record['dtotal']
        self.old_utotal = self.peer['utotal'] = record['utotal']
        self.peer['max_uprate'] = record['max_uprate']
        self.peer['max_downrate'] = record['max_downrate']
        self.peer['max_speed'] = record['max_speed']
        self.peer['meet_times'] = record['meet_times']
        self.peer['friend_layer'] = record['friend_layer']
        self.peer['torrents'] = record['torrents']
        self.peer['lastfile'] = record['lastfile']
        
    def updateByBTPeer(self, btpeer, torrent_id):
        """ update the buddy by yourself """
        
        self.dtotal[torrent_id] = btpeer.dtotal
        self.utotal[torrent_id] = btpeer.utotal
        self.peer['dtotal'] = self.old_dtotal + sum(self.dtotal.values())
        self.peer['utotal'] = self.old_utotal + sum(self.utotal.values())
        if btpeer.speed > self.peer['max_speed']:
            self.peer['max_speed'] = btpeer.speed
        if btpeer.uprate > self.peer['max_uprate']:
            self.peer['max_uprate'] = btpeer.uprate
        if btpeer.downrate > self.peer['max_downrate']:
            self.peer['max_downrate'] = btpeer.downrate
        
    def updateByFriend(self, friend):
        """ update the buddy by your friends """

        self.peer_id = friend['peer_id']
        self.peer['contact'] = friend['contact']
        self.peer['max_uprate'] = friend['max_uprate']
        self.peer['max_downrate'] = friend['max_downrate']
        self.peer['max_speed'] = friend['max_speed']
        self.peer['friend_layer'] = friend['friend_layer'] + 1    # friend of friend
        self.peer['torrents'] = friend['torrents']
        self.peer['lastfile'] = friend['lastfile']
                        
    def addTorrent(self, ABCTorrent):
        """ add a torrent into the buddy's torrent list """
        
        self.peer['lastfile'] = torrent.filename
        try:
            idx = self.torrents.index(ABCTorrent.id)    # test if this torrent appeared before
            return
        except:
            pass
        BTTorrent(torrent)    # add a new torrent and insert it into Torrent_list
        self.torrents.append(torrent.id)
        
    def meetAgain(self, torrent=None):
        self.peer['meet_times'] += 1
        if torrent is not None:
            self.addTorrent(torrent)
    
    #TODO: after lunch....
    def update_info(self, bt_id, bt_info):
        assert self.torrents.has_key(bt_id)
        self.torrents[bt_id].update_info(bt_info)
        
    def statistics(self):
        self.filelist = []
        self.total_up = 0
        self.total_down = 0
        self.max_uprate = 0
        self.max_downrate = 0
        for torrent in self.torrents.values():
            self.filelist.append(torrent.filename)
            self.total_up += torrent.total_up
            self.total_down += torrent.total_down
            if torrent.max_uprate > self.max_uprate:
                self.max_uprate = torrent.max_uprate
            if torrent.max_downrate > self.max_downrate:
                self.max_downrate = torrent.max_downrate
                
    def loadBuddySwarm():
        """ Load Buddy_swarm from disk """
        
        file_path = "buddy.dat"
        print "Loading buddy list from", file_path, "..."
        try:
            buddy_file = open(file_path, "r")
            BTBuddy.Buddy_swarm = cPickle.load(buddy_file)
            buddy_file.close()
        except:
            pass
                    
    loadBuddySwarm = staticmethod(loadBuddySwarm)
        
    def saveBuddySwarm():
        """ Save Buddy_swarm on disk """
        
        file_path = "buddy.dat"
        try:
            buddy_file = open(file_path, "w")
        except IOError, message:
            print >> sys.stderr, "Buddy file", file_path, "could not be opened:", message
            return
            
        try:
            cPickle.dump(BTBuddy.Buddy_swarm, buddy_file)
        except Exception, message:
            pass

        buddy_file.close()
            
    saveBuddySwarm = staticmethod(saveBuddySwarm)


class BTTorrent:
    """ Torrent information of each buddy """
    
    def __init__(self, ABCTorrent):
        self.torrent = {}
        self.torrent['id'] = ABCTorrent.id
        self.torrent['filename'] = ABCTorrent.filename
        self.torrent['description'] = ''
        self.torrent['tags'] = []    # for future extension
        self.torrent['size'] = ABCTorrent.realsize
        self.torrent['time'] = os.time()
        
    def __str__(self):
        return self.filename
        
    def update_info(self, bt_info):
        self.total_up = bt_info['utotal']
        self.total_down = bt_info['dtotal']
        #TODO: find stable up/down rate, avg rate, total 
        if bt_info['uprate'] > self.max_uprate:
            self.max_uprate = bt_info['uprate']
        if bt_info['downrate'] > self.max_downrate:
            self.max_downrate = bt_info['downrate']
            
    def loadTorrentStore():
        """ Load Torrent_store from disk """
        
        file_path = "torrent.dat"
        print "Loading torrent list from", file_path, "..."
        try:
            torrent_file = open(file_path, "r")
            BTTorrent.Torrent_store = cPickle.load(torrent_file)
            torrent_file.close()
        except:
            pass

    loadTorrentStore = staticmethod(loadTorrentStore)
        
    def saveTorrentStore():
        """ Save Torrent_store on disk """
        
        file_path = "torrent.dat"
        print "saving torrent store ... "
        try:
            torrent_file = open(file_path, "w")
        except Exception, message:
            print "Error in saveTorrentStore, open:", message
            pass
            
        try:
            cPickle.dump(BTTorrent.Torrent_store, torrent_file)
        except Exception, message:
            print "Error in saveTorrentStore, dump:", message
            pass

        torrent_file.close()
        
    saveTorrentStore = staticmethod(saveTorrentStore)


class BTFriend:
    """ This class presents a friend of you. You trusts him/her and can upload or 
    download his/her files.
    """
    
    def __init__(self, id_type, id):
        self.id_type = id_type
        self.id = id
        self.your_trust = 8.0
        self.general_trust = 8.0
        self.buddy = None
        
    Friend_swarm = {}
    
    def getBuddy(self):
        if BTBuddy.Buddy_swarm.has_key(self.id):
            return BTBuddy.Buddy_swarm[self.id]
        else:
            pass    # error!
        
        
if __name__ == '__main__':
    class ABCTorrent:
        def __init__(self, id):
            self.id = id
            self.peer_swarm = {}
            self.filename = str(id)
            
    BTBuddy.loadBuddySwarm()
            
    if not BTBuddy.Buddy_swarm:
        for i in range(30):
            num_ip = 7
            num_torrent = 23
            bt = ABCTorrent(i % num_torrent)
            bt_info = {'ip':str(i % num_ip)}
            peer = BTPeer(bt_info, bt)
    #    print Buddy_swarm
    for buddy_id in BTBuddy.Buddy_swarm:
        print BTBuddy.Buddy_swarm[buddy_id].id, BTBuddy.Buddy_swarm[buddy_id].torrents.keys()
        
    BTBuddy.saveBuddySwarm()
    
