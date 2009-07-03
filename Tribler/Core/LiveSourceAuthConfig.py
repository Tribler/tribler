# Written by Arno Bakker
# see LICENSE.txt for license information

from Tribler.Core.simpledefs import *
import Tribler.Core.Overlay.permid as permidmod 
from Tribler.Core.Utilities.Crypto import RSA_keypair_to_pub_key_in_der 
from M2Crypto import RSA


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
            self.keypair = permidmod.generate_keypair()
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
        keypair = permidmod.read_keypair(filename)
        return ECDSALiveSourceAuthConfig(keypair)
    load = staticmethod(load)

    def save(self,filename):
        """ Save the ECDSALiveSourceAuthConfig to disk.
        @param filename  An absolute Unicode filename
        """
        permidmod.save_keypair(self.keypair,filename)
    
    
class RSALiveSourceAuthConfig(LiveSourceAuthConfig):
    """ Class for configuring the RSA authentication method for data from the
    source in live streaming. The RSA method adds a RSA signature to each
    piece that is generated.
    """
    def __init__(self,keypair=None):
        """ Constructor for LIVE_AUTHMETHOD_RSA authentication of the 
        live source. If no keypair is specified, one is generated.
        
        @param keypair  (Optional) An M2Crypto.RSA keypair.
        """
        LiveSourceAuthConfig.__init__(self,LIVE_AUTHMETHOD_RSA)
        if keypair is None:
            self.keypair = rsa_generate_keypair()
        else:
            self.keypair = keypair

    def get_pubkey(self):
        return RSA_keypair_to_pub_key_in_der(self.keypair)
    
    def get_keypair(self):
        return self.keypair
    
    #
    # Class method
    #
    def load(filename):
        """
        Load a saved RSALiveSourceAuthConfig from disk.
        
        @param filename  An absolute Unicode filename
        @return RSALiveSourceAuthConfig object
        """
        keypair = rsa_read_keypair(filename)
        return RSALiveSourceAuthConfig(keypair)
    load = staticmethod(load)

    def save(self,filename):
        """ Save the RSALiveSourceAuthConfig to disk.
        @param filename  An absolute Unicode filename
        """
        rsa_write_keypair(self.keypair,filename)
    
    
    
def rsa_generate_keypair():
    """ Create keypair using default params, use __init__(keypair) parameter
    if you want to use custom params.
    """
    # Choose fast exponent e. See Handbook of applied cryptography $8.2.2(ii)
    # And small keysize, attackers have duration of broadcast to reverse 
    # engineer key. 
    e = 3
    keysize = 768
    return RSA.gen_key(keysize,e)
    
def rsa_read_keypair(filename):
    return RSA.load_key(filename)

def rsa_write_keypair(keypair,filename):
    keypair.save_key(filename,cipher=None)
