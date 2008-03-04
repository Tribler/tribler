# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
from time import time
from traceback import print_exc

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.CacheDB.MugshotManager import ICON_MAX_SIZE
from Tribler.Core.Utilities.utilities import *

DEBUG = True

MIN_OVERLAP_WAIT = 12.0*3600.0 # half a day in seconds

class OverlapMsgHandler:
    
    def __init__(self):
        
        self.recentpeers = {}

    def register(self, overlay_bridge, launchmany):
        if DEBUG:
            print >> sys.stderr,"socnet: bootstrap: overlap"
        self.mypermid = launchmany.session.get_permid()
        self.session = launchmany.session
        self.peer_db = launchmany.peer_db 
        self.superpeer_db = launchmany.superpeer_db
        self.overlay_bridge = overlay_bridge

    #
    # Incoming SOCIAL_OVERLAP
    # 
    def recv_overlap(self,permid,message,selversion):
        # 1. Check syntax
        try:
            oldict = bdecode(message[1:])
        except:
            print_exc()
            if DEBUG:
                print >> sys.stderr,"socnet: SOCIAL_OVERLAP: error becoding"
            return False

        if not isValidDict(oldict,permid):
            return False

        # 2. Process
        self.process_overlap(permid,oldict)
        return True

    def process_overlap(self,permid,oldict):
        #self.print_hashdict(oldict['hashnetwork'])

        # 1. Clean recently contacted admin
        self.clean_recentpeers()

        # 3. Save persinfo + hrwidinfo + ipinfo
        if self.peer_db.hasPeer(permid):
            save_ssocnet_peer(self,permid,oldict,False,False,False)
        elif DEBUG:
            print >> sys.stderr,"socnet: overlap: peer unknown?! Weird, we just established connection"

        # 6. Reply
        if not (permid in self.recentpeers.keys()):
            self.recentpeers[permid] = time()
            self.reply_to_overlap(permid)

    def clean_recentpeers(self):
        newdict = {}
        for permid2,t in self.recentpeers.iteritems():
            if (t+MIN_OVERLAP_WAIT) > time():
                newdict[permid2] = t
            #elif DEBUG:
            #    print >> sys.stderr,"socnet: overlap: clean recent: not keeping",show_permid_short(permid2)
                
        self.recentpeers = newdict

    def reply_to_overlap(self,permid):
        oldict = self.create_oldict()
        self.send_overlap(permid,oldict)

    #
    # At overlay-connection establishment time.
    #
    def initiate_overlap(self,permid,locally_initiated):
        self.clean_recentpeers()
        if not (permid in self.recentpeers.keys() or permid in self.superpeer_db.getSuperPeers()):
            if locally_initiated:
                # Make sure only one sends it
                self.recentpeers[permid] = time()
                self.reply_to_overlap(permid)
            elif DEBUG:
                print >> sys.stderr,"socnet: overlap: active: he should initiate"
        elif DEBUG:
            print >> sys.stderr,"socnet: overlap: active: peer recently contacted already"

    #
    # General
    #
    def create_oldict(self):
        """
        Send:
        * Personal info: name, picture, rwidhashes
        * IP info: IP + port
        Both are individually signed by us so dest can safely 
        propagate. We distinguish between what a peer said
        is his IP+port and the information obtained from the network
        or from other peers (i.e. BUDDYCAST)
        """
        
        persinfo = {'name':self.session.get_nickname()}
        
        # See if we can find icon using PermID:
        [type,data] = self.peer_db.getPeerIcon(self.mypermid)
        if not type is None and not data is None:
            persinfo['icontype'] = type
            persinfo['icondata'] = str(data)
        
        oldict = {}
        oldict['persinfo'] = persinfo

        #if DEBUG:
        #    print >> sys.stderr,"socnet: overlap: active: sending hashdict"
        #    self.print_hashdict(oldict['hashnetwork'])

        return oldict


    def send_overlap(self,permid,oldict):
        try:
            body = bencode(oldict)
            ## Optimization: we know we're currently connected
            self.overlay_bridge.send(permid, SOCIAL_OVERLAP + body,self.send_callback)
        except:
            if DEBUG:
                print_exc(file=sys.stderr)
            pass

    
    def send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"socnet: SOCIAL_OVERLAP: error sending to",show_permid_short(permid),exc
            pass

    #
    # Internal methods
    #


def isValidDict(oldict,source_permid):
    if not isinstance(oldict, dict):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_OVERLAP: not a dict"
        return False
    k = oldict.keys()        

    if DEBUG:
        print >> sys.stderr,"socnet: SOCIAL_OVERLAP: keys",k

    if not ('persinfo' in k) or not isValidPersinfo(oldict['persinfo'],False):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_OVERLAP: key 'persinfo' missing or value wrong type in dict"
        return False

    for key in k:
        if key not in ['persinfo']:
            if DEBUG:
                print >> sys.stderr,"socnet: SOCIAL_OVERLAP: unknown key",key,"in dict"
            return False

    return True



def isValidPersinfo(persinfo,signed):
    if not isinstance(persinfo,dict):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_*: persinfo: not a dict"
        return False

    k = persinfo.keys()
    #print >> sys.stderr,"socnet: SOCIAL_*: persinfo: keys are",k
    if not ('name' in k) or not isinstance(persinfo['name'],str):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_*: persinfo: key 'name' missing or value wrong type"
        return False

    if 'icontype' in k and not isValidIconType(persinfo['icontype']):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_*: persinfo: key 'icontype' value wrong type"
        return False

    if 'icondata' in k and not isValidIconData(persinfo['icondata']):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_*: persinfo: key 'icondata' value wrong type"
        return False

    if ('icontype' in k and not ('icondata' in k)) or ('icondata' in k and not ('icontype' in k)):
        if DEBUG:
            print >> sys.stderr,"socnet: SOCIAL_*: persinfo: key 'icontype' without 'icondata' or vice versa"
        return False

    if signed:
        if not ('insert_time' in k) or not isinstance(persinfo['insert_time'],int):
            if DEBUG:
                print >> sys.stderr,"socnet: SOCIAL_*: persinfo: key 'insert_time' missing or value wrong type"
            return False

    for key in k:
        if key not in ['name','icontype','icondata','insert_time']:
            if DEBUG:
                print >> sys.stderr,"socnet: SOCIAL_*: persinfo: unknown key",key,"in dict"
            return False

    return True


def isValidIconType(type):
    """ MIME-type := type "/" subtype ... """
    if not isinstance(type,str):
        return False
    idx = type.find('/')
    ridx = type.rfind('/')
    return idx != -1 and idx == ridx

def isValidIconData(data):
    if not isinstance(data,str):
        return False
    
#    if DEBUG:
#        print >>sys.stderr,"socnet: SOCIAL_*: persinfo: IconData length is",len(data)
    
    return len(data) <= ICON_MAX_SIZE



def save_ssocnet_peer(self,permid,record,persinfo_ignore,hrwidinfo_ignore,ipinfo_ignore):
    """ This function is used by both BootstrapMsgHandler and 
        OverlapMsgHandler, and uses their database pointers. Hence the self 
        parameter. persinfo_ignore and ipinfo_ignore are booleans that
        indicate whether to ignore the personal info, resp. ip info in
        this record, because they were unsigned in the message and
        we already received signed versions before.
    """
    if permid == self.mypermid:
        return
    
    # 1. Save persinfo
    if not persinfo_ignore:
        persinfo = record['persinfo']
        
        if DEBUG:
            print >>sys.stderr,"socnet: Got persinfo",persinfo.keys()
            if len(persinfo.keys()) > 1:
                 print >>sys.stderr,"socnet: Got persinfo THUMB THUMB THUMB THUMB"
        
        if self.peer_db.hasPeer(permid):
            self.peer_db.updatePeer(permid, name=persinfo['name'])
        else:
            self.peer_db.addPeer(permid,{'name':persinfo['name']})
    
        # b. Save icon
        if 'icontype' in persinfo and 'icondata' in persinfo: 
            if DEBUG:
                print >> sys.stderr,"socnet: saving icon for",show_permid_short(permid)
            self.peer_db.updatePeerIcon(permid, persinfo['icontype'],persinfo['icondata'])    
