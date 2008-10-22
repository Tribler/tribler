# Written by Ali Abbas, Arno Bakker
# see LICENSE.txt for license information

# TODO: either maintain connections to friends always or supplement the
# list of friends with a number of on-line taste buddies.
#
# TODO: at least add fifo order to msgs, otherwise clicking 
# "make friend", "delete friend", "make friend" could arive in wrong order
# due to forwarding.
#

import threading
import sys
import os
import socket
import random
import cPickle
from time import time
from types import StringType, ListType, DictType, IntType, BooleanType
from traceback import print_exc,print_stack
from sets import Set

from Tribler.Core.simpledefs import *
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.BitTornado.bencode import bencode, bdecode

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.SocialNetwork.OverlapMsgHandler import OverlapMsgHandler
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, FriendDBHandler
from Tribler.Core.CacheDB.SqliteFriendshipStatsCacheDB import FriendshipStatisticsDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Core.Utilities.utilities import *

from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVENTH

DEBUG = True

"""
State diagram:

NOFRIEND -> I_INVITED or HE_INVITED
I_INVITED -> APPROVED or HE_DENIED
HE_INVITED -> APPROVED
HE_INVITED -> I_DENIED

In theory it could happen that he sends an response=1 RESP, in which case
he approved us. I consider that an HE_INIVITE
"""

RESCHEDULE_INTERVAL = 60
RESEND_INTERVAL = 5*60


class FriendshipMsgHandler:
    __singleton = None
    __lock = threading.Lock()

    @classmethod
    def getInstance(cls, *args, **kargs):
        if not cls.__singleton:
            cls.__lock.acquire()
            try:
                if not cls.__singleton:
                    cls.__singleton = cls(*args, **kargs)
            finally:
                cls.__lock.release()
        return cls.__singleton
    
    def __init__(self):
        if FriendshipMsgHandler.__singleton:
            raise RuntimeError, "FriendshipMsgHandler is singleton"
        self.overlay_bridge = None
        self.currmsgs = {}
        self.online_fsext_peers = Set() # online peers that speak FRIENDSHIP ext
        self.peerdb = PeerDBHandler.getInstance()
        self.frienddb = FriendDBHandler.getInstance()
        self.friendshipStatistics_db = FriendshipStatisticsDBHandler.getInstance()
        self.list_no_of_conn_attempts_per_target= {}
        self.usercallback = None
    
    def register(self, overlay_bridge, session):
        if DEBUG:
            print >> sys.stderr, "friendship: register"
        self.overlay_bridge = overlay_bridge
        self.session = session
        try:
            self.load_checkpoint()
        except:
            print_exc()
        self.overlay_bridge.add_task(self.reschedule_connects,RESCHEDULE_INTERVAL)
     
     
    def shutdown(self):
        """
        Delegate all outstanding messages to others
        """
        # Called by OverlayThread
        self.delegate_friendship_making()
        self.checkpoint()
        

    def register_usercallback(self,usercallback):
        self.usercallback = usercallback
    
    def anythread_send_friendship_msg(self,permid,type,params):
        """ Called when user adds someone from the person found, or by 
        explicity adding someone with her credentials
        It establishes overlay connection with the target peer """
        # Called by any thread
        
        olthread_func = lambda:self.send_friendship_msg(permid,type,params,submit=True)
        self.overlay_bridge.add_task(olthread_func,0)
        
        
    def send_friendship_msg(self,permid,type,params,submit=False):
        # Called by overlay thread 
        
        if submit:
            if DEBUG:
                print >>sys.stderr,"friendship: send_friendship_msg: Saving msg",show_permid_short(permid)
            self.save_msg(permid,type,params)
            
            if type == F_REQUEST_MSG:
                # Make him my friend, pending his approval
                self.frienddb.setFriendState(permid, commit=True,state=FS_I_INVITED)
            elif type == F_RESPONSE_MSG:
                # Mark response in DB
                if params['response']:
                    state = FS_MUTUAL
                else:
                    state = FS_I_DENIED
                self.frienddb.setFriendState(permid, commit=True,state=state)

        func = lambda exc,dns,permid,selversion:self.fmsg_connect_callback(exc, dns, permid, selversion, type)
        self.overlay_bridge.connect(permid,self.fmsg_connect_callback)
        
        
    def fmsg_connect_callback(self,exc,dns,permid,selversion, type = None):
        """ Callback function for the overlay connect function """
        # Called by OverlayThread

        if exc is None:
            if selversion < OLPROTO_VER_SEVENTH:
                self.remove_msgs_for_ltv7_peer(permid)
                return
            
            # Reached him
            sendlist = self.get_msgs_as_sendlist(targetpermid=permid)
            if DEBUG:
                print >> sys.stderr, 'friendship: fmsg_connect_callback: sendlist len',len(sendlist)
                #print_stack()
            
            for i in range(0,len(sendlist)):
                tuple = sendlist[i]
                
                permid,msgid,msg = tuple
                send_callback = lambda exc,permid:self.fmsg_send_callback(exc,permid,msgid)
                
                if DEBUG:
                    print >>sys.stderr,"friendship: fmsg_connect_callback: Sending",`msg`
                
                mypermid = self.session.get_permid()
                
                commit = (i == len(sendlist)-1)
                isForwarder = 0
                no_of_helpers = 0
