# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import urlparse
import binascii
import random
import time
from traceback import print_exc,print_stack

from Tribler.Core.Swift.SwiftProcess import *
from Tribler.Utilities.Instance2Instance import *


DEBUG = False

class SwiftProcessMgr(InstanceConnectionHandler):
    """ Class that manages a number of SwiftProcesses """

    def __init__(self,binpath,i2iport,dlsperproc,sesslock):
        self.binpath = binpath
        self.i2iport = i2iport
        # ARNOSMPTODO: Implement such that a new proc is created when needed
        self.dlsperproc = dlsperproc
        self.sesslock = sesslock
        self.done = False
        
        self.sps = []

        InstanceConnectionHandler.__init__(self,None)

        # Start server for cmd socket communication to swift processes
        self.i2is = Instance2InstanceServer(self.i2iport,self,timeout=(24.0*3600.0)) 
        self.i2is.start()

    def get_or_create_sp(self,workdir,zerostatedir,listenport,httpgwport,cmdgwport):
        """ Download needs a process """
        self.sesslock.acquire()
        print >>sys.stderr,"spm: get_or_create_sp"
        try:
            if self.done:
                return None
            
            sp = None
            if listenport is not None:
                # Reuse the one with the same requested listen port
                for sp2 in self.sps:
                    if sp2.listenport == listenport:
                        sp = sp2
                        print >>sys.stderr,"spm: get_or_create_sp: Reusing",sp.get_pid()
                        break
            elif self.dlsperproc > 1:
                # Find one with room, distribute equally
                random.shuffle(self.sps)
                for sp2 in self.sps:
                    if len(sp2.get_downloads()) < self.dlsperproc:
                        sp = sp2
                        print >>sys.stderr,"spm: get_or_create_sp: Reusing",sp.get_pid() 
                        break
                    
            if sp is None:
                # Create new process
                sp = SwiftProcess(self.binpath,workdir,zerostatedir,listenport,httpgwport,cmdgwport,self)
                print >>sys.stderr,"spm: get_or_create_sp: Creating new",sp.get_pid()
                self.sps.append(sp)
            
                # Arno, 2011-10-13: On Linux swift is slow to start and
                # allocate the cmd listen socket?!
                if sys.platform == "linux2":
                    print >>sys.stderr,"spm: Need to sleep 1 second for swift to start on Linux?! FIXME"
                    time.sleep(1)
                
                sp.start_cmd_connection()
                
            return sp
        finally:
            self.sesslock.release()
        
    def release_sp(self,sp):
        """ Download no longer needs process. Apply process-cleanup policy """
        # ARNOSMPTODO: MULTIPLE: Add policy param on whether to keep process around when no downloads. 
        self.sesslock.acquire()
        try:
            if len(sp.get_downloads()) == 0:
                self.destroy_sp(sp)
        finally:
            self.sesslock.release()
        
        
    def destroy_sp(self,sp):
        print >>sys.stderr,"spm: destroy_sp:",sp.get_pid()
        self.sesslock.acquire()
        try:
            self.sps.remove(sp)
            sp.early_shutdown()
            # Don't need gracetime, no downloads left.
            sp.network_shutdown()
        finally:
            self.sesslock.release()

    def early_shutdown(self):
        """ First phase of two phase shutdown. network_shutdown is called after
        gracetime (see Session.shutdown()).
        """
        # Called by any thread, assume sessionlock is held
        print >>sys.stderr,"spm: early_shutdown"
        self.done = False
        self.i2is.shutdown() # Calls self.shutdown() indirectly

    def shutdown(self): # InstanceConnectionHandler
        """ Gets called when i2is.shutdown is called. Do not call directly """
        for sp in self.sps:
            try:
                sp.early_shutdown()
            except:
                print_exc()
            
    def network_shutdown(self):
        """ Gracetime expired, kill procs """
        # Called by network thread
        for sp in self.sps:
            try:
                sp.network_shutdown()
            except:
                print_exc()

