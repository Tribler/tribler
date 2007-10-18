# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import time
import copy
import sha
import socket
from UserDict import DictMixin
from threading import RLock,Condition,Event,Thread
from traceback import print_exc,print_stack
from BitTornado.natpunch import UPnPWrapper, UPnPError

DEBUG = False


class UPnPThread(Thread):
    """ Thread to run the UPnP code. Moved out of main startup-
        sequence for performance. As you can see this thread won't
        exit until the client exits. This is due to a funky problem
        with UPnP mode 2. That uses Win32/COM API calls to find and
        talk to the UPnP-enabled firewall. This mechanism apparently
        requires all calls to be carried out by the same thread.
        This means we cannot let the final DeletePortMapping(port) 
        (==UPnPWrapper.close(port)) be done by a different thread,
        and we have to make this one wait until client shutdown.

        Arno, 2006-11-12
    """

    def __init__(self,upnp_type,ext_ip,listen_port,error_func,got_ext_ip_func):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName( "UPnP"+self.getName() )
        
        self.upnp_type = upnp_type
        self.locally_guessed_ext_ip = ext_ip
        self.listen_port = listen_port
        self.error_func = error_func
        self.got_ext_ip_func = got_ext_ip_func 
        self.shutdownevent = Event()

    def run(self):
        if self.upnp_type > 0:
            self.upnp_wrap = UPnPWrapper.getInstance()
            self.upnp_wrap.register(self.locally_guessed_ext_ip)

            if self.upnp_wrap.test(self.upnp_type):
                try:
                    shownerror=False
                    # Get external IP address from firewall
                    if self.upnp_type != 1: # Mode 1 doesn't support getting the IP address"
                        ret = self.upnp_wrap.get_ext_ip()
                        if ret == None:
                            shownerror=True
                            self.error_func(self.upnp_type,self.listen_port,0)
                        else:
                            self.got_ext_ip_func(ret)

                    # Do open_port irrespective of whether get_ext_ip()
                    # succeeds, UPnP mode 1 doesn't support get_ext_ip()
                    # get_ext_ip() must be done first to ensure we have the 
                    # right IP ASAP.
                    
                    # Open TCP listen port on firewall
                    ret = self.upnp_wrap.open(self.listen_port,iproto='TCP')
                    if ret == False and not shownerror:
                        self.error_func(self.upnp_type,self.listen_port,0)

                    # Open UDP listen port on firewall
                    ret = self.upnp_wrap.open(self.listen_port,iproto='UDP')
                    if ret == False and not shownerror:
                        self.error_func(self.upnp_type,self.listen_port,0,listenproto='UDP')
                
                except UPnPError,e:
                    self.error_func(self.upnp_type,self.listen_port,1,e)
            else:
                if self.upnp_type != 3:
                    self.error_func(self.upnp_type,self.listen_port,2)
                elif DEBUG:
                    print >>sys.stderr,"upnp: thread: Initialization failed, but didn't report error because UPnP mode 3 is now enabled by default"

        # Now that the firewall is hopefully open, activate other services
        # here. For Buddycast we don't have an explicit notification that it
        # can go ahead. It will start 15 seconds after client startup, which
        # is assumed to be sufficient for UPnP to open the firewall.
        ## dmh.start_active()

        if self.upnp_type > 0:
            if DEBUG:
                print >>sys.stderr,"upnp: thread: Waiting till shutdown"
            self.shutdownevent.wait()
            # Don't write to sys.stderr, that sometimes doesn't seem to exist
            # any more?! Python garbage collection funkiness of module sys import?
            # The GUI is definitely gone, so don't use self.error_func()
            if DEBUG:
                print "upnp: thread: Shutting down, closing port on firewall"
            try:
                self.upnp_wrap.close(self.listen_port,iproto='TCP')
                self.upnp_wrap.close(self.listen_port,iproto='UDP')
            except Exception,e:
                print "upnp: thread: close port at shutdown threw",e
                print_exc()

        # End of UPnPThread

    def shutdown(self):
        self.shutdownevent.set()
