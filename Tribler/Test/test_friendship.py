# Written by Arno Bakker
# see LICENSE.txt for license information

#
# WARNING:
#
# To run this test, please set
# RESCHEDULE_INTERVAL = 6
# RESEND_INTERVAL = 6
#
# In Tribler/Core/SocialNetwork/FriendshipMsgHandler.py
#


import unittest
import sys
import time
import socket
from traceback import print_exc
from types import StringType, DictType, IntType
from M2Crypto import EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
import btconn
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.MessageID import *
from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Test.test_social_overlap import TestSocialOverlap

DEBUG=True

REQ='REQ'
RESP='RESP'
FWD='FWD'

class TestFriendship(TestAsServer):
    """ 
    Testing FRIENDSHIP message of FRIENDSHIP extension V1
    """
    
    def setUp(self):
        """ override TestAsServer """
        print >>sys.stderr,"test: *** setup friendship"
        TestAsServer.setUp(self)

        self.usercallbackexpected = True
        self.usercallbackreceived = False

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # FRIENDSHIP
        self.config.set_social_networking(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        

        self.setUpMyListenSocket()

    def setUpMyListenSocket(self):
        self.dest_keypair = EC.gen_params(EC.NID_sect233k1)
        self.dest_keypair.gen_key()
        self.destpermid = str(self.dest_keypair.pub().get_der())
        self.destport = 4810
        
        # Start our server side, to with Tribler will try to connect
        self.destss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.destss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.destss.bind(('', self.destport))
        self.destss.listen(1)

        print >>sys.stderr,"test: my   permid",show_permid_short(self.mypermid)
        print >>sys.stderr,"test: his  permid",show_permid_short(self.hispermid)
        print >>sys.stderr,"test: dest permid",show_permid_short(self.destpermid)

    def tearDown(self):
        """ override TestAsServer """
        print >>sys.stderr,"test: *** tear down friendship"
        TestAsServer.tearDown(self)
        self.assert_((not self.usercallbackexpected) or (self.usercallbackreceived))
        time.sleep(10)

    #
    # Good FRIENDSHIP REQ
    # 
    def singtest_good_friendship_req1(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a REQ, and let the usercallback send a positive response 
        """
        self.session.set_friendship_callback(self.approve_usercallback)
        self.subtest_good_friendship_req(REQ,mresp=1)
        
        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.mypermid)
        self.assert_(fs == FS_MUTUAL)

    def approve_usercallback(self,permid,params):
        print >>sys.stderr,"test: Got user callback"
        self.usercallbackreceived = True
        self.session.send_friendship_message(permid,RESP,approved=True)

    def singtest_good_friendship_req0(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a REQ, and let the usercallback send a negative response 
        """
        self.session.set_friendship_callback(self.deny_usercallback)
        self.subtest_good_friendship_req(REQ,mresp=0)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.mypermid)
        self.assert_(fs == FS_I_DENIED)

    def deny_usercallback(self,permid,params):
        print >>sys.stderr,"test: Got user callback"
        self.usercallbackreceived = True
        self.session.send_friendship_message(permid,RESP,approved=False)


    def singtest_good_friendship_he_already_invited(self):
        """ 
            Test good FRIENDSHIP REQ message:
            We set the friendDB as if Tribler already sent an invite, 
            we then send a REQ, which should give an automatic reply. 
        """
        peerdb = self.session.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = self.mypermid
        peer['ip'] = '127.0.0.2'
        peer['port'] = 5000
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'],peer,update_dns=True,commit=True)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        frienddb.setFriendState(self.mypermid,FS_I_INVITED)
        print >>sys.stderr,"test: already invited, setting",show_permid_short(self.mypermid)

        self.usercallbackexpected = False
        self.subtest_good_friendship_req(REQ,mresp=1)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.mypermid)
        self.assert_(fs == FS_MUTUAL)



    def singtest_good_resp_he_already_at_mutual(self):
        """ 
            Test good FRIENDSHIP REQ message:
            We set the friendDB as if Tribler already sent an invite, 
            we then send a REQ, which should give an automatic reply. 
        """
        peerdb = self.session.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = self.mypermid
        peer['ip'] = '127.0.0.2'
        peer['port'] = 5000
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'],peer,update_dns=True,commit=True)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        frienddb.setFriendState(self.mypermid,FS_MUTUAL)
        print >>sys.stderr,"test: already invited, setting",show_permid_short(self.mypermid)

        self.usercallbackexpected = False
        self.subtest_good_friendship_req(RESP,mresp=1,expectreply=False)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.mypermid)
        self.assert_(fs == FS_MUTUAL)



    def singtest_good_friendship_req1_send_social_overlap(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a SOCIAL_OVERLAP, then a REQ, and let the usercallback 
            send a positive response, and check if he recorded our image. 
        """
        self.session.set_friendship_callback(self.approve_check_icon_usercallback)
        self.subtest_good_friendship_req(REQ,mresp=1,socover=True)
        
    def approve_check_icon_usercallback(self,permid,params):
        print >>sys.stderr,"test: Got user callback"
        
        peerdb = self.session.open_dbhandler(NTFY_PEERS)
        img = peerdb.getPeerIcon(self.mypermid)
        print >>sys.stderr,"test: My img is",`img`
        self.assert_(img[0] is not None)
        
        self.usercallbackreceived = True
        self.session.send_friendship_message(permid,RESP,approved=True)


    def subtest_good_friendship_req(self,mtype,fwd=None,mresp=None,socover=False,expectreply=True):
        print >>sys.stderr,"test: good FRIENDSHIP",mtype,fwd
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        
        if socover:
            tso = TestSocialOverlap("test_all")
            msg = tso.create_good_soverlap()
            s.send(msg)
        
        msg = self.create_good_friendship_payload(mtype,fwd,mresp)
        s.send(msg)

        s.b.s.settimeout(10.0)
        try:
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP: Got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            if expectreply:
                print >> sys.stderr,"test: Timeout, bad, peer didn't reply with FRIENDSHIP message"
                self.assert_(False)
            else:
                print >> sys.stderr,"test: Timeout, good, wasn't expecting a reply"
                self.assert_(True)

        if expectreply:
            self.check_friendship(resp[1:],RESP,None,mresp)
            time.sleep(10)
            # the other side should not have closed the connection, as
            # this is all valid, so this should not throw an exception:
            s.send('bla')
            s.close()



    #
    # Good FRIENDSHIP FWD destined for 3rd party (also us, as dest)
    # 
    def singtest_good_friendship_fwd_req_dest3rdp(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a FWD containing a REQ and see if Tribler tries to
            deliver it to the 3rd party. 
        """
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_dest3rdp(FWD,fwd=REQ)

    def singtest_good_friendship_fwd_resp0_dest3rdp(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a FWD containing a negative RESP and see if Tribler tries to
            deliver it to the specified dest (also us on diff listen port) 
        """
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_dest3rdp(FWD,fwd=RESP,mresp=0)
        
    def singtest_good_friendship_fwd_resp1_dest3rdp(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a FWD containing a positive RESP and see if Tribler tries to
            deliver it to the specified dest (also us on diff listen port) 
        """
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_dest3rdp(FWD,fwd=RESP,mresp=1)

    def subtest_good_friendship_fwd_dest3rdp(self,mtype,fwd=None,mresp=None):
        print >>sys.stderr,"test: good FRIENDSHIP dest = 3rd party",mtype,fwd
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_friendship_payload(mtype,fwd,mresp,source=self.mypermid,dest=self.destpermid)
        s.send(msg)

        # He should try to forward the request to us
        try:
            self.destss.settimeout(10.0)
            conn, addr = self.destss.accept()
            s = OLConnection(self.dest_keypair,'',0,conn,self.destport)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP fwd: Dest got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't connect to FWD dest"
            self.assert_(False)

        self.check_friendship(resp[1:],FWD,fwd,mresp,source=self.mypermid,dest=self.destpermid)


    #
    # Good FRIENDSHIP FWD destined for him
    #

    def singtest_good_friendship_fwd_req_desthim(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            We send a FWD containing a REQ meant for Tribler, and see if it
            sends a reply to dest (now source)
        """
        self.session.set_friendship_callback(self.approve_usercallback)
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_req_desthim(FWD,fwd=REQ,mresp=1)
        
        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.destpermid)
        self.assert_(fs == FS_MUTUAL)


    def subtest_good_friendship_fwd_req_desthim(self,mtype,fwd=None,mresp=None):
        print >>sys.stderr,"test: good FRIENDSHIP dest = him",mtype,fwd
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_friendship_payload(mtype,fwd,mresp,source=self.destpermid,dest=self.hispermid)
        s.send(msg)

        # He should try to reply to dest's request, forwarded through my
        try:
            self.destss.settimeout(10.0)
            conn, addr = self.destss.accept()
            s = OLConnection(self.dest_keypair,'',0,conn,self.destport)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP fwd: Dest got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't connect to FWD dest"
            self.assert_(False)

        self.check_friendship(resp[1:],RESP,fwd,mresp)


    def singtest_good_friendship_fwd_resp0_desthim(self):
        """ 
            Test good FRIENDSHIP RESP message: 
            We send a FWD containing a negative RESP and see if Tribler
            registers our denial. 
        """
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_resp_desthim(FWD,fwd=RESP,mresp=0)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.destpermid)
        self.assert_(fs == FS_HE_DENIED)


    def singtest_good_friendship_fwd_resp1_desthim(self):
        """ 
            Test good FRIENDSHIP RESP message: 
            We send a FWD containing a positive RESP and see if Tribler
            registers our confirmation. 
        """
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_resp_desthim(FWD,fwd=RESP,mresp=1)

        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.getFriendState(self.destpermid)
        print >>sys.stderr,"FS AFTER IS",fs
        self.assert_(fs == FS_HE_INVITED)


    def subtest_good_friendship_fwd_resp_desthim(self,mtype,fwd=None,mresp=None):
        print >>sys.stderr,"test: good FRIENDSHIP dest = him",mtype,fwd
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_friendship_payload(mtype,fwd,mresp,source=self.destpermid,dest=self.hispermid)
        s.send(msg)

        # He should not reply.
        try:
            self.destss.settimeout(10.0)
            conn, addr = self.destss.accept()
            s = OLConnection(self.dest_keypair,'',0,conn,self.destport)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP fwd: Dest got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    self.assert_(False)
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, good"
            self.assert_(True)



    #
    # Delegate
    #
    #
    # Good FRIENDSHIP REQ
    # 
    def singtest_good_friendship_delegate_req(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            Let Tribler send a REQ to a non-responding peer. Then it should
            send a FWD to us as friend or buddy. 
        """
        self.config_db()

        # Send request to offline peer
        self.session.send_friendship_message(self.mypermid,REQ)
        
        # See if he forwards to us
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_fromhim(FWD,fwd=REQ)


    def singtest_good_friendship_delegate_shutdown(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            Let Tribler send a REQ to a non-responding peer. Then it should
            send a FWD to us as friend or buddy. 
        """
        self.config_db()

        # Send request to offline peer
        print >>sys.stderr,"test: SESSION send msg"
        self.session.send_friendship_message(self.mypermid,REQ)
        time.sleep(1) # make sure message is saved

        # Shutdown session, to provoke forwarding
        print >>sys.stderr,"test: SESSION Shutdown"
        self.session.shutdown()
        
        # See if he forwards to us
        self.usercallbackexpected = False
        self.subtest_good_friendship_fwd_fromhim(FWD,fwd=REQ)

        self.session = None

    def config_db(self):
        peerdb = self.session.open_dbhandler(NTFY_PEERS)
        # Add friend
        peer = {}
        peer['permid'] = self.destpermid
        peer['ip'] = '127.0.0.1'
        peer['port'] = self.destport
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'],peer,update_dns=True,commit=True)
        
        # Make us as dest his friend
        frienddb = self.session.open_dbhandler(NTFY_FRIENDS)
        fs = frienddb.setFriendState(self.destpermid,state=FS_MUTUAL)

        # Add offline peer
        peer = {}
        peer['permid'] = self.mypermid
        peer['ip'] = '127.0.0.2'
        peer['port'] = 5000
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'],peer,update_dns=True,commit=True)
        

    def subtest_good_friendship_fwd_fromhim(self,mtype,fwd=None,mresp=None):
        print >>sys.stderr,"test: Expecting good FRIENDSHIP fwd from him",mtype,fwd

        # He should try to forward the request to us, his friend
        try:
            self.destss.settimeout(330.0)
            conn, addr = self.destss.accept()
            s = OLConnection(self.dest_keypair,'',0,conn,self.destport)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP fwd: Dest got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't connect to FWD dest"
            self.assert_(False)

        self.check_friendship(resp[1:],mtype,fwd,mresp,source=self.hispermid,dest=self.mypermid)



    def singtest_good_friendship_he_invites(self):
        """ 
            Test good FRIENDSHIP REQ message: 
            Let Tribler send a REQ to a good peer.
        """
        self.config_db()

        icontype = 'image/jpeg'
        icondata = self.read_usericon_ok()
        self.session.set_mugshot(icondata)

        # Send request to offline peer
        self.session.send_friendship_message(self.destpermid,REQ)
        
        # See if he forwards to us
        self.usercallbackexpected = False
        self.subtest_good_friendship_req_fromhim(REQ)

    def read_usericon_ok(self):
        return self.read_file('usericon-ok.jpg')

    def read_file(self,filename):
        f = open( filename, 'rb')
        data = f.read()
        f.close()
        return data



    def subtest_good_friendship_req_fromhim(self,mtype,fwd=None,mresp=None):
        print >>sys.stderr,"test: good FRIENDSHIP req from him",mtype,fwd

        # He should try to forward the request to us, his friend
        try:
            self.destss.settimeout(330.0)
            conn, addr = self.destss.accept()
            s = OLConnection(self.dest_keypair,'',0,conn,self.destport)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print >>sys.stderr,"test: good FRIENDSHIP fwd: Dest got reply",getMessageName(resp[0])
                if resp[0] == FRIENDSHIP:
                    break
                elif resp[0] == SOCIAL_OVERLAP:
                    d = bdecode(resp[1:])
                    print >>sys.stderr,"test: SOCIAL OVERLAP",`d`
                    pass
                else:
                    self.assert_(False)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't connect to FWD dest"
            self.assert_(False)

        self.check_friendship(resp[1:],mtype,fwd,mresp,source=self.hispermid,dest=self.mypermid)

        


    #
    # Bad FRIENDSHIP messages
    #
    def singtest_bad_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        
        self.usercallbackexpected = False
        
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()
        self.subtest_bad_friendship_response()
        self.subtest_bad_friendship_fwd()


    def create_good_friendship_payload(self,mtype,fwd,resp,source=None,dest=None):
        d = self.create_good_friendship(mtype,fwd,resp,source=source,dest=dest)
        return self.create_payload(d)
        
    def create_good_friendship(self,mtype,fwd,resp,source=None,dest=None):
        d = {}
        d['msg type'] = mtype
        if mtype == REQ:
            pass
        elif mtype == RESP:
            d['response'] = resp 
        else: # forward
            d['msg'] = self.create_good_friendship(fwd,None,resp)
            d['source'] = self.create_good_peer(source)
            d['dest'] = self.create_good_peer(dest)
        return d
            
    def create_good_peer(self,permid):
        d = {}
        d['permid'] = permid
        d['ip'] = '127.0.0.1'
        d['port'] = self.destport
        
        return d

    def create_payload(self,r):
        return FRIENDSHIP+bencode(r)

    def check_friendship(self,data,mtype,fwd,resp,dobdecode=True,source=None,dest=None):
        if dobdecode:
            d = bdecode(data)
        else:
            d = data
        
        print >>sys.stderr,"test: Got FRIENDSHIP",`d`,type(d)
        
        self.assert_(type(d) == DictType)
        self.assert_('msg type' in d)
        self.assert_(type(d['msg type']) == StringType)
        self.assert_(d['msg type'] == mtype)
        
        if mtype == RESP:
            self.assert_('response' in d)
            self.assert_(type(d['response']) == IntType)
            
            print >>sys.stderr,"test: COMPARE",`d['response']`,`resp`
            
            self.assert_(d['response'] == resp)
        elif mtype == FWD:
            self.assert_('source' in d)
            self.check_peer(d['source'],permid=source)
            self.assert_('dest' in d)
            self.check_peer(d['dest'],permid=dest)
            self.assert_('msg' in d)
            self.check_friendship(d['msg'],fwd,None,resp,dobdecode=False)

    def check_peer(self,d,permid=None):
        self.assert_('permid' in d)
        self.assert_(type(d['permid']) == StringType)
        self.assert_(d['permid'] == permid)
        self.assert_('ip' in d)
        self.assert_(type(d['ip']) == StringType)
        self.assert_('port' in d)
        self.assert_(type(d['port']) == IntType)



    def singtest_checkpoint(self):
        """ Unused """
        self.session.send_friendship_message(self.destpermid,RESP,approved=True)
        self.session.lm.overlay_apps.friendship_handler.checkpoint()
        self.session.lm.overlay_apps.friendship_handler.load_checkpoint()


    #
    # Bad FRIENDSHIP
    #    
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)

    def subtest_bad_not_dict1(self):
        self._test_bad(self.create_not_dict1)

    def subtest_bad_not_dict2(self):
        self._test_bad(self.create_not_dict2)

    def subtest_bad_empty_dict(self):
        self._test_bad(self.create_empty_dict)

    def subtest_bad_wrong_dict_keys(self):
        self._test_bad(self.create_wrong_dict_keys)

    def create_not_bdecodable(self):
        return FRIENDSHIP+"bla"

    def create_not_dict1(self):
        friendship = 481
        return self.create_payload(friendship)

    def create_not_dict2(self):
        friendship = []
        return self.create_payload(friendship)

    def create_empty_dict(self):
        friendship = {}
        return self.create_payload(friendship)

    def create_wrong_dict_keys(self):
        friendship = {}
        friendship['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        friendship['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_payload(friendship)

    def subtest_bad_friendship_response(self):
        self._test_bad(self.create_bad_response)

    def create_bad_response(self):
        friendship = {}
        friendship['msg type'] = RESP
        friendship['response'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_payload(friendship)


    def subtest_bad_friendship_fwd(self):
        methods = [
            self.make_bad_msg_forwarding_forward,
            self.make_bad_source,
            self.make_bad_dest]
        for method in methods:
            print >> sys.stderr,"\ntest: ",method,
            self._test_bad(method)
        

    def make_bad_msg_forwarding_forward(self):
        d = self.create_good_friendship(FWD,fwd=REQ,resp=None,source=self.destpermid,dest=self.hispermid)
        d['msg'] = self.create_good_friendship(FWD,fwd=REQ,resp=None,source=self.destpermid,dest=self.hispermid)
        return self.create_payload(d)
        
    def make_bad_source(self):
        d = self.create_good_friendship(FWD,fwd=REQ,resp=None,source=self.destpermid,dest=self.hispermid)
        d['source'] = self.make_bad_peer()
        return self.create_payload(d)

    def make_bad_dest(self):
        d = self.create_good_friendship(FWD,fwd=REQ,resp=None,source=self.destpermid,dest=self.hispermid)
        d['dest'] = self.make_bad_peer()
        return self.create_payload(d)

    def make_bad_peer(self):
        d = {}
        d['permid'] = 'peer 481'
        # Error is too little fields. 
        # TODO: test all possible bad peers
        
        return d

    def _test_bad(self,gen_friendship_func):
        print >>sys.stderr,"test: bad friendship",gen_friendship_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_friendship_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()

def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_friendship.py <method name>"
    else:
        suite.addTest(TestFriendship(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
