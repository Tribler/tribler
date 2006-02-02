from time import time
import os

from Tribler.utilities import validIP, validPort, validPermid, validName
from CacheDBHandler import FriendDBHandler

friend_file = 'friends.txt'

DEBUG = False

def init():
    print "secover: Update FriendList"
    FriendList().updateFriendList()

class FriendList:
    def __init__(self, friend_file=friend_file, db_dir=''):
        self.friend_file = friend_file
        self.db_dir = db_dir
        self.friend_db = FriendDBHandler(db_dir=self.db_dir)
        
    def clear(self):    # clean database
        if hasattr(self, 'friend_db'):
            self.friend_db.clear()
        
    def clean(self):    # delete friend file
        try:
            os.remove(self.friend_file)
        except Exception, msg:
            pass

    def updateFriendList(self, friend_file=''):
        if not friend_file:
            friend_file = self.friend_file
        self.friend_list = self.readFriendList(friend_file)
        self.updateDB(self.friend_list)
        self.clean()
        
    def updateDB(self, friend_list):
        if not friend_list:
            return
        for friend in friend_list:
            self.friend_db.addExternalFriend(friend)

    def getFriends(self):
        return self.friend_db.getFriends()
    
    def readFriendList(self, filename=''):
        """ read (name, permid, friend_ip, friend_port) lines from a text file """
        
        if not filename:
            filename = self.friend_file
        try:
            file = open(filename, "r")
        except IOError:
            return []
            
        friends = file.readlines()
        file.close()
        friends_info = []
        for friend in friends:
            if friend.strip().startswith("#"):    # skip commended lines
                continue
            friend_line = friend.split(',')
            friend_info = []
            for i in range(len(friend_line)):
                friend_info.append(friend_line[i].strip())
            if self.validFriendList(friend_info):
                friend = {'name':friend_info[0], 'permid':friend_info[1], 
                          'ip':friend_info[2], 'port':int(friend_info[3])}
#                if len(friend_info) > 4:
#                    last_seen = int(friend_info[4])
#                    if last_seen < 0:
#                        last_seen = 0
#                    if last_seen > time():
#                        last_seen = int(time())
#                else:
#                    last_seen = 0
#                friend['last_seen'] = last_seen
                friends_info.append(friend)
        return friends_info
    
    def validFriendList(self, friend_info):
        try:
            if len(friend_info) < 4:
                raise RuntimeError, "one line in friends.txt can only contain at least 4 elements"
            validName(friend_info[0])
            validPermid(friend_info[1])
            validIP(friend_info[2])
            validPort(int(friend_info[3]))
        except Exception, msg:
            if DEBUG:
                print "======== reading friend list error ========"
                print friend_info
                print msg
                print "==========================================="
            return False
        else:
            return True
    
    def getFriends(self):
        return self.friend_db.getFriends()
        

