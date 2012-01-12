# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import urlparse
import binascii
from traceback import print_exc,print_stack

from Tribler.Core.Base import *
from Tribler.Core.simpledefs import *

class SwiftDef(ContentDefinition):
    """ Definition of a swift swarm, that is, the root hash (video-on-demand) 
    and any optional peer-address sources. """
    
    def __init__(self,roothash,tracker=None,duration=None):
        self.roothash = roothash
        self.tracker = tracker
        self.duration = duration
    
    def load_from_url(url):
        """
        If the URL starts with the swift URL scheme, we convert the URL to a 
        SwiftDef.
        
        Scheme: tswift://tracker/roothash-as-hex
                tswift://tracker/roothash-as-hex@duration-in-secs
        
        @param url URL
        @return SwiftDef.
        """
        # Class method, no locking required
        p = urlparse.urlparse(url)
        roothash = binascii.unhexlify(p.path[1:41])
        tracker = "http://"+p.netloc
        if '@' in p.path:
            duration = int(p.path[42:])
        else:
            duration = None
        
        s = SwiftDef(roothash,tracker,duration)
        return s
    load_from_url = staticmethod(load_from_url)


    def is_swift_url(url):
        return isinstance(url, str) and url.startswith(SWIFT_URL_SCHEME)
    is_swift_url = staticmethod(is_swift_url)


    #
    # ContentDefinition interface
    #
    def get_def_type(self):
        """ Returns the type of this Definition
        @return string
        """
        return "swift"

    def get_name(self):
        """ Returns the user-friendly name of this Definition
        @return string
        """
        return self.get_roothash_as_hex()

    def get_live(self):
        """ Whether swift swarm is a live stream 
        @return Boolean
        """
        return False

    #
    # Swift specific
    #
    def get_roothash(self):
        """ Returns the roothash of the swift swarm.
        @return A string of length 20. """
        return self.roothash

    def get_roothash_as_hex(self):
        """ Returns the roothash of the swift swarm.
        @return A string of length 40, of 20 concatenated 2-char hex bytes. """

        return binascii.hexlify(self.roothash)
    
    def set_tracker(self,url):
        """ Sets the tracker  
        @param url The tracker URL.
        """
        self.tracker = url
        
    def get_tracker(self):
        """ Returns the tracker URL.
        @return URL """
        return self.tracker

    def get_url(self):
        """ Return the basic URL representation of this SwiftDef.
        @return URL
        """
        p = urlparse.urlparse(self.tracker)
        return SWIFT_URL_SCHEME+'://'+p.netloc+'/'+binascii.hexlify(self.roothash)
      
    def get_url_with_meta(self):
        """ Return the URL representation of this SwiftDef with extra 
        metadata, e.g. duration.
        @return URL
        """
        url = self.get_url()
        if self.duration is not None:
            url += '@'+str(self.duration)
        return url
            
    def get_duration(self):
        """ Return the (optional) duration of this SwiftDef or None
        @return a number of seconds
        """  
        return self.duration
        