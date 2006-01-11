from socket import inet_aton 
from base64 import encodestring, decodestring
import sys

superpeer_file = 'superpeer.txt'

class SuperPeer:
    def __init__(self):
        self.superpeers = SuperPeerTable.getInstance()
        pre_superpeers = self.readSuperPeer(superpeer_file)
        for peer in pre_superpeers:
            self.superpeers.addSuperPeerByPeer(peer)
        self.superpeers_list = []
        self.updateSuperPeers()

    def readSuperPeer(self, filename):
        """ read (superpeer_ip, superpeer_port) lines from a text file """
        
        try:
            file = open(filename, "r")
        except IOError:
            print >> sys.stderr, "File " + filename + " could not be opened"
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
            inet_aton(ip)
            permid = superpeer[2]
            if len(permid) != 148:
                return False
        except:
            return False
        return True    
    
    def getSuperPeers(self):
        return self.superpeers.getSuperPeers()

    def updateSuperPeers(self):
        #TODO: select new superpeers
        self.superpeer_list = self.getSuperPeers()

if __name__=='__main__':
    superpeer_file = '../' + superpeer_file
    sp = SuperPeer()
    print sp.superpeer_list
    
