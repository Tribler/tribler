# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""
This unittest runs the UPnPServer and the UPnPClient in a single thread.
The UPnPServer is extended with a couple of simple services.
The tests then revolve arount using the UPnPClient to discover and
interact with the services defined by the UPnPServer.
"""
import time
import unittest
import threading

from Tribler.UPnP.common.taskrunner import TaskRunner
from Tribler.UPnP.upnpserver.upnpserver import UPnPServer
from Tribler.UPnP.upnpclient.upnpclient import UPnPClient
from Tribler.UPnP.services import SwitchPower, URLService
from Tribler.UPnP import SERVER_PRODUCT_NAME
from Tribler.UPnP import SERVER_ROOT_DEVICE_CONFIG

##############################################
# EVENT RECEIVER
##############################################

class _EventReceiver:
    """
    Dummy Event receiver that always holds the last event
    it received.
    """
    def __init__(self):
        self._args = (None, None, None)
    def handler(self, *args):
        """Invoked when event is delivered."""
        self._args = args
    def get_last_event(self):
        """Get the state of the last event."""
        return self._args


##############################################
# UPNP TEST CASE
##############################################
 
class UPnPTestCase(unittest.TestCase):

    """TestCase for UPnPServer and UPnPClient."""

    def setUp(self):
        """Set up test environment."""
        self._tr = TaskRunner()
        self.server = UPnPServer(self._tr, 
                            SERVER_PRODUCT_NAME,
                            SERVER_ROOT_DEVICE_CONFIG)

        self.service1 = SwitchPower("SwitchPower")
        self.service2 = URLService("URLService")
        self.server.add_service(self.service1)
        self.server.add_service(self.service2)

        self.client = UPnPClient(self._tr)
        self.thread = threading.Thread(target=self._tr.run_forever)
        self.thread.start()
        time.sleep(0.1) # wait for client to discover server

    def tearDown(self):
        """Clean up test environment."""
        self.client.close()
        self.server.close()
        self._tr.stop()
        self.thread.join()

    def test_device_discovery(self):
        """
        Test if UPnPClient is able to discover the UPnPDevice
        hosted by UPnPServer.
        """
        root = self.server.get_root_device()
        self.assertTrue( root.uuid in self.client.get_device_uuids())

    def test_switchpower(self):
        """Test discovery and use of SwitchPowerService."""

        stub = self.client.get_services_by_short_id("SwitchPower")[0]

        # Test service_id
        self.assertEqual(self.service1.get_service_id(), 
                         stub.get_service_id())
        # Test service_type
        self.assertEqual(self.service1.get_service_type(), 
                         stub.get_service_type())

        # Subscribe
        evr = _EventReceiver()
        stub.subscribe(evr.handler)

        # Update SwitchPowerService by using Stub.
        value = stub.GetStatus()
        stub.SetTarget(not value)
        new_value = stub.GetStatus()
        self.assertEqual(not value, new_value, 
                         evr.get_last_event()[2])

        # Update SwitchPowerService directly.
        self.service1.set_target(not new_value)
        time.sleep(0.1) # wait for notification
        self.assertEqual(not new_value, evr.get_last_event()[2])

        # Unsubscribe
        stub.unsubscribe(evr.handler)

    def test_urlservice(self):
        """Test discovery and use of URLService."""
        stub = self.client.get_services_by_short_id("URLService")[0]
        
        # Subscribe
        evr = _EventReceiver()
        stub.subscribe(evr.handler)
   
        # Update URLService by using Stub.
        stub.GetURL()
        new_url = "http://p2p-next.org"
        stub.SetURL(new_url)
        service_url = self.service2.get_url()
        url = stub.GetURL()
        self.assertEqual(new_url, service_url, url)
        self.assertEqual(url, evr.get_last_event()[2])

        # Update URLService directly
        url2 = "http://itek.norut.no"
        self.service2.set_url(url2)
        time.sleep(0.1) # wait for notification
        self.assertEqual(url2, evr.get_last_event()[2])

        # Unsubscribe
        stub.unsubscribe(evr.handler)


##############################################
# MAIN
##############################################

if __name__ == "__main__":
    unittest.main()
















    
