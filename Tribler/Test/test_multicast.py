# Written by Njaal Borch
# see LICENSE.txt for license information
#

# Arno, 2009-04-16: 
# - You should also test whether Tribler responds correctly to multicast 
#   messages sent directly from a socket, and not via your code.
#
# - Some IPv6 tests will fail on Win32 if IPv6 is not installed.
#
#

import unittest
import tempfile
import select

from Tribler.Core.Multicast import *


#class MyLoggerTest(unittest.TestCase):
class DoNotRunThisNow:

    """
    Test the MyLogger class
    
    """

    def setUp(self):
        self.log = MyLogger()
        self.conn = BTConnection('localhost',self.hisport)

    def testLog(self):

        self.log.debug("DEBUG message")

        self.log.info("INFO message")

        self.log.warning("WARNING message")

        self.log.fatal("FATAL message")

        try:
            raise Exception("Exception text")
        except:
            self.log.exception("Should have a traceback below here:")


class FakeOverlayBridge:
    def add_task(self, function, data):
        function()

class FakePeerDBHandler:
    
    def addPeer(self,permid,peer_data,update_dns=True,update_connected=True,commit=True):
        pass
    
    def setPeerLocalFlag(permid,is_local):
        pass
    

class TestUDPServer(threading.Thread):

    def __init__(self, socket, mc_channel):
        threading.Thread.__init__(self)
        
        self.socket = socket
        self.mc_channel = mc_channel
        self.running = True
        
    def run(self):
        
        while self.running:
            try:
                if select.select([self.socket],[],[], 1)[0]:
                    (data, addr) = self.socket.recvfrom(1500)
                    self.mc_channel.data_came_in(addr, data)
            except Exception,e:
                print e
                

    def stop(self):
        self.running = False
    

class MulticastTest(unittest.TestCase):

    """
    Test multicast class

    """
    
    def __init__(self, param):
        unittest.TestCase.__init__(self, param)
        
        #TestAsServer.__init__(self, param)
        self.test_server = None
        self.overlay_bridge = FakeOverlayBridge()
        self.peer_db = FakePeerDBHandler()
        
    def prepare_test(self, config, capabilitites=None):
        """
        Cannot be done by setUp as we need special config
        """

        self.multicast = Multicast(config, self.overlay_bridge, 1234, 1, self.peer_db,
                                   capabilities=capabilitites)
        
        self.test_server = TestUDPServer(self.multicast.getSocket(),
                                         self.multicast)
        self.test_server.start()
        
    def tearDown(self):
        if self.test_server is not None:
            self.test_server.stop()
        self.multicast = None
        
        
    def testIPv4(self):

        # Dummy config
        config = {'permid':'123',
                  'hostname':'myhostname',
                  'port':'1234',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_enabled':True,
                  'multicast_ipv4_enabled':True,
                  'multicast_ipv6_enabled':False,
                  'multicast_announce':True}
        
        self.prepare_test(config)
        
        failed = True
        seen = 0
        for (permid, addr, capabilities) in self.multicast.discoverNodes():
            if permid == '123':
                failed = False
        if failed:
            raise Exception("Didn't discover myself using IPv4")

    
    def testIPv6(self):

        # Dummy config
        config = {'permid':'123',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_enabled':True,
                  'multicast_ipv4_enabled':False,
                  'multicast_ipv6_enabled':True,
                  'multicast_announce':True}
        
        self.prepare_test(config)
        failed = True
        for (permid, addr, capabilities) in self.multicast.discoverNodes():
            if permid == '123':
                failed = False
        if failed:
            raise Exception("Didn't discover myself using IPv6")

    def testBoth(self):

        # Dummy config
        config = {'permid':'123',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_enabled':True,
                  'multicast_ipv4_enabled':True,
                  'multicast_ipv6_enabled':True,
                  'multicast_announce':True}
        
        self.prepare_test(config)

        seen = 0
        for (permid, addr, capabilities) in self.multicast.discoverNodes():
            if permid == '123':
                seen += 1
        if seen < 2:
            raise Exception("Didn't discover myself enough using both (saw me %d times, expected 2)"%seen)

    def testAllDisabled(self):

        # Dummy config
        config = {'permid':'123',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_ipv4_enabled':False,
                  'multicast_ipv6_enabled':False,
                  'multicast_announce':True}
        
        self.prepare_test(config)

        try:
            if len(self.multicast.discoverNodes()) > 0:
                raise Exception("Discovered nodes even though multicast is not allowed")
        except:
            # Expected
            pass


    def testAnnounce(self):

        # Dummy config
        config = {'permid':'123',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_enabled':True,
                  'multicast_ipv4_enabled':True,
                  'multicast_ipv6_enabled':True,
                  'multicast_announce':True}
        
        self.prepare_test(config)

        # Handle the announce
        self.announces = []
        self.multicast.addAnnounceHandler(self.handleAnnounce)
        self.multicast.sendAnnounce(['elem1','elem2'])

        # Wait for asynchronous handling
        time.sleep(2.0)

        for announce in self.announces:
            if announce == ['123', 'elem1', 'elem2']:
                return # Got it

        raise Exception("Failed to get announce")
 
    def handleAnnounce(self, permid, addr, list):

        """
        Handle announce callback function
        """
        self.announces.append([permid] + list)

    def testCapabilities(self):
        """
        Test capabilities thingy
        """

        myCapabilities = ["Something", "something else", "something totally different"]
        
        # Dummy config
        config = {'permid':'testCapabilities',
                  'multicast_ipv4_address':'224.0.1.43',
                  'multicast_ipv6_address':'ff02::4124:1261:ffef',
                  'multicast_port':'6124',
                  'multicast_enabled':True,
                  'multicast_ipv4_enabled':False,
                  'multicast_ipv6_enabled':True,
                  'multicast_announce':True}
        
        self.prepare_test(config, myCapabilities)

        failed = True
        for (permid, addr, capabilities) in self.multicast.discoverNodes():
            if permid == config['permid']:
                failed = False
                if capabilities != myCapabilities:
                    raise Exception("Got bad capabilities, got %s, expected %s"%(str(capabilities), str(myCapabilities)))
                
        if failed:
            raise Exception("Didn't discover myself using IPv6")
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MulticastTest))
    
    return suite


        
if __name__ == "__main__":

    # TODO: Multicast does gives us multiple hits for ourselves, is that ok?

    print "Testing the Multicast classes"

    unittest.main()

    print "All done"

