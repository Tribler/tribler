# Written by Arno Bakker
# see LICENSE.txt for license information
#
# This test checks the new ReturnConnHandler class created in Fall 2006
#
# Note that we start a new Python interpreter for each test case.
# Also note we create 2 peers and thus two networking stacks. In principle, 
# they should use two different ReturnConnHandler instances (not a singleton), but 
# there may be some interference.
# 
# To properly follow the test, enable debugging on BitTornado/SocketHandler,
# BitTornado/ServerPortHandler and BitTornado/Rawserver in addition to
# Tribler/NATFirewall/ReturnConnHandler
#
#

import sys
import unittest
from threading import Event, Thread, currentThread
from socket import error as socketerror
from time import sleep

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.BitTornado.ServerPortHandler import MultiHandler
from Tribler.Core.BitTornado.BT1.MessageID import DIALBACK_REQUEST

from Tribler.Core.NATFirewall.ReturnConnHandler import ReturnConnHandler

# Thread must come as first parent class!
class Peer(Thread):
    def __init__(self,testcase,port):
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
        self.dialback_connhand = ReturnConnHandler.getInstance()
        self.dialback_connhand.resetSingleton()

        self.dialback_connhand.register(self.rawserver,self.multihandler,self.listen_port,config['max_message_length'])
        self.rawserver.sockethandler.set_handler(self.dialback_connhand)
        self.dialback_connhand.start_listening()

        # Stupid rawserver goes into very long wait if there are no short
        # term tasks. Emulate this
        self.rawserver.add_task(self.dummy_task,0)

    def run(self):
        print >> sys.stderr,"test: MyServer: run called by",currentThread().getName()
        self.multihandler.listen_forever()

    def report_failure(self,msg):
        self.testcase.assertRaises(Exception, self.report_failure)

    def report_error(self,msg):
        self.testcase.assertRaises(Exception, self.report_error)

    def dummy_task(self):
        self.rawserver.add_task(self.dummy_task,1)

    def shutdown(self):
        self.doneflag.set()
        self.rawserver.shutdown()


class TestReturnConnHandler(unittest.TestCase):
    
    def setUp(self):
        self.peer1 = Peer(self,1234)
        self.peer2 = Peer(self,5678)
        self.peer1.start()
        self.peer2.start()
        self.wanted = False
        self.wanted2 = False
        self.got = False
        self.got2 = False
        self.first = True

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

    #
    # connect_dns() to an address that noone responds at
    #
    def singtest_connect_dns_to_dead_peer(self):
        print >> sys.stderr,"test: test_connect_dns_to_dead_peer"
        self.wanted = True
        self.peer1.dialback_connhand.connect_dns(("127.0.0.1", 22220),self.connect_dns_to_dead_peer_callback)
        # Arno, 2009-04-23: was 2 secs, somehow the failed event comes in real slow now.
        sleep(4) # let rawserver thread establish connection, which should fail
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)

    def connect_dns_to_dead_peer_callback(self,exc,dns):
        print >> sys.stderr,"test: connect_dns_to_dead_peer_callback"
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 22220))
        self.got = True


    #
    # connect_dns() to an address that peer2 responds
    #
    def singtest_connect_dns_to_live_peer(self):
        print >> sys.stderr,"test: test_connect_dns_to_live_peer"
        self.wanted = True
        self.peer1.dialback_connhand.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 1)
        self.assert_(self.peer1.dialback_connhand.iplport2oc.has_key('127.0.0.1:5678'))

    def connect_dns_to_live_peer_callback(self,exc,dns):
        print >> sys.stderr,"test: connect_dns_to_live_peer_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got = True


    #
    # send() over a non-existing connection to peer2
    #
    def singtest_send_unopenedA(self):
        print >> sys.stderr,"test: test_send_unopenedA"
        self.wanted = True
        hisdns = ("127.0.0.1", 5678)
        self.peer1.dialback_connhand.send(hisdns,'msg=bla',self.send_unopenedA_send_callback)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)

    def send_unopenedA_send_callback(self,exc,dns):
        print >> sys.stderr,"test: send_unopenedA_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got = True

    #
    # send() over a connection to peer2 that peer1 closed
    #
    def singtest_send_local_close(self):
        print >> sys.stderr,"test: test_send_local_close"
        self.wanted = True

        self.peer1.dialback_connhand.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 1)
        self.assert_(self.peer1.dialback_connhand.iplport2oc.has_key('127.0.0.1:5678'))

        hisdns = ("127.0.0.1", 5678)
        self.peer1.dialback_connhand.close(hisdns)
        self.peer1.dialback_connhand.send(hisdns,'msg=bla',self.send_local_close_send_callback)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)

    def send_local_close_send_callback(self,exc,dns):
        print >> sys.stderr,"test: send_local_close_send_callback",exc
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got = True

    #
    # send() over a connection to peer2 that peer2 closed
    #
    def singtest_send_remote_close(self):
        print >> sys.stderr,"test: test_send_remote_close"

        self.wanted = True
        self.wanted2 = True

        # register handler for connections
        self.peer2.dialback_connhand.register_conns_callback(self.send_remote_close_conns_callback)

        hisdns = ("127.0.0.1", 5678)
        # peer2 will immediately the close connection
        # (for SecureOverlay there are message exchanges, so behaviour is different)
        self.peer1.dialback_connhand.connect_dns(hisdns,self.send_remote_close_connect_callback)
        sleep(2)
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)

    def send_remote_close_conns_callback(self,exc,dns,locally_initiated):
        print  >> sys.stderr,"test: send_remote_close_conns_callback",exc,dns
        hisdns = ("127.0.0.1", 1234)
        if self.first:
            print >>sys.stderr,"test: send_remote_close_conns_callback: FIRST:"
            self.assert_(exc is None)
            self.assert_(dns == hisdns)
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True

            print >>sys.stderr,"test: send_remote_close_conns_callback: FIRST: BEFORE CLOSE"
            self.peer2.dialback_connhand.close(hisdns)
        else:
            print >>sys.stderr,"test: send_remote_close_conns_callback: SECOND"
            self.assert_(exc is not None)
            self.assert_(dns == hisdns)
            self.assert_(not locally_initiated)

    def send_remote_close_connect_callback(self,exc,dns):
        print >> sys.stderr,"test: send_remote_close_connect_callback"
        self.assert_(exc is not None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got = True


    #
    # send() over an open connection to peer2
    #
    def singtest_send_opened(self):
        print >> sys.stderr,"test: test_send_opened"
        self.wanted = True
        self.wanted2 = True
        hisdns = ("127.0.0.1", 5678)
        msg = DIALBACK_REQUEST+'12345678901234567890'
        self.peer1.dialback_connhand.connect_dns(hisdns,lambda e,d: self.send_opened_connect_callback(e,d,msg))

    def send_opened_connect_callback(self,exc,dns,msg):
        print >> sys.stderr,"test: send_opened_connect_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.peer1.dialback_connhand.send(dns,msg,self.send_opened_send_callback)
        self.got = True

    def send_opened_send_callback(self,exc,dns):
        print >> sys.stderr,"test: send_opened_send_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got2 = True


    #
    # close() a non-existing to peer2
    #
    def singtest_close_unopened(self):
        print >> sys.stderr,"test: test_close_unopened"
        hisdns = ("127.0.0.1", 5678)
        self.peer1.dialback_connhand.close(hisdns)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)


    #
    # close() an open connection to peer2
    #
    def singtest_close_opened(self):
        print >> sys.stderr,"test: test_close_opened"
        hisdns = ("127.0.0.1", 5678)
        self.peer1.dialback_connhand.connect_dns(hisdns,self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 1)
        self.assert_(self.peer1.dialback_connhand.iplport2oc.has_key('127.0.0.1:5678'))

        self.peer1.dialback_connhand.close(hisdns)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)


    #
    # Let peer2 register an receive callback and let peer1 send a message
    #
    def singtest_receive(self):
        print >> sys.stderr,"test: test_receive"
        self.wanted = True
        self.wanted2 = True
        # register handler for messages
        self.peer2.dialback_connhand.register_recv_callback(self.receive_msg_callback)

        hisdns = ("127.0.0.1", 5678)
        msg = DIALBACK_REQUEST+'12345678901234567890'
        self.peer1.dialback_connhand.connect_dns(hisdns,lambda e,d: self.receive_connect_callback(e,d,msg))

    def receive_connect_callback(self,exc,dns,msg):
        print >> sys.stderr,"test: receive_connect_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.peer1.dialback_connhand.send(dns,msg,self.receive_send_callback)
        print >> sys.stderr,"test: test_receive exiting"

    def receive_send_callback(self,exc,dns):
        print >> sys.stderr,"test: receive_send_callback"
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got2 = True

    def receive_msg_callback(self,dns,message):
        print  >> sys.stderr,"test: testcase succesfully received message"
        self.got = True
        self.assert_(message[0] == DIALBACK_REQUEST)
        self.assert_(dns == ("127.0.0.1", 1234))
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
        self.peer2.dialback_connhand.register_recv_callback(self.receive_msg_callback)
        # register handler for connections
        self.peer2.dialback_connhand.register_conns_callback(self.got_conn_incoming_conns_callback)


        hisdns = ("127.0.0.1", 5678)
        msg = DIALBACK_REQUEST+'12345678901234567890'
        self.peer1.dialback_connhand.connect_dns(hisdns,lambda e,d:self.got_conn_incoming_connect_callback(e,d,msg))


    def got_conn_incoming_connect_callback(self,exc,dns,msg):
        print >> sys.stderr,"test: got_conn_incoming_connect_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.peer1.dialback_connhand.send(dns,msg,self.receive_send_callback)
        print >> sys.stderr,"test: test_got_conn_incoming exiting"

    def got_conn_incoming_conns_callback(self,exc,dns,locally_initiated):
        print  >> sys.stderr,"test: got_conn_incoming_conns_callback",dns
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 1234))
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
        self.peer1.dialback_connhand.register_conns_callback(self.got_conn_outgoing_conns_callback)

        hisdns = ("127.0.0.1", 5678)
        msg = DIALBACK_REQUEST+'12345678901234567890'
        self.peer1.dialback_connhand.connect_dns(hisdns,lambda e,d:self.got_conn_outgoing_connect_callback(e,d,msg))


    def got_conn_outgoing_connect_callback(self,exc,dns,msg):
        print >> sys.stderr,"test: got_conn_outgoing_connect_callback",exc
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
        self.got2 = True

    def got_conn_outgoing_conns_callback(self,exc,dns,locally_initiated):
        print  >> sys.stderr,"test: got_conn_outgoing_conns_callback",exc,dns
        self.assert_(exc is None)
        self.assert_(dns == ("127.0.0.1", 5678))
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
        self.peer2.dialback_connhand.register_conns_callback(self.got_conn_local_close_conns_callback)

        self.peer1.dialback_connhand.connect_dns(("127.0.0.1", 5678),self.connect_dns_to_live_peer_callback)
        sleep(2) # let rawserver thread establish connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 1)
        self.assert_(self.peer1.dialback_connhand.iplport2oc.has_key('127.0.0.1:5678'))

        hisdns = ("127.0.0.1", 5678)
        self.peer1.dialback_connhand.close(hisdns)
        sleep(2) # let rawserver thread close connection, which should succeed
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)


    def got_conn_local_close_conns_callback(self,exc,dns,locally_initiated):
        print  >> sys.stderr,"test: got_conn_local_close_conns_callback",exc,dns
        if self.first:
            self.assert_(exc is None)
            self.assert_(dns == ("127.0.0.1", 1234))
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True
        else:
            self.assert_(exc is not None)
            self.assert_(dns == ("127.0.0.1", 1234))
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
        self.peer2.dialback_connhand.register_conns_callback(self.got_conn_remote_close_conns_callback)

        # peer2 will immediately the close connection
        # (for SecureOverlay there are message exchanges, so behaviour is different)
        self.peer1.dialback_connhand.connect_dns(("127.0.0.1", 5678),self.send_remote_close_connect_callback)
        sleep(2)
        self.assert_(len(self.peer1.dialback_connhand.iplport2oc) == 0)


    def got_conn_remote_close_conns_callback(self,exc,dns,locally_initiated):
        print  >> sys.stderr,"test: got_conn_remote_close_conns_callback",exc,dns
        if self.first:
            self.assert_(exc is None)
            self.assert_(dns == ("127.0.0.1", 1234))
            self.assert_(not locally_initiated)
            self.first = False
            self.got2 = True

            hisdns = ("127.0.0.1", 1234)
            self.peer2.dialback_connhand.close(hisdns)
        else:
            self.assert_(exc is not None)
            self.assert_(dns == ("127.0.0.1", 1234))
            self.assert_(not locally_initiated)
            self.got = True



def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_so.py <method name>"
    else:
        suite.addTest(TestReturnConnHandler(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