#                if type == F_REQUEST_MSG:
#                    print
#                elif type == F_RESPONSE_MSG:
#                    print
                #Set forwarder to True and also no of helpers to 10
                if type == F_FORWARD_MSG:
                    isForwarder = 1
                    no_of_helpers = 10
                    
                  
                no_of_attempts = 0
                if permid in self.currmsgs:
                    msgid2rec = self.currmsgs[permid]
                    for msgid in msgid2rec:
                        msgrec = msgid2rec[msgid]
                        no_of_attempts = msgrec['attempt']
                
#                insertFriendshipStatistics(self, my_permid, target_permid, current_time, isForwarder = 0, no_of_attempts = 0, no_of_helpers = 0, commit = True):
                
                self.friendshipStatistics_db.insertOrUpdateFriendshipStatistics( bin2str(mypermid), 
                                                                         bin2str(permid), 
                                                                         int(time()),
                                                                         isForwarder, 
                                                                         no_of_attempts ,
                                                                         no_of_helpers, 
                                                                         commit=commit)
                
                self.overlay_bridge.send(permid, FRIENDSHIP + bencode(msg), send_callback)
                
                
        else:
            if DEBUG:
                peer = self.peerdb.getPeer(permid)
                print >>sys.stderr, 'friendship: Could not connect to peer', show_permid_short(permid),peer['name']
                print >>sys.stderr,exc
            
            mypermid = self.session.get_permid()
            
            isForwarder = 0
            no_of_helpers = 0
            if type == F_FORWARD_MSG:
                isForwarder = 1
                no_of_helpers = 10
                    
                 
            no_of_attempts = 0
            if permid in self.currmsgs:
                msgid2rec = self.currmsgs[permid]
                for msgid in msgid2rec:
                    msgrec = msgid2rec[msgid]
                    no_of_attempts = msgrec['attempt']
                
                
            self.friendshipStatistics_db.insertOrUpdateFriendshipStatistics( bin2str(mypermid), 
                                                                         bin2str(permid), 
                                                                         int(time()),
                                                                         isForwarder, 
                                                                         no_of_attempts ,
                                                                         no_of_helpers)
        
        


    def fmsg_send_callback(self,exc,permid,msgid):
        
        # If an exception arises
        if exc is None:
            self.delete_msg(permid,msgid)
        else:
            if DEBUG:
                print >> sys.stderr, 'friendship: Could not send to ',show_permid_short(permid)  
                print_exc()
            
        mypermid = self.session.get_permid()
        
        no_of_attempts = 0
        no_of_helpers = 10
        isForwarder = False
        if permid in self.currmsgs:
            msgid2rec = self.currmsgs[permid]
            for msgid in msgid2rec:
                msgrec = msgid2rec[msgid]
                no_of_attempts = msgrec['attempt']
                if msgrec['forwarded'] == True:
                    isForwarder = 1
            
            
        self.friendshipStatistics_db.insertOrUpdateFriendshipStatistics( bin2str(mypermid), 
                                                                         bin2str(permid), 
                                                                         int(time()),
                                                                         isForwarder, 
                                                                         no_of_attempts ,
                                                                         no_of_helpers)
                    

    def remove_msgs_for_ltv7_peer(self,permid):
        """ Remove messages destined for a peer that does not speak >= v7 of
        the overlay protocol
        """
        sendlist = self.get_msgs_as_sendlist(targetpermid=permid)
        if DEBUG:
            print >> sys.stderr, 'friendship: remove_msgs_for_ltv7_peer: sendlist len',len(sendlist)
        
        for i in range(0,len(sendlist)):
            tuple = sendlist[i]
            
            permid,msgid,msg = tuple
            self.delete_msg(permid,msgid)


    #
    # Incoming connections
    #
    def handleConnection(self, exc, permid, selversion, locally_initiated):

        if selversion < OLPROTO_VER_SEVENTH:
            return True

        if exc is None:
            self.online_fsext_peers.add(permid)

            # if we meet peer otherwise, dequeue messages
            if DEBUG:
                print >> sys.stderr,"friendship: Met peer, attempting to deliver msgs",show_permid_short(permid)
            
            # If we're initiating the connection from this handler, the 
            # fmsg_connect_callback will get called twice:
            # 1. here
            # 2. just a bit later when the callback for a successful connect()
            #    is called.
            # Solution: we delay this call, which should give 2. the time to
            # run and remove msgs from the queue.
            #
            # Better: remove msgs from queue when sent and reinsert if send fails
            #
            friendship_delay_func = lambda:self.fmsg_connect_callback(None,None,permid,selversion)
            self.overlay_bridge.add_task(friendship_delay_func,4)
        else:
            try:
                self.online_fsext_peers.remove(permid)
            except:
                pass
            
        return True        


    #
    # Incoming messages
    # 
    def handleMessage(self, permid, selversion, message):
        """ Handle incoming Friend Request, and their response"""

        if selversion < OLPROTO_VER_SEVENTH:
            if DEBUG:
                print >> sys.stderr,"friendship: Got FRIENDSHIP msg from peer with old protocol",show_permid_short(permid)
            return False
        
        try:
            d = bdecode(message[1:])
        except:
            print_exc()
            return False
        
        return self.process_message(permid,selversion,d)
    
    
    def process_message(self,permid,selversion,d):
        
        if self.isValidFriendMsg(d):

            if DEBUG:
                print >> sys.stderr,"friendship: Got FRIENDSHIP msg",d['msg type']
        
            # If the message is to become a friend, i.e., a friendship request
            if d['msg type'] == F_REQUEST_MSG:
                self.process_request(permid,d)                  
                        
            # If the message is to have a response on friend request    
            elif d['msg type'] == F_RESPONSE_MSG: 
                self.process_response(permid,d)
                    
            # If the receiving message is to delegate the Friendship request to the target peer
            elif d['msg type'] == F_FORWARD_MSG:
                return self.process_forward(permid,selversion,d)
            else:
                if DEBUG:
                    print >>sys.stderr,"friendship: Got unknown msg type",d['msg type']
                return False
            
            return True
        else:
            if DEBUG:
                print >>sys.stderr,"friendship: Got bad FRIENDSHIP message"
            return False
                
    def process_request(self,permid,d):
        # to see that the following peer is already a friend, or not
        fs = self.frienddb.getFriendState(permid) 

        if DEBUG:
            print >>sys.stderr,"friendship: process_request: Got request, fs",show_permid_short(permid),fs

        
        if fs == FS_NOFRIEND or fs == FS_HE_DENIED:
            # not on HE_INVITED, to filter out duplicates
            
            # And if that peer is not already added as a friend, either approved, or unapproved
            # call friend dialog
            self.frienddb.setFriendState(permid, commit=True, state = FS_HE_INVITED)
            
            # FUTURE: always do callback, such that we also know about failed
            # attempts
            if self.usercallback is not None:
                friendship_usercallback = lambda:self.usercallback(permid,[])
                self.session.uch.perform_usercallback(friendship_usercallback)
        elif fs == FS_I_INVITED: 
            # In case, requestee is already added as friend, just make this 
            # requestee as an approved friend

            if DEBUG:
                print >>sys.stderr,"friendship: process_request: Got request but I already invited him"
            
            self.frienddb.setFriendState(permid, commit=True, state = FS_MUTUAL)

            if DEBUG:
                print >>sys.stderr,"friendship: process_request: Got request but I already invited him: sending reply"

            self.send_friendship_msg(permid,F_RESPONSE_MSG,{'response':1},submit=True)
        elif fs == FS_MUTUAL:
            if DEBUG:
                print >>sys.stderr,"friendship: process_request: Got request but already approved"
            pass
        elif fs == FS_I_DENIED:
            if DEBUG:
                print >>sys.stderr,"friendship: process_request: Got request but I already denied"
            pass
        elif DEBUG:
            print >>sys.stderr,"friendship: process_request: Got request, but fs is",fs

    def process_response(self,permid,d):

        mypermid = self.session.get_permid()
                     
                
        self.friendshipStatistics_db.updateFriendshipResponseTime( bin2str(mypermid), 
                                                                         bin2str(permid), 
                                                                         int(time()))

        
        fs = self.frienddb.getFriendState(permid)
         
        # If the request to add has been approved
        if d['response'] == 1:
            if fs == FS_I_INVITED:
                self.frienddb.setFriendState(permid, commit=True, state = FS_MUTUAL)
            elif fs != FS_MUTUAL:
                # Unsollicited response, consider this an invite, if not already friend
                self.frienddb.setFriendState(permid, commit=True, state = FS_HE_INVITED)
        else:
            # He denied our friendship
            self.frienddb.setFriendState(permid, commit=True, state = FS_HE_DENIED)

                
    def process_forward(self,permid,selversion,d):
        
        mypermid = self.session.get_permid()
        if d['dest']['permid'] == mypermid:
            # This is a forward containing a message meant for me
            
            # First add original sender to DB so we can connect back to it
            self.addPeerToDB(d['source'])
            
            self.process_message(d['source']['permid'],selversion,d['msg'])
            
            return True
        
            
        else:
            # Queue and forward
            if DEBUG:
                print >>sys.stderr,"friendship: process_fwd: Forwarding immediately to",show_permid_short(d['dest']['permid'])

            if permid != d['source']['permid']:
                if DEBUG:
                    print >>sys.stderr,"friendship: process_fwd: Forwarding: Illegal, source is not sender, and dest is not me"
                return False
            # First add dest to DB so we can connect to it
            
            # FUTURE: don't let just any peer overwrite the IP+port of a peer
            # if self.peer_db.hasPeer(d['dest']['permid']):
            self.addPeerToDB(d['dest'])
            
            self.send_friendship_msg(d['dest']['permid'],d['msg type'],d,submit=True)
            return True

    def addPeerToDB(self,mpeer):
        peer = {}
        peer['permid'] = mpeer['permid']
        peer['ip'] = mpeer['ip']
        peer['port'] = mpeer['port']
        peer['last_seen'] = 0
        self.peerdb.addPeer(mpeer['permid'],peer,update_dns=True,commit=True)
        

    def create_friendship_msg(self,type,params):
        
        if DEBUG:
            print >>sys.stderr,"friendship: create_fs_msg:",type,`params`
        
        mypermid = self.session.get_permid()
        myip = self.session.get_external_ip()
        myport = self.session.get_listen_port()
        
        d ={'msg type':type}     
        if type == F_RESPONSE_MSG:
            d['response'] = params['response']
        elif type == F_FORWARD_MSG:
            
            if DEBUG:
                print >>sys.stderr,"friendship: create: fwd: params",`params`
            peer = self.peerdb.getPeer(params['destpermid']) # ,keys=['ip', 'port']) 
            if peer is None:
                if DEBUG:
                    print >> sys.stderr, "friendship: create msg: Don't know IP + port of peer", show_permid_short(params['destpermid'])
                return
            #if DEBUG:
            #    print >> sys.stderr, "friendship: create msg: Peer at",peer
            
            # FUTURE: add signatures on ip+port
            src = {'permid':mypermid,'ip':myip,'port':myport}
            dst = {'permid':params['destpermid'],'ip':peer['ip'],'port':peer['port']}
            d.update({'source':src,'dest':dst,'msg':params['msg']})
        return d



    def isValidFriendMsg(self,d):

        if DEBUG:
            print >>sys.stderr,"friendship: msg: payload is",`d`    

        
        if type(d) != DictType:
            if DEBUG:
                print >>sys.stderr,"friendship: msg: payload is not bencoded dict"    
            return False
        if not 'msg type' in d:
            if DEBUG:
                print >>sys.stderr,"friendship: msg: dict misses key",'msg type'    
            return False
        
        if d['msg type'] == F_REQUEST_MSG:
            keys = d.keys()[:]
            if len(keys)-1 != 0:
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: REQ: contains superfluous keys",keys    
                return False
            return True
            
        if d['msg type'] == F_RESPONSE_MSG:
            if (d.has_key('response') and (d['response'] == 1 or d['response'] == 0)):
                return True
            else:
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: RESP: something wrong",`d`    
                return False
            
        if d['msg type'] == F_FORWARD_MSG:
            if not self.isValidPeer(d['source']):
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: FWD: source bad",`d`    
                return False
            if not self.isValidPeer(d['dest']):
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: FWD: dest bad",`d`    
                return False
            if not 'msg' in d:
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: FWD: no msg",`d`    
                return False
            if not self.isValidFriendMsg(d['msg']):
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: FWD: bad msg",`d`    
                return False
            if d['msg']['msg type'] == F_FORWARD_MSG:
                if DEBUG:
                    print >>sys.stderr,"friendship: msg: FWD: cannot contain fwd",`d`    
                return False
            return True
        
        return False


    def isValidPeer(self,d):
        if (d.has_key('ip') and d.has_key('port') and d.has_key('permid') 
            and validPermid(d['permid'])
            and validIP(d['ip'])and validPort(d['port'])):
            return True
        else:
            return False                 


    def save_msg(self,permid,type,params):
        
        if not permid in self.currmsgs:
            self.currmsgs[permid] = {}
        
        mypermid = self.session.get_permid()    
        now = time()
        attempt = 1
        
        base = mypermid+permid+str(now)+str(random.random())
        msgid = sha(base).hexdigest()
        msgrec = {'permid':permid,'type':type,'params':params,'attempt':attempt,'t':now,'forwarded':False}
        
        msgid2rec = self.currmsgs[permid]
        msgid2rec[msgid] = msgrec
        
    def delete_msg(self,permid,msgid):
        try: 
            if DEBUG:
                print >>sys.stderr,"friendship: Deleting msg",show_permid_short(permid),msgid
            msgid2rec = self.currmsgs[permid]
            del msgid2rec[msgid]
        except:
            print_exc()

    def set_msg_forwarded(self,permid,msgid):
        try: 
            msgid2rec = self.currmsgs[permid]
            msgid2rec[msgid]['forwarded'] = True
        except:
            print_exc()

    def reschedule_connects(self):
        """ This function is run peridocically and reconnects to peers when
        messages meant for it are due to be retried
        """
        now = time()
        delmsgids = []
        reconnectpermids = Set()
        for permid in self.currmsgs:
            msgid2rec = self.currmsgs[permid]
            for msgid in msgid2rec:
                msgrec = msgid2rec[msgid]

                eta = self.calc_eta(msgrec)
                
                if DEBUG:
                    diff = None
                    if eta is not None:
                        diff = eta - now
                        
                    peer = self.peerdb.getPeer(permid)
                    if DEBUG:
                        print >>sys.stderr,"friendship: reschedule: ETA",show_permid_short(permid),peer['name'],diff
                
                if eta is None: 
                    delmsgids.append((permid,msgid))
                elif now > eta-1.0: # -1 for round off
                    # reconnect
                    reconnectpermids.add(permid)
                    msgrec['attempt'] = msgrec['attempt'] + 1
                    
                    # Delegate 
                    if msgrec['type'] == F_REQUEST_MSG and msgrec['attempt'] == 2:
                         self.delegate_friendship_making(targetpermid=permid,targetmsgid=msgid)
        
        # Remove timed out messages
        for permid,msgid in delmsgids:
            if DEBUG:
                print >>sys.stderr,"friendship: reschedule: Deleting",show_permid_short(permid),msgid
            self.delete_msg(permid,msgid)
        
        # Initiate connections to peers for which we have due messages    
        for permid in reconnectpermids:
            if DEBUG:
                print >>sys.stderr,"friendship: reschedule: Reconnect to",show_permid_short(permid)

            self.overlay_bridge.connect(permid,self.fmsg_connect_callback)
        
        # Reschedule this periodic task
        self.overlay_bridge.add_task(self.reschedule_connects,RESCHEDULE_INTERVAL)
        
        
    def calc_eta(self,msgrec):
        if msgrec['type'] == F_FORWARD_MSG:
            if msgrec['attempt'] >= 10:
                # Stop trying to forward after a given period 
                return None
            # exponential backoff, on 10th attempt we would wait 24hrs
            eta = msgrec['t'] + pow(3.116,msgrec['attempt'])
        else:
            if msgrec['attempt'] >= int(7*24*3600/RESEND_INTERVAL):
                # Stop trying to forward after a given period = 1 week 
                return None

            eta = msgrec['t'] + msgrec['attempt']*RESEND_INTERVAL 
        return eta
        

    def get_msgs_as_sendlist(self,targetpermid=None):

        sendlist = []
        if targetpermid is None:
            permids = self.currmsgs.keys()
        else:
            permids = [targetpermid] 
        
        for permid in permids:
            msgid2rec = self.currmsgs.get(permid,[])
            for msgid in msgid2rec:
                msgrec = msgid2rec[msgid]
                
                if DEBUG:
                    print >>sys.stderr,"friendship: get_msgs: Creating",msgrec['type'],`msgrec['params']`
                if msgrec['type'] == F_FORWARD_MSG:
                    msg = msgrec['params']
                else:
                    msg = self.create_friendship_msg(msgrec['type'],msgrec['params'])
                tuple = (permid,msgid,msg)
                sendlist.append(tuple)
        return sendlist


    def get_msgs_as_fwd_sendlist(self,targetpermid=None,targetmsgid=None):

        sendlist = []
        if targetpermid is None:
            permids = self.currmsgs.keys()
        else:
            permids = [targetpermid] 
        
        for permid in permids:
            msgid2rec = msgid2rec = self.currmsgs.get(permid,[])
            for msgid in msgid2rec:
                if targetmsgid is None or msgid == targetmsgid:
                    msgrec = msgid2rec[msgid]
                    if msgrec['type'] != F_FORWARD_MSG and msgrec['forwarded'] == False:
                        # Don't forward forwards, or messages already forwarded
                    
                        # Create forward message for original
                        params = {}
                        params['destpermid'] = permid
                        params['msg'] = self.create_friendship_msg(msgrec['type'],msgrec['params'])
                    
                        msg = self.create_friendship_msg(F_FORWARD_MSG,params)
                        tuple = (permid,msgid,msg)
                        sendlist.append(tuple)
        return sendlist
        

                
    def delegate_friendship_making(self,targetpermid=None,targetmsgid=None):
        if DEBUG:
            print >>sys.stderr,"friendship: delegate:",show_permid_short(targetpermid),targetmsgid

        # 1. See if there are undelivered msgs
        sendlist = self.get_msgs_as_fwd_sendlist(targetpermid=targetpermid,targetmsgid=targetmsgid)
        if DEBUG:
            print >>sys.stderr,"friendship: delegate: Number of messages queued",len(sendlist)
        
        if len(sendlist) == 0:
            return
  
        # 2. Get friends, not necess. online
        friend_permids = self.frienddb.getFriends()
        
        if DEBUG:
            l = len(friend_permids)
            print >>sys.stderr,"friendship: delegate: friend helpers",l
            for permid in friend_permids:
                print >>sys.stderr,"friendship: delegate: friend helper",show_permid_short(permid)
        
        # 3. Sort online peers on similarity, highly similar should be tastebuddies
        if DEBUG:
            print >>sys.stderr,"friendship: delegate: Number of online v7 peers",len(self.online_fsext_peers)
        tastebuddies = self.peerdb.getPeers(list(self.online_fsext_peers),['similarity','name']) 
        tastebuddies.sort(sim_desc_cmp)

        if DEBUG:
            print >>sys.stderr,"friendship: delegate: Sorted tastebuddies",`tastebuddies`

        tastebuddies_permids = []
        size = min(10,len(tastebuddies))
        for i in xrange(0,size):
            peer = tastebuddies[i]
            if DEBUG:
                print >>sys.stderr,"friendship: delegate: buddy helper",show_permid_short(peer['permid'])
            tastebuddies_permids.append(peer['permid'])

        # 4. Create list of helpers:
        #
        # Policy: Helpers are a mix of friends and online tastebuddies
        # with 70% friends (if avail) and 30% tastebuddies
        #
        # I chose this policy because friends are not guaranteed to be online
        # and waiting to see if we can connect to them before switching to
        # the online taste buddies is complex code-wise and time-consuming.
        # We don't have a lot of time when this thing is called by Session.shutdown()
        #
        nwant = 10
        nfriends = int(nwant * .7)
        nbuddies = int(nwant * .3)
        
        part1 = sampleorlist(friend_permids,nfriends)
        fill = nfriends-len(part1) # if no friends, use tastebuddies
        part2 = sampleorlist(tastebuddies_permids,nbuddies+fill)
        helpers = part1 + part2

        if DEBUG:
            l = len(helpers)
            print >>sys.stderr,"friendship: delegate: end helpers",l
            for permid in helpers:
                print >>sys.stderr,"friendship: delegate: end helper",show_permid_short(permid),self.frienddb.getFriendState(permid),self.peerdb.getPeers([permid],['similarity','name'])


        for tuple in sendlist:
            destpermid,msgid,msg = tuple
            for helperpermid in helpers:
                if destpermid != helperpermid:
                    connect_callback = lambda exc,dns,permid,selversion:self.forward_connect_callback(exc,dns,permid,selversion,destpermid,msgid,msg)
                    
                    if DEBUG:
                        print >>sys.stderr,"friendship: delegate: Connecting to",show_permid_short(helperpermid)
                     
                    self.overlay_bridge.connect(helperpermid, connect_callback)


    def forward_connect_callback(self,exc,dns,permid,selversion,destpermid,msgid,msg):
        if exc is None:
            
            if selversion < OLPROTO_VER_SEVENTH:
                return
            
            send_callback = lambda exc,permid:self.forward_send_callback(exc,permid,destpermid,msgid)
            if DEBUG:
                print >>sys.stderr,"friendship: forward_connect_callback: Sending",`msg`
            self.overlay_bridge.send(permid, FRIENDSHIP + bencode(msg), send_callback)
        elif DEBUG:
            print >>sys.stderr,"friendship: forward: Could not connect to helper",show_permid_short(permid)


    def forward_send_callback(self,exc,permid,destpermid,msgid):
        if DEBUG:
            if exc is None:
                if DEBUG:
                    print >>sys.stderr,"friendship: forward: Success forwarding to helper",show_permid_short(permid)
                self.set_msg_forwarded(destpermid,msgid)
            else:
                if DEBUG:
                    print >>sys.stderr,"friendship: forward: Failed to forward to helper",show_permid_short(permid)
                pass
        
    def checkpoint(self):
        statedir = self.session.get_state_dir()
        newfilename = os.path.join(statedir,'new-friendship-msgs.pickle')
        finalfilename = os.path.join(statedir,'friendship-msgs.pickle')
        try:
            f = open(newfilename,"wb")
            cPickle.dump(self.currmsgs,f)
            f.close()
            try:
                os.remove(finalfilename)
            except:
                # If first time, it doesn't exist
                print_exc()
            os.rename(newfilename,finalfilename)
        except:
            print_exc()
        
    def load_checkpoint(self):
        statedir = self.session.get_state_dir()
        finalfilename = os.path.join(statedir,'friendship-msgs.pickle')
        try:
            f = open(finalfilename,"rb")
            self.currmsgs = cPickle.load(f)
        except:
            print_exc()

        # Increase # attempts till current time
        now = time()
        for permid in self.currmsgs:
            msgid2rec = self.currmsgs[permid]
            for msgid in msgid2rec:
                msgrec = msgid2rec[msgid]
                diff = now - msgrec['t']
                a = int(diff/RESEND_INTERVAL)
                a += 1
                if DEBUG:
                    print >>sys.stderr,"friendship: load_checkp: Changing #attempts from",msgrec['attempt'],a
                msgrec['attempt'] = a

        
def sim_desc_cmp(peera,peerb):
    if peera['similarity'] < peerb['similarity']:
        return 1
    elif peera['similarity'] > peerb['similarity']:
        return -1
    else:
        return 0
    
def sampleorlist(z,k):
    if len(z) < k:
        return z
    else:
        return random.sample(k)
