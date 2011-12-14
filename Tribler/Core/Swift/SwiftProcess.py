# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import subprocess
import random
import time
import binascii
from threading import RLock
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Utilities.Instance2Instance import *

DEBUG = True

DONE_STATE_WORKING = 0
DONE_STATE_EARLY_SHUTDOWN = 1
DONE_STATE_SHUTDOWN = 2

class SwiftProcess(InstanceConnection):
    """ Representation of an operating-system process running the C++ swift engine.
    A swift engine can participate in one or more swarms."""


    def __init__(self,binpath,destdir,connhandler):
        # Called by any thread, assume sessionlock is held
        self.splock = RLock()
        self.binpath = binpath
        self.destdir = destdir
        InstanceConnection.__init__(self, None, connhandler, self.i2ithread_readlinecallback)
        
        self.cmdport = random.randint(11001,11999)  # NSSA control socket
        self.httpport = random.randint(12001,12999) # content web server
        
        # Security: only accept commands from localhost, enable HTTP gw, 
        # no stats/webUI web server
        args=[]
        args.append(str(self.binpath))
        args.append("-c") # command port
        args.append("127.0.0.1:"+str(self.cmdport))
        args.append("-g") # HTTP gateway port
        args.append("127.0.0.1:"+str(self.httpport))
        args.append("-o")
        args.append(str(destdir))
        args.append("-w")
        # args.append("-B") # DEBUG Hack        
        
        if DEBUG:
            print >>sys.stderr,"SwiftProcess: __init__: Running",args
        
        self.popen = subprocess.Popen(args,close_fds=True,cwd=destdir) 

        self.roothash2dl = {}
        self.donestate = DONE_STATE_WORKING  # shutting down

    #
    # Instance2Instance
    #   
    def start_cmd_connection(self):
        # Called by any thread, assume sessionlock is held
        self.singsock = self.connhandler.start_connection(("127.0.0.1", self.cmdport),self)
        
    def i2ithread_readlinecallback(self,ic,cmd):
        #print >>sys.stderr,"sp: Got command #"+cmd+"#"
        words = cmd.split()
        roothash = binascii.unhexlify(words[1])
        
        self.splock.acquire()
        try:
            d = self.roothash2dl[roothash]
        except:
            print "GOT", words
            print "HAVE", [key.encode("HEX") for key in self.roothash2dl.keys()]
            raise
        finally:
            self.splock.release()
        
        # Hide NSSA interface for SwiftDownloadImpl
        if words[0] == "INFO": # INFO HASH status dl/total
            dlstatus = int(words[2])
            pargs = words[3].split("/")
            dynasize = int(pargs[1])
            if dynasize == 0:
                progress = 0.0
            else:
                progress = float(pargs[0])/float(pargs[1])
            dlspeed = float(words[4])
            ulspeed = float(words[5])
            numleech = int(words[6])
            numseeds = int(words[7])
            d.i2ithread_info_callback(dlstatus,progress,dynasize,dlspeed,ulspeed,numleech,numseeds)
        elif words[0] == "PLAY":
            httpurl = words[2]
            d.i2ithread_vod_event_callback(VODEVENT_START,httpurl)


    #
    # Swift Mgmt interface
    #
    def start_download(self,d):
        self.splock.acquire()
        try:
            roothash = d.get_def().get_roothash()
            roothash_hex = d.get_def().get_roothash_as_hex()

            # Before send to handle INFO msgs
            self.roothash2dl[roothash] = d
            url = d.get_def().get_url()
            
            # Default is unlimited, so don't send MAXSPEED then
            maxdlspeed=d.get_max_speed(DOWNLOAD)
            if maxdlspeed == 0:
                maxdlspeed = None
            maxulspeed=d.get_max_speed(UPLOAD)
            if maxulspeed == 0:
                maxulspeed = None
                
            self.send_start(url,roothash_hex=roothash_hex,maxdlspeed=maxdlspeed,maxulspeed=maxulspeed)

        finally:
            self.splock.release()

        
    def remove_download(self,d,removestate,removecontent):
        self.splock.acquire()
        try:
            roothash_hex = d.get_def().get_roothash_as_hex()
            
            self.send_remove(roothash_hex,removestate,removecontent)
    
            # After send to handle INFO msgs
            roothash = d.get_def().get_roothash()

            del self.roothash2dl[roothash] 
        finally:
            self.splock.release()

    def get_downloads(self):
        self.splock.acquire()
        try:
            return self.roothash2dl.values() 
        finally:
            self.splock.release()


    def get_pid(self):
        if self.popen is not None:
            return self.popen.pid
        else:
            return -1

    def set_max_speed(self,d,direct,speed):
        self.splock.acquire()
        try:
            roothash_hex = d.get_def().get_roothash_as_hex()
            
            self.send_max_speed(roothash_hex,direct,speed)
        finally:
            self.splock.release()


    def checkpoint_download(self,d):
        self.splock.acquire()
        try:
            roothash_hex = d.get_def().get_roothash_as_hex()
            self.send_checkpoint(roothash_hex)
        finally:
            self.splock.release()


    def early_shutdown(self):
        # Called by any thread, assume sessionlock is held
        # May get called twice, once by spm.release_sp() and spm.shutdown()
        if self.donestate == DONE_STATE_WORKING:
            self.donestate = DONE_STATE_EARLY_SHUTDOWN
        else:
            return
        
        if self.popen is not None:
            # Tell engine to shutdown so it can deregister dls from tracker
            print >>sys.stderr,"sp: Telling process to shutdown"
            self.send_shutdown()
                

    def network_shutdown(self):
        # Called by network thread, assume sessionlock is held
        if self.donestate == DONE_STATE_EARLY_SHUTDOWN:
            self.donestate = DONE_STATE_SHUTDOWN
        else:
            return

        if self.popen is not None:
            try:
                print >>sys.stderr,"sp: Terminating process"
                self.popen.terminate()
                self.popen.wait()
                self.popen = None
            except:
                print_exc()
        # self.singsock auto closed by killing proc.
    
    #
    # Internal methods
    #
    def send_start(self,url,roothash_hex=None,maxdlspeed=None,maxulspeed=None):
        # assume splock is held to avoid concurrency on socket
        print >>sys.stderr,"sp: send_start:",url
        
        cmd = 'START '+url+'\r\n'
        if maxdlspeed is not None:
            cmd += 'MAXSPEED '+roothash_hex+' DOWNLOAD '+str(float(maxdlspeed))+'\r\n'
        if maxulspeed is not None:
            cmd += 'MAXSPEED '+roothash_hex+' UPLOAD '+str(float(maxulspeed))+'\r\n'
        
        self.singsock.write(cmd)
        
    def send_remove(self,roothash_hex,removestate,removecontent):
        # assume splock is held to avoid concurrency on socket
        self.singsock.write('REMOVE '+roothash_hex+' '+str(int(removestate))+' '+str(int(removecontent))+'\r\n')

    def send_checkpoint(self,roothash_hex):
        # assume splock is held to avoid concurrency on socket
        self.singsock.write('CHECKPOINT '+roothash_hex+'\r\n')


    def send_shutdown(self):
        # assume splock is held to avoid concurrency on socket
        self.singsock.write('SHUTDOWN\r\n')

    def send_max_speed(self,roothash_hex,direct,speed):
        # assume splock is held to avoid concurrency on socket
        print >>sys.stderr,"sp: send_max_speed:",direct,speed
        
        cmd = 'MAXSPEED '+roothash_hex
        if direct == DOWNLOAD:
            cmd += ' DOWNLOAD '
        else:
            cmd += ' UPLOAD '
        cmd += str(float(speed))+'\r\n'
        
        self.singsock.write(cmd)
        
        
