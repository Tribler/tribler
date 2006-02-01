# Written by Jie Yang
# see LICENSE.txt for license information

from socket import inet_aton 
from base64 import decodestring
import sys

#from cachedb import SuperPeerTable
from CacheDBHandler import MyDBHandler

superpeer_file = 'superpeer.txt'
permid_len = 112

class SuperPeer:
    def __init__(self):
        self.superpeers = MyDBHandler()
        pre_superpeers = self.readSuperPeer(superpeer_file)
        for peer in pre_superpeers:
            self.superpeers.addSuperPeerByPeer(peer)
        self.updateSuperPeers()
        self.superpeers.sync()

    def readSuperPeer(self, filename):
        """ read (superpeer_ip, superpeer_port) lines from a text file """
        
        try:
            file = open(filename, "r")
        except IOError:
            print "File " + filename + " could not be opened"
            sys.exit(1)
            
        superpeers = file.readlines()
        superpeers_info = []
        for superpeer in superpeers:
            if superpeer.strip().startswith("#"):    # skip commended lines
                continue
            superpeer_line = superpeer.split(',')
            superpeer_info = []
            sl = len(superpeer_line)
            if sl > 1:
                for i in range(sl):
                    superpeer_info.append(superpeer_line[i].strip())
            if self.validSuperPeer(superpeer_info):
                superpeer = {'ip':superpeer_info[0], 'port':superpeer_info[1], 'permid':decodestring(superpeer_info[2])}
                if len(superpeer_info) > 3:
                    superpeer['name'] = superpeer_info[3]
                superpeers_info.append(superpeer)
        return superpeers_info
    
    def validSuperPeer(self, superpeer):
        if len(superpeer) < 2:
            return False
        ip = superpeer[0]
        try:
            port = int(superpeer[1])
            if port < 1 or port > 65535:
                return False
            permid = superpeer[2]
            if len(permid) != permid_len:
                return False
        except:
            return False
        return True    
    
    def getSuperPeers(self):
        return self.superpeers.getSuperPeers()

    def updateSuperPeers(self):
        #TODO: select new superpeers
        pass
        
        
if __name__=='__main__':
    superpeer_file = '../' + superpeer_file
    sp = SuperPeer()
    print sp.getSuperPeers()
    
