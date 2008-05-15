# Written by Arno Bakker
# see LICENSE.txt for license information

import sys

from Tribler.Core.simpledefs import *
from Tribler.Core.Overlay.permid import generate_keypair,read_keypair,save_keypair 

class LiveSourceAuthConfig:
    """ Base class for configuring authentication methods for data from the
    source in live streaming.
    """
    def __init__(self,authmethod):
        self.authmethod = authmethod
        
    def get_method(self):
        return self.authmethod
    
    
class ECDSALiveSourceAuthConfig(LiveSourceAuthConfig):
    """ Class for configuring the ECDSA authentication method for data from the
    source in live streaming. The ECDSA method adds a ECDSA signature to each
    piece that is generated.
    """
    def __init__(self,keypair=None):
        """ Constructor for LIVE_AUTHMETHOD_ECDSA authentication of the 
        live source. If no keypair is specified, one is generated.
        
        @param keypair  (Optional) An M2Crypto.EC keypair.
        """
        LiveSourceAuthConfig.__init__(self,LIVE_AUTHMETHOD_ECDSA)
        if keypair is None:
            self.keypair = generate_keypair()
        else:
            self.keypair = keypair

    def get_pubkey(self):
        return self.keypair.pub().get_der()
    
    def get_keypair(self):
        return self.keypair
    
    #
    # Class method
    #
    def load(filename):
        """
        Load a saved ECDSALiveSourceAuthConfig from disk.
        
        @param filename  An absolute Unicode filename
        @return ECDSALiveSourceAuthConfig object
        """
        keypair = read_keypair(filename)
        return ECDSALiveSourceAuthConfig(keypair)
    load = staticmethod(load)

    def save(self,filename):
        """ Save the ECDSALiveSourceAuthConfig to disk.
        @param filename  An absolute Unicode filename
        """
        save_keypair(self.keypair,filename)
    