# Written by Arno Bakker
# see LICENSE.txt for license information
#
# This test checks the new SecureOverlay class created in Fall 2006
#
# Note that we start a new Python interpreter for each test case.
# Also note we create 2 peers and thus two networking stacks. In principle, 
# they should use two different SecureOverlay instances (not a singleton), but 
# there may be some interference.
# 
# To properly follow the test, enable debugging on BitTornado/SocketHandler,
# BitTornado/ServerPortHandler and BitTornado/Rawserver in addition to
# Tribler/Overlay/SecureOverlay
#
#

import sys
import os
import unittest
from threading import Event, Thread, currentThread
from socket import error as socketerror
from time import sleep
import tempfile
from traceback import print_exc,print_stack
import shutil

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.BitTornado.ServerPortHandler import MultiHandler
from Tribler.Core.BitTornado.BT1.MessageID import GET_METADATA

from M2Crypto import EC
from Tribler.Core.Overlay.SecureOverlay import SecureOverlay, overlay_infohash, OLPROTO_VER_CURRENT
import Tribler.Core.CacheDB.sqlitecachedb as sqlitecachedb  
from Tribler.Core.CacheDB.SqliteCacheDBHandler import PeerDBHandler
from Tribler.Core.Utilities.utilities import show_permid_short

class FakeSession:
    
    def __init__(self,lm,keypair,permid,listen_port):
        self.lm = lm
        self.keypair = keypair
        self.permid = permid
        self.listen_port = listen_port

    def get_permid(self):
        return self.permid
        
    def get_listen_port(self):
        return self.listen_port

# Thread must come as first parent class!
class Peer(Thread):
    def __init__(self,testcase,port,secover):
        Thread.__init__(self)
        self.setDaemon(True)

        self.testcase = testcase

        self.doneflag = Event()
        config = {}
        config['timeout_check_interval'] = 100000
        config['timeout'] = 100000
        config['ipv6_enabled'] = 0
        config['minport'] = port
        config['maxport'] = port+5
        config['random_port'] = 0
        config['bind'] = ''
        config['ipv6_binds_v4'] = 0
        config['max_message_length'] = 2 ** 23
        config['state_dir'] = config['install_dir'] = tempfile.mkdtemp()
        config['peer_icon_path'] = 'icons'

        self.rawserver = RawServer(self.doneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.report_failure,
                                   errorfunc = self.report_error)
        while 1:
            try:
                self.listen_port = self.rawserver.find_and_bind(0, 
                                config['minport'], config['maxport'], config['bind'], 
                                reuse = True,
                                ipv6_socket_style = config['ipv6_binds_v4'], 
                                randomizer = config['random_port'])
                print >> sys.stderr,"test: Got listen port", self.listen_port
                break
            except socketerror, e:
                self.report_failure(str(e))
                msg = "Couldn't not bind to listen port - " + str(e)
                self.report_failure(msg)
                return

        self.multihandler = MultiHandler(self.rawserver, self.doneflag)
        # Note: We don't want a singleton, we want
        # two different instances for peer1 and peer2
        self.secure_overlay = secover

        self.my_keypair = EC.gen_params(EC.NID_sect233k1)
        self.my_keypair.gen_key()
        self.my_permid = str(self.my_keypair.pub().get_der())


        self.session = FakeSession(self,self.my_keypair,self.my_permid,self.listen_port)
        self.peer_db = PeerDBHandler.getInstance()

        self.secure_overlay.register(self,config['max_message_length'])
        print >>sys.stderr,"Peer: Setting",self.secure_overlay.get_handler(),"as handler at SocketHandler"
        self.rawserver.sockethandler.set_handler(self.secure_overlay.get_handler())
        self.secure_overlay.start_listening()

        # Stupid rawserver goes into very long wait if there are no short
        # term tasks. Emulate this
        self.rawserver.add_task(self.dummy_task,0)

    def run(self):
        print >> sys.stderr,"test: MyServer: run called by",currentThread().getName()
        self.multihandler.listen_forever()
        pass    

    def report_failure(self,msg):
        self.testcase.assertRaises(Exception, self.report_failure)

    def report_error(self,msg):
        self.testcase.assertRaises(Exception, self.report_error)

    def dummy_task(self):
        self.rawserver.add_task(self.dummy_task,1)

    def get_ext_ip(self):
        return '127.0.0.1'

    def shutdown(self):
        self.doneflag.set()
        self.rawserver.shutdown()


class TestSecureOverlay(unittest.TestCase):
    
    def setUp(self):
        self.config_path = tempfile.mkdtemp()
        config = {}
        config['state_dir'] = self.config_path
        config['install_dir'] = os.path.join('..','..')
        config['peer_icon_path'] = os.path.join(self.config_path,'peer_icons')
        sqlitecachedb.init(config, self.rawserver_fatalerrorfunc)
        
        secover1 = SecureOverlay.getInstance()
        secover1.resetSingleton()
        secover2 = SecureOverlay.getInstance()
        secover2.resetSingleton()
        
        self.peer1 = Peer(self,1234,secover1)
        self.peer2 = Peer(self,5678,secover2)
        self.peer1.start()
        self.peer2.start()
        self.wanted = False
        self.wanted2 = False
        self.got = False
        self.got2 = False
        self.first = True

        print >>sys.stderr,"test: setUp: peer1 permid is",show_permid_short(self.peer1.my_permid)
        print >>sys.stderr,"test: setUp: peer2 permid is",show_permid_short(self.peer2.my_permid)

        sleep(2) # let server threads start

    def tearDown(self):
        print >> sys.stderr,"test: tearDown: waiting 10 secs"
        sleep(10)
        if self.wanted and not self.got:
            self.assert_(False,"callback was not called")
        if self.wanted2 and not self.got2:
            self.assert_(False,"other callback was not called")
        self.peer1.shutdown()
        self.peer2.shutdown()
        sleep(5)
        try:
            shutil.rmtree(self.config_path)
        except:
            # Not fatal if something goes wrong here, and Win32 often gives
            # spurious Permission Denied errors.
            #print_exc()
            pass

    #
    # connect_dns() to an address that noone responds at
    #
    def singtest_connect_dns_to_dead_peer(self):
        print >> sys.stderr,"test: test_connect_dns_to_dead_peer"
        self.wanted = True
        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 22220),self.connect_dns_to_dead_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should fail
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def connect_dns_to_dead_peer_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_dns_to_dead_peer_callback"
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 22220))
        self.assert_(permid is None)
        self.got = True


    #
    # connect_dns() to an address that peer2 responds
    #
    def singtest_connect_dns_to_live_peer(self):
        print >> sys.stderr,"test: test_connect_dns_to_live_peer"
        self.wanted = True
        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))

    def connect_dns_to_live_peer_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_dns_to_live_peer_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # connect() to a fake permid
    #
    def singtest_connect_to_dead_peerA(self):
        print >> sys.stderr,"test: test_connect_to_dead_peer"
        self.wanted = True
        hispermid = 'blabla'
        self.peer1.secure_overlay.connect(hispermid,self.connect_to_dead_peerA_callback)
        sleep(2) # let rawserver thread establish connection, which should fail
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def connect_to_dead_peerA_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_to_dead_peer_callback"
        self.assert_(exc is not None)
        self.assert_(permid == 'blabla')
        self.got = True

    #
    # connect() to a real permid for which there is an address in the
    # database that noone responds at
    #
    def singtest_connect_to_dead_peerB(self):
        print >> sys.stderr,"test: test_connect_to_dead_peerB"
        self.wanted = True

        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid, {'ip':"127.0.0.1", 'port':22220})

        self.peer1.secure_overlay.connect(hispermid,self.connect_to_dead_peerB_callback)
        sleep(2) # let rawserver thread establish connection, which should fail
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def connect_to_dead_peerB_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_to_dead_peerB_callback",exc
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 22220))
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # connect() to peer2 which responds
    #
    def singtest_connect_to_live_peer(self):
        print >> sys.stderr,"test: test_connect_to_live_peer"
        self.wanted = True

        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})

        self.peer1.secure_overlay.connect(hispermid,self.connect_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))

    def connect_to_live_peer_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_to_live_peer_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # connect() to peer2 which responds, and then connect again
    #
    def singtest_connect_twice_to_live_peer(self):
        print >> sys.stderr,"test: test_connect_to_live_peer"
        self.wanted = True
        self.wanted2 = True
        
        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})

        self.peer1.secure_overlay.connect(hispermid,self.connect_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))
        self.peer1.secure_overlay.connect(hispermid,self.connect_to_live_peer_again_callback)

    def connect_to_live_peer_again_callback(self,exc,dns,permid,selver):
        print >> sys.stderr,"test: connect_to_live_peer_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.got2 = True


    #
    # send() over a non-existing connection to peer2
    #
    def singtest_send_unopenedA(self):
        print >> sys.stderr,"test: test_send_unopenedA"
        self.wanted = True
        hispermid = self.peer2.my_permid
        self.peer1.secure_overlay.send(hispermid,'msg=bla',self.send_unopenedA_send_callback)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def send_unopenedA_send_callback(self,exc,permid):
        print >> sys.stderr,"test: send_unopenedA_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # send() over a non-existing connection to peer2 whose address is in database
    #
    def singtest_send_unopenedB(self):
        print >> sys.stderr,"test: test_send_unopenedB"
        self.wanted = True
        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})
        self.peer1.secure_overlay.send(hispermid,'msg=bla',self.send_unopenedB_send_callback)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def send_unopenedB_send_callback(self,exc,permid):
        print >> sys.stderr,"test: send_unopenedB_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # send() over a connection to peer2 that peer1 closed
    #
    def singtest_send_local_close(self):
        print >> sys.stderr,"test: test_send_local_close"
        self.wanted = True

        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))

        hispermid = self.peer2.my_permid
        self.peer1.secure_overlay.close(hispermid)
        self.peer1.secure_overlay.send(hispermid,'msg=bla',self.send_local_close_send_callback)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def send_local_close_send_callback(self,exc,permid):
        print >> sys.stderr,"test: send_local_close_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(permid == self.peer2.my_permid)
        self.got = True

    #
    # send() over a connection to peer2 that peer2 closed
    #
    def singtest_send_remote_close(self):
        print >> sys.stderr,"test: test_send_remote_close"

        self.wanted = True
        self.wanted2 = True

        # register handler for connections
        self.peer2.secure_overlay.register_conns_callback(self.send_remote_close_conns_callback)

        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        # let rawserver thread establish connection, which should succeed
        # then let rawserver thread close connection, which should succeed
        # net result is no connection to peer2
        self.peer1.secure_overlay.send(self.peer2.my_permid,'msg=bla',self.send_remote_close_send_callback)
        sleep(2) 
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def send_remote_close_conns_callback(self,exc,permid,selversion,locally_initiated,hisdns):
        print  >> sys.stderr,"test: send_remote_close_conns_callback",exc,show_permid_short(permid)
        if self.first:
            self.assert_(exc is None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True

            hispermid = self.peer1.my_permid
            self.peer2.secure_overlay.close(hispermid)
        else:
            self.assert_(exc is not None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)

    def send_remote_close_send_callback(self,exc,permid):
        print >> sys.stderr,"test: send_remote_close_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(permid == self.peer2.my_permid)
        self.got = True


    #
    # send() over an open connection to peer2
    #
    def singtest_send_opened(self):
        print >> sys.stderr,"test: test_send_opened"
        self.wanted = True
        self.wanted2 = True
        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})
        msg = GET_METADATA+'12345678901234567890'
        self.peer1.secure_overlay.connect(hispermid,lambda e,d,p,s: self.send_opened_connect_callback(e,d,p,s,msg))

    def send_opened_connect_callback(self,exc,dns,permid,selver,msg):
        print >> sys.stderr,"test: send_opened_connect_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.peer1.secure_overlay.send(permid,msg,self.send_opened_send_callback)
        self.got = True

    def send_opened_send_callback(self,exc,permid):
        print >> sys.stderr,"test: send_opened_send_callback"
        self.assert_(exc is None)
        self.assert_(permid == self.peer2.my_permid)
        self.got2 = True


    #
    # close() a non-existing to peer2
    #
    def singtest_close_unopened(self):
        print >> sys.stderr,"test: test_close_unopened"
        hispermid = self.peer2.my_permid
        self.peer1.secure_overlay.close(hispermid)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)


    #
    # close() an open connection to peer2
    #
    def singtest_close_opened(self):
        print >> sys.stderr,"test: test_close_opened"
        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))

        hispermid = self.peer2.my_permid
        self.peer1.secure_overlay.close(hispermid)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)


    #
    # Let peer2 register an receive callback and let peer1 send a message
    #
    def singtest_receive(self):
        print >> sys.stderr,"test: test_receive"
        self.wanted = True
        self.wanted2 = True
        # register handler for messages
        self.peer2.secure_overlay.register_recv_callback(self.receive_msg_callback)

        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})
        msg = GET_METADATA+'12345678901234567890'
        self.peer1.secure_overlay.connect(hispermid,lambda e,d,p,s: self.receive_connect_callback(e,d,p,s,msg))

    def receive_connect_callback(self,exc,dns,permid,selver,msg):
        print >> sys.stderr,"test: receive_connect_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.peer1.secure_overlay.send(permid,msg,self.receive_send_callback)
        print >> sys.stderr,"test: test_receive exiting"

    def receive_send_callback(self,exc,permid):
        print >> sys.stderr,"test: receive_send_callback"
        self.assert_(exc is None)
        self.assert_(permid == self.peer2.my_permid)
        self.got2 = True

    def receive_msg_callback(self,permid,selversion,message):
        print  >> sys.stderr,"test: testcase succesfully received message"
        self.got = True
        self.assert_(message[0] == GET_METADATA)
        self.assert_(permid == self.peer1.my_permid)
        self.assert_(selversion == OLPROTO_VER_CURRENT)
        return True

    #
    # Let peer2 register an connection callback and let peer1 send a message
    # which implies setting up a connection
    #
    def singtest_got_conn_incoming(self):
        print >> sys.stderr,"test: test_got_conn_incoming"
        self.wanted = True
        self.wanted2 = True
        # register handler for messages
        self.peer2.secure_overlay.register_recv_callback(self.receive_msg_callback)
        # register handler for connections
        self.peer2.secure_overlay.register_conns_callback(self.got_conn_incoming_conns_callback)


        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})
        msg = GET_METADATA+'12345678901234567890'
        self.peer1.secure_overlay.connect(hispermid,lambda e,d,p,s:self.got_conn_incoming_connect_callback(e,d,p,s,msg))


    def got_conn_incoming_connect_callback(self,exc,dns,permid,selver,msg):
        print >> sys.stderr,"test: got_conn_incoming_connect_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.peer1.secure_overlay.send(permid,msg,self.receive_send_callback)
        print >> sys.stderr,"test: test_got_conn_incoming exiting"

    def got_conn_incoming_conns_callback(self,exc,permid,selversion,locally_initiated,hisdns):
        print  >> sys.stderr,"test: got_conn_incoming_conns_callback",exc,show_permid_short(permid)
        self.assert_(exc is None)
        self.assert_(permid == self.peer1.my_permid)
        self.assert_(selversion == OLPROTO_VER_CURRENT)
        self.assert_(not locally_initiated)
        self.got = True


    #
    # Let peer1 register an connection callback and let peer1 send a message
    # which implies setting up a connection
    #
    def singtest_got_conn_outgoing(self):
        print >> sys.stderr,"test: test_got_conn_outgoing"
        self.wanted = True
        self.wanted2 = True
        # register handler for connections
        self.peer1.secure_overlay.register_conns_callback(self.got_conn_outgoing_conns_callback)

        peer_db = PeerDBHandler.getInstance()
        hispermid = self.peer2.my_permid
        peer_db.addPeer(hispermid,{'ip':"127.0.0.1", 'port':5678})
        msg = GET_METADATA+'12345678901234567890'
        self.peer1.secure_overlay.connect(hispermid,lambda e,d,p,s:self.got_conn_outgoing_connect_callback(e,d,p,s,msg))


    def got_conn_outgoing_connect_callback(self,exc,dns,permid,selver,msg):
        print >> sys.stderr,"test: got_conn_outgoing_connect_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.assert_(permid == self.peer2.my_permid)
        self.got2 = True

    def got_conn_outgoing_conns_callback(self,exc,permid,selversion,locally_initiated,hisdns):
        print  >> sys.stderr,"test: got_conn_outgoing_conns_callback",exc,show_permid_short(permid)
        self.assert_(exc is None)
        self.assert_(permid == self.peer2.my_permid)
        self.assert_(selversion == OLPROTO_VER_CURRENT)
        self.assert_(locally_initiated)
        self.got = True



    #
    # Let peer2 register a connection callback and let peer1 close the connection
    # after succesful setup.
    #
    def singtest_got_conn_local_close(self):
        print >> sys.stderr,"test: test_got_conn_local_close"

        self.wanted = True
        self.wanted2 = True

        # register handler for connections
        self.peer2.secure_overlay.register_conns_callback(self.got_conn_local_close_conns_callback)

        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 1)
        self.assert_(self.peer1.secure_overlay.iplport2oc.has_key('127.0.0.1:5678'))

        hispermid = self.peer2.my_permid
        self.peer1.secure_overlay.close(hispermid)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)


    def got_conn_local_close_conns_callback(self,exc,permid,selversion,locally_initiated,hisdns):
        print  >> sys.stderr,"test: got_conn_local_close_conns_callback",exc,show_permid_short(permid)
        if self.first:
            self.assert_(exc is None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True
        else:
            self.assert_(exc is not None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)
            self.got = True

    #
    # Let peer2 register a connection callback and let peer2 close the connection
    # after succesful setup.
    #
    def singtest_got_conn_remote_close(self):
        print >> sys.stderr,"test: test_got_conn_remote_close"

        self.wanted = True
        self.wanted2 = True

        # register handler for connections
        self.peer2.secure_overlay.register_conns_callback(self.got_conn_remote_close_conns_callback)

        self.peer1.secure_overlay.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        # let rawserver thread establish connection, which should succeed
        # then let rawserver thread close connection, which should succeed
        # net result is no connection to peer2
        sleep(2) 
        self.assert_(len(self.peer1.secure_overlay.iplport2oc) == 0)

    def got_conn_remote_close_conns_callback(self,exc,permid,selversion,locally_initiated,hisdns):
        print  >> sys.stderr,"test: got_conn_remote_close_conns_callback",exc,show_permid_short(permid)
        if self.first:
            self.assert_(exc is None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True

            hispermid = self.peer1.my_permid
            self.peer2.secure_overlay.close(hispermid)
        else:
            self.assert_(exc is not None)
            self.assert_(permid == self.peer1.my_permid)
            self.assert_(selversion == OLPROTO_VER_CURRENT)
            self.assert_(not locally_initiated)
            self.got = True

    def rawserver_fatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"test_secure_overlay: RawServer fatal error func called",e
        print_exc()
        self.assert_(False)


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_so.py <method name>"
    else:
        suite.addTest(TestSecureOverlay(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
