# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import shutil
import binascii
from threading import Thread,currentThread
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.APIImplementation.ThreadPool import ThreadPool
from Tribler.Core.CacheDB.Notifier import Notifier

DEBUG = False

class UserCallbackHandler:
    
    def __init__(self,session):
        self.session = session
        self.sesslock = session.sesslock
        self.sessconfig = session.sessconfig

        # Notifier for callbacks to API user
        self.threadpool = ThreadPool(2)
        self.notifier = Notifier.getInstance(self.threadpool)

    def shutdown(self):
        # stop threadpool
        self.threadpool.joinAll()

    def perform_vod_usercallback(self,d,usercallback,mimetype,stream,filename):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"Session: perform_vod_usercallback()"
        def session_vod_usercallback_target():
            try:
                usercallback(d,mimetype,stream,filename)
            except:
                print_exc()
        self.perform_usercallback(session_vod_usercallback_target)

    def perform_getstate_usercallback(self,usercallback,data,returncallback):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"Session: perform_getstate_usercallback()"
        def session_getstate_usercallback_target():
            try:
                (when,getpeerlist) = usercallback(data)
                returncallback(usercallback,when,getpeerlist)
            except:
                print_exc()
        self.perform_usercallback(session_getstate_usercallback_target)


    def perform_removestate_callback(self,infohash,contentdest,removecontent):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"Session: perform_removestate_callback()"
        def session_removestate_callback_target():
            if DEBUG:
                print >>sys.stderr,"Session: session_removestate_callback_target called",currentThread().getName()
            try:
                self.session.sesscb_removestate(infohash,contentdest,removecontent)
            except:
                print_exc()
        self.perform_usercallback(session_removestate_callback_target)
        
    def perform_usercallback(self,target):
        self.sesslock.acquire()
        try:
            # TODO: thread pool, etc.
            self.threadpool.queueTask(target)
            
        finally:
            self.sesslock.release()

    def notify(self, subject, changeType, obj_id, *args):
        """
        Notify all interested observers about an event with threads from the pool
        """
        self.notifier.notify(subject,changeType,obj_id,*args)
        