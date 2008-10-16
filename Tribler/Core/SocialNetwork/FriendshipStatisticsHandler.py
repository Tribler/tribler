import sys
import socket
from time import time

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.BitTornado.bencode import bencode, bdecode

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIFTH
from Tribler.Core.SocialNetwork.OverlapMsgHandler import OverlapMsgHandler
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin

from Tribler.Core.Utilities.utilities import show_permid


import wx

DATA = 'FRIENDSHIP_STATISTICS_DATA'
SEND_STATISTICS = 'SEND FRIENDSHIP STATISTICS'
ACKNOWLEDGEMENT = 'ACKNOWLEDGEMENT'
overlay_bridge = None
DEBUG = True

class FriendshipStatisticsHandler:
    __single = None
    
    def __init__(self, utility = None, params = None):
        if FriendshipStatisticsHandler.__single:
            raise RuntimeError, "Friendship Statistics Handler is singleton"
        FriendshipStatisticsHandler.__single = self
               
        
    
    def getInstance(*args, **kw):
        if FriendshipStatisticsHandler.__single is None:
            FriendshipStatisticsHandler(*args, **kw)       
        return FriendshipStatisticsHandler.__single
    getInstance = staticmethod(getInstance)
    
    def register(self, overlay_bridge, launchmany, config):
        if DEBUG:
            print >> sys.stderr, "Friendship Statistics Handler: register"
        self.overlay_bridge = overlay_bridge #instance of overlay bridge to communicate to peers
        self.config = config
        self.lm = launchmany
        
        self.mypermid = self.lm.session.get_permid()
        self.myip = self.lm.get_ext_ip()
        self.myport = self.lm.session.get_listen_port()
        self.mynickname = self.lm.session.get_nickname()
        
        
        self.superpeer_list = self.lm.superpeer_db.getSuperPeers()
        self.friendshipStatistics_db = self.lm.friendship_statistics_db.getInstance()
        
    #
    # Incoming connections
    #
    def handleConnection(self, exc, permid, selversion, locally_initiated):
        
        if DEBUG:
            print >> sys.stderr, "FRIENDSHIP STATISTICS: handleConnection", exc, "v", selversion, "local", locally_initiated
        if exc is not None:
            return
        
        if selversion < OLPROTO_VER_FIFTH:
            return True

        if self.config['superpeer']:
            if DEBUG:
                print >> sys.stderr, "FRIENDSHIP STATISTICS: overlap: Ignoring connection, we are superpeer"
            return True
        
        if not (permid in self.superpeer_list):
            # connect to that peer, and asks for her friendship data
            self.overlay_bridge.connect(permid, self.friendshipStatisticsConnectionEstablishedCallBack)
             
             
        
        
#        self.overlay_bridge.initiate_overlap(permid, locally_initiated)
#        return True  

    #
    # Incoming messages
    # 
    def friendshipStatisticsConnectionEstablishedCallBack(self, exc, dns, target_permid, selversion):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr, 'FRIENDSHIP STATISTICS: Could not connect to peer: ' + target_permid  
                print >> sys.stderr, exc
        
        msg_dict = {'message type':SEND_STATISTICS,
                'current time':int(time())}
        msg = bencode(msg_dict)
        self.overlay_bridge.send(target_permid, FRIENDSHIP_STATISTICS + msg, self.friendshipStatisticsMessageSendCallBack)
    
    def friendshipStatisticsMessageSendCallBack(self, exc, target_permid, other=0):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr, 'FRIENDSHIP STATISTICS: Could not send friend statistics message to peer: ' + target_permid  
                print >> sys.stderr, exc
        
        
    #
    # Incoming messages
    # 
    def handleMessage(self, permid, selversion, message):
        """ Handle incoming Friend Statistics, and their response"""
        
        
        
        if message[0] == FRIENDSHIP_STATISTICS:
            friendshipStatistics_data = bdecode(message[1:])
            if friendshipStatistics_data['message type'] == DATA:
                self.saveFriendshipStatistics(friend_data['current time'], friendshipStatistics_data[2:])
                
                msg_dict = {'message type': ACKNOWLEDGEMENT}
                          
                msg = bencode(msg_dict)
                          
                self.overlay_bridge.send(permid, FRIENDSHIP_STATISTICS + msg, self.friendshipStatisticsMessageSendCallBack)

                
            elif friendshipStatistics_data['message type'] == SEND_STATISTICS:
                # Super peer has initiated this stats collection
                if permid in self.superpeer_list:
                    # Fetch all the requests from the database
                    #msg = self.getStaticsFromFriendshipStatisticsTable(self.mypermid)
                    msg_dict = {'message type': DATA,
                          'data':self.getStaticsFromFriendshipStatisticsTable(self.mypermid, friendshipStatistics_data['current time'])}
                    msg = bencode(msg_dict)
                          
                    self.overlay_bridge.send(permid, FRIENDSHIP_STATISTICS + msg, self.friendshipStatisticsMessageSendCallBack)
            elif friendshipStatistics_data['message type'] == ACKNOWLEDGEMENT:
                ## DO NOTHING
                if DEBUG:
                    print >> sys.stdout, 'FRIEND STATISITCS: Friend Statistics data has been successfully received by the super-peer' 
                
                 
            
        
    def getStaticsFromFriendshipStatisticsTable(self, mypermid, last_update_time):
        return self.friendshipStatistics_db.getAllFriendshipStatistics(mypermid, last_update_time)
    
    def saveFriendshipStatistics(self, target_permid, currentTime,  message):
        
        self.friendshipStatistics_db.saveFriendshipStatisticData(message)
        
        
        #self.friendshipStatistics_db.