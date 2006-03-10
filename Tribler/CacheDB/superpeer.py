# Written by Jie Yang
# see LICENSE.txt for license information

from time import time
import os, sys
import base64

from Tribler.utilities import validIP, validPort, validPermid, validName
from CacheDBHandler import SuperPeerDBHandler

superpeer_file = 'superpeer.txt'

DEBUG = False

def init(install_dir = None):
    ## FIXME
    filename = make_filename(install_dir, superpeer_file)
    SuperPeerList().updateSuperPeerList(filename)
    
def make_filename(install_dir,filename):
    if install_dir is None or not isinstance(install_dir, str):
        return filename
    else:
        return os.path.join(install_dir,filename)    

class SuperPeerList:
    def __init__(self, superpeer_file=superpeer_file, db_dir=''):
        self.superpeer_file = superpeer_file
        self.db_dir = db_dir
        self.superpeer_db = SuperPeerDBHandler(db_dir=self.db_dir)
        
    def clear(self):    # clean database
        if hasattr(self, 'superpeer_db'):
            self.superpeer_db.clear()
        
    def updateSuperPeerList(self, superpeer_file=''):
        if not superpeer_file:
            superpeer_file = self.superpeer_file
        self.superpeer_list = self.readSuperPeerList(superpeer_file)
        self.updateDB(self.superpeer_list)
        
    def updateDB(self, superpeer_list):
        if not superpeer_list:
            return
        for superpeer in superpeer_list:
            self.superpeer_db.addExternalSuperPeer(superpeer)

    def getSuperPeers(self):
        return self.superpeer_db.getSuperPeers()
    
    def readSuperPeerList(self, filename=''):
        """ read (name, permid, superpeer_ip, superpeer_port) lines from a text file """
        
        if not filename:
            filename = self.superpeer_file
        try:
            filepath = os.path.abspath(filename)
            file = open(filepath, "r")
        except IOError:
            print >> sys.stderr, "cannot open superpeer file", filepath
            return []
            
        superpeers = file.readlines()
        file.close()
        superpeers_info = []
        for superpeer in superpeers:
            if superpeer.strip().startswith("#"):    # skip commended lines
                continue
            superpeer_line = superpeer.split(',')
            superpeer_info = []
            for i in range(len(superpeer_line)):
                superpeer_info.append(superpeer_line[i].strip())
            try:
                superpeer_info[2] = base64.decodestring( superpeer_info[2]+'\n' )
            except:
                continue
            if self.validSuperPeerList(superpeer_info):
                superpeer = {'ip':superpeer_info[0], 'port':superpeer_info[1], 
                          'permid':superpeer_info[2]}
                if len(superpeer_info) > 3:
                    superpeer['name'] = superpeer_info[3]
                superpeers_info.append(superpeer)
        return superpeers_info
    
    def validSuperPeerList(self, superpeer_info):
        try:
            if len(superpeer_info) < 3:
                raise RuntimeError, "one line in superpeers.txt contains at least 3 elements"
            #validIP(superpeer_info[0])
            validPort(int(superpeer_info[1]))
            validPermid(superpeer_info[2])
        except Exception, msg:
            if DEBUG:
                print "======== reading superpeer list error ========"
                print superpeer_info
                print msg
                print "==========================================="
            return False
        else:
            return True
    

    
