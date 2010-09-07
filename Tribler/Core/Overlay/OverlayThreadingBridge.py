# Written by Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# This class bridges between the OverlayApps class and the SecureOverlay
# and ensures that all upcalls made by the NetworkThread via the SecureOverlay
# are handed over to a different thread, the OverlayThread that propagates the
# upcall to the OverlayApps.
# 

import sys
from threading import currentThread
from traceback import print_exc

from Tribler.Core.Overlay.SecureOverlay import CloseException
from Tribler.Core.BitTornado.BT1.MessageID import getMessageName
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
import threading

DEBUG = False

class OverlayThreadingBridge:

    __single = None
    lock = threading.Lock()

    def __init__(self):
        if OverlayThreadingBridge.__single:
            raise RuntimeError, "OverlayThreadingBridge is Singleton"
        OverlayThreadingBridge.__single = self 
        
        self.secover = None
        self.olapps = None
        self.olappsmsghandler = None
        self.olappsconnhandler = None

        # Current impl of wrapper: single thread
        self.tqueue = TimedTaskQueue(nameprefix="Overlay")

    def getInstance(*args, **kw):
        # Singleton pattern with double-checking
        if OverlayThreadingBridge.__single is None:
            OverlayThreadingBridge.lock.acquire()   
            try:
                if OverlayThreadingBridge.__single is None:
                    OverlayThreadingBridge(*args, **kw)
            finally:
                OverlayThreadingBridge.lock.release()
        return OverlayThreadingBridge.__single
    getInstance = staticmethod(getInstance)

    def resetSingleton(self):
        """ For testing purposes """
        OverlayThreadingBridge.__single = None 

    def register_bridge(self,secover,olapps):
        """ Called by MainThread """
        self.secover = secover
        self.olapps = olapps
        
        secover.register_recv_callback(self.handleMessage)
        secover.register_conns_callback(self.handleConnection)

    #
    # SecOverlay interface
    #
    def register(self,launchmanycore,max_len):
        """ Called by MainThread """
        self.secover.register(launchmanycore,max_len)

        # FOR TESTING ONLY
        self.iplport2oc = self.secover.iplport2oc

    def get_handler(self):
        return self.secover

    def start_listening(self):
        """ Called by MainThread """
        self.secover.start_listening()

    def register_recv_callback(self,callback):
        """ Called by MainThread """
        self.olappsmsghandler = callback

    def register_conns_callback(self,callback):
        """ Called by MainThread """
        self.olappsconnhandler = callback

    def handleConnection(self,exc,permid,selversion,locally_initiated,hisdns):
        """ Called by NetworkThread """
        # called by SecureOverlay.got_auth_connection() or cleanup_admin_and_callbacks()
        if DEBUG:
            print >>sys.stderr,"olbridge: handleConnection",exc,show_permid_short(permid),selversion,locally_initiated,hisdns,currentThread().getName()
        
        def olbridge_handle_conn_func():
            # Called by OverlayThread

            if DEBUG:
                print >>sys.stderr,"olbridge: handle_conn_func",exc,show_permid_short(permid),selversion,locally_initiated,hisdns,currentThread().getName()
             
            try:
                if hisdns:
                    self.secover.add_peer_to_db(permid,hisdns,selversion)
                    
                if self.olappsconnhandler is not None:    # self.olappsconnhandler = OverlayApps.handleConnection 
                    self.olappsconnhandler(exc,permid,selversion,locally_initiated)
            except:
                print_exc()
                
            if isinstance(exc,CloseException):
                self.secover.update_peer_status(permid,exc.was_auth_done())
                
        self.tqueue.add_task(olbridge_handle_conn_func,0)
        
    def handleMessage(self,permid,selversion,message):
        """ Called by NetworkThread """
        #ProxyService_
        #
        # DEBUG
        #print "### olbridge: handleMessage", show_permid_short(permid), selversion, getMessageName(message[0]), currentThread().getName()
        #
        #_ProxyService
        
        if DEBUG:
            print >>sys.stderr,"olbridge: handleMessage",show_permid_short(permid),selversion,getMessageName(message[0]),currentThread().getName()
        
        def olbridge_handle_msg_func():
            # Called by OverlayThread
            
            if DEBUG:
                print >>sys.stderr,"olbridge: handle_msg_func",show_permid_short(permid),selversion,getMessageName(message[0]),currentThread().getName()
             
            try:
                if self.olappsmsghandler is None:
                    ret = True
                else:
                    ret = self.olappsmsghandler(permid,selversion,message)
            except:
                print_exc()
                ret = False
            if ret == False:
                if DEBUG:
                    print >>sys.stderr,"olbridge: olbridge_handle_msg_func closing!",show_permid_short(permid),selversion,getMessageName(message[0]),currentThread().getName()
                self.close(permid)
                
        self.tqueue.add_task(olbridge_handle_msg_func,0)
        return True


    def connect_dns(self,dns,callback):
        """ Called by OverlayThread/NetworkThread """
        
        if DEBUG:
            print >>sys.stderr,"olbridge: connect_dns",dns
        
        def olbridge_connect_dns_callback(cexc,cdns,cpermid,cselver):
            # Called by network thread

            if DEBUG:
                print >>sys.stderr,"olbridge: connect_dns_callback",cexc,cdns,show_permid_short(cpermid),cselver
             
            olbridge_connect_dns_callback_lambda = lambda:callback(cexc,cdns,cpermid,cselver)
            self.add_task(olbridge_connect_dns_callback_lambda,0)
            
        self.secover.connect_dns(dns,olbridge_connect_dns_callback)


    def connect(self,permid,callback):
        """ Called by OverlayThread """

        if DEBUG:
            print >>sys.stderr,"olbridge: connect",show_permid_short(permid), currentThread().getName()
        
        def olbridge_connect_callback(cexc,cdns,cpermid,cselver):
            # Called by network thread
            
            if DEBUG:
                print >>sys.stderr,"olbridge: connect_callback",cexc,cdns,show_permid_short(cpermid),cselver, callback, currentThread().getName()

             
            olbridge_connect_callback_lambda = lambda:callback(cexc,cdns,cpermid,cselver)
            # Jie: postpone to call this callback to schedule it after the peer has been added to buddycast connection list
            # Arno, 2008-09-15: No-no-no
            self.add_task(olbridge_connect_callback_lambda,0)    
            
        self.secover.connect(permid,olbridge_connect_callback)


    def send(self,permid,msg,callback):
        """ Called by OverlayThread """

        if DEBUG:
            print >>sys.stderr,"olbridge: send",show_permid_short(permid),len(msg)

        def olbridge_send_callback(cexc,cpermid):
            # Called by network thread
            
            if DEBUG:
                print >>sys.stderr,"olbridge: send_callback",cexc,show_permid_short(cpermid)

             
            olbridge_send_callback_lambda = lambda:callback(cexc,cpermid)
            self.add_task(olbridge_send_callback_lambda,0)
        
        self.secover.send(permid,msg,olbridge_send_callback)

    def close(self,permid):
        """ Called by OverlayThread """
        self.secover.close(permid)
        
    def add_task(self,task,t=0,ident=None):
        """ Called by OverlayThread """
        self.tqueue.add_task(task,t,ident)
        
#===============================================================================
#    # Jie: according to Arno's suggestion, commit on demand instead of periodically
#    def periodic_commit(self):
#        period = 5*60    # commit every 5 min
#        try:
#            db = SQLiteCacheDB.getInstance()
#            db.commit()
#        except:
#            period = period*2
#        self.add_task(self.periodic_commit, period)
#        
#===============================================================================
        
        
