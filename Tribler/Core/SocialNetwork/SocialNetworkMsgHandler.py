# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information


import sys, socket
from time import time

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIFTH
from Tribler.Core.SocialNetwork.OverlapMsgHandler import OverlapMsgHandler

from Tribler.Core.Utilities.utilities import show_permid_short

DEBUG = False

class SocialNetworkMsgHandler:
    
    __single = None
    
    def __init__(self):
        if SocialNetworkMsgHandler.__single:
            raise RuntimeError, "SocialNetworkMsgHandler is singleton"
        SocialNetworkMsgHandler.__single = self
        self.overlap = OverlapMsgHandler()

    def getInstance(*args, **kw):
        if SocialNetworkMsgHandler.__single is None:
            SocialNetworkMsgHandler(*args, **kw)
        return SocialNetworkMsgHandler.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,overlay_bridge,launchmany,config):
        if DEBUG:
            print >> sys.stderr,"socnet: register"
        self.overlay_bridge = overlay_bridge
        self.config = config
        self.overlap.register(overlay_bridge,launchmany)

    #
    # Incoming messages
    # 
    def handleMessage(self,permid,selversion,message):
        
        t = message[0]
        if t == SOCIAL_OVERLAP:
            if DEBUG:
                print >> sys.stderr,"socnet: Got SOCIAL_OVERLAP",len(message)
            if self.config['superpeer']:
                if DEBUG:
                    print >> sys.stderr,"socnet: overlap: Ignoring, we are superpeer"
                return True
            else:
                return self.overlap.recv_overlap(permid,message,selversion)

        else:
            if DEBUG:
                print >> sys.stderr,"socnet: UNKNOWN OVERLAY MESSAGE", ord(t)
            return False

    #
    # Incoming connections
    #
    def handleConnection(self,exc,permid,selversion,locally_initiated):
        
        if DEBUG:
            print >> sys.stderr,"socnet: handleConnection",exc,"v",selversion,"local",locally_initiated
        if exc is not None:
            return
        
        if selversion < OLPROTO_VER_FIFTH:
            return True

        if self.config['superpeer']:
            if DEBUG:
                print >> sys.stderr,"socnet: overlap: Ignoring connection, we are superpeer"
            return True

        self.overlap.initiate_overlap(permid,locally_initiated)
        return True

    