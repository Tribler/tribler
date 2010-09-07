# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements the SSDP deamon of a UPnP control point.
"""
import time
import uuid as uuid_module
import ssdpmessage
import ssdpdaemon

_LOG_TAG = "SSDPClient"

##############################################
# SSDP CLIENT DAEMON
##############################################

class SSDPClient(ssdpdaemon.SSDPDaemon):

    """
    This implements the SSDP deamon of UPnP control points.
    
    This class is implemented in a non-blocking, event-based manner.
    Execution is outsourced to the given task_runner.
    """

    def __init__(self, task_runner, logger=None):

        ssdpdaemon.SSDPDaemon.__init__(self, task_runner, logger)

        # Devices
        self._ssdp_devices = {} # uuid : SSDPDevice

        # Event Handlers
        self._add_handler = lambda uuid: None
        self._remove_handler = lambda uuid: None

    ##############################################
    # PUBLIC API
    ##############################################


    def set_add_handler(self, handler):
        """Add handler is executed whener a device is added."""
        self._add_handler = handler

    def set_remove_handler(self, handler):
        """Remove handler is executed whener a device is removed."""
        self._remove_handler = handler

    def get_ssdp_device(self, uuid):
        """Given a uuid, get reference to the local representation of a
        remote SSDP root device."""
        return self._ssdp_devices.get(uuid, None)

    def search(self, target="upnp:rootdevice"):
        """Multicast a SSDP search for root devices on the local network. """
        msg = ssdpmessage.SearchMessage()
        msg.init(max_delay=3, st=target)
        self.multicast(msg)

    def close(self):
        """Close sockets and cancel tasks."""
        ssdpdaemon.SSDPDaemon.close(self)
        for device in self._ssdp_devices.values():
            device.close()

    ##############################################
    # OVERRIDE HANDLERS
    ##############################################

    def startup(self):
        """Extending Startup by adding Search."""
        ssdpdaemon.SSDPDaemon.startup(self)
        self.search()

    def handle_search(self, msg, sock_addr):
        """Handlers the receipt of a SSDP Search message."""
        self.log("IGNORE %s from %s" % (msg.type, sock_addr))

    def handle_reply(self, msg, sock_addr):
        """Handles the receipt of a SSDP Reply message."""
        self._handle_announce_or_reply(msg, sock_addr)

    def handle_announce(self, msg, sock_addr):
        """Handles the receipt of a SSDP Announce message."""
        self._handle_announce_or_reply(msg, sock_addr)

    def _handle_announce_or_reply(self, msg, sock_addr):
        """Handles the receipt of a SSDP Announce message
        or a SSDP Reply message."""
        # uuid
        tokens = msg.usn.split(":")
        if len(tokens) != 5:
            # use only those announce messages that has a specific
            # structure :
            # "uuid:<uuid>::upnp:rootdevice"
            self.log("IGNORE %s [%s]" % (msg.type, sock_addr[0]))
            return
        uuid = uuid_module.UUID(tokens[1])
        # renew
        if self._ssdp_devices.has_key(uuid):
            self._renew_device(uuid, msg.max_age)
        # new
        else:
            # target
            if isinstance(msg, ssdpmessage.ReplyMessage):
                target = msg.st
            elif isinstance(msg, ssdpmessage.AnnounceMessage):
                target = msg.nt
            ssdp_device = SSDPDevice(self.task_runner,
                                     uuid, msg.max_age, 
                                     msg.location, target, 
                                     msg.osversion, 
                                     msg.productversion)
            self._add_device(ssdp_device)

    def handle_unannounce(self, msg, sock_addr):
        """Handles the receipt of a SSDP UnAnnounce message."""
        # Handle UnAnnounces for root devices exclusively.
        # usn = "uuid:73721e4e-0a84-4985-97e2-974b2c50323b"
        tokens = msg.usn.split(":")
        if len(tokens) != 2:
            self.log("IGNORE %s [%s]" % (msg.type, sock_addr[0]))
            return
        uuid = uuid_module.UUID(tokens[1])
        self._remove_device(uuid)


    ##############################################
    # PRIVATE UTILITY
    ##############################################
       
    def _handle_expiry(self, uuid):
        """A device has expired, causing it to be removed."""
        self._remove_device(uuid)

    def _add_device(self, ssdp_device):
        """Add new SSDP root device."""
        uuid = ssdp_device.uuid
        self._ssdp_devices[uuid] = ssdp_device
        ssdp_device.set_expiry_handler(self._handle_expiry)
        self.log("ADD [%d] %s" % (ssdp_device.max_age, uuid))
        # Publish Event ADD
        self.task_runner.add_task(self._add_handler, 
                                  args=(uuid,ssdp_device.location))

    def _renew_device(self, uuid, max_age):
        """Receive announce from already known device."""
        self._ssdp_devices[uuid].alive(max_age)
        self.log("ALIVE [%d] %s" % (max_age, uuid))
        
    def _remove_device(self, uuid):
        """Remove device."""
        if self._ssdp_devices.has_key(uuid):
            del self._ssdp_devices[uuid]
            self.log("REMOVE %s" % (uuid))
            # Publish Event REMOVE            
            self.task_runner.add_task(self._remove_handler, 
                                      args=(uuid,))


##############################################
# SSDP DEVICE
##############################################

class SSDPDevice:

    """This represents a local view of a remote SSDP root device."""

    def __init__(self, task_runner, 
                 uuid, max_age, location, search_target, 
                 os_version, product_version):

        self.uuid = uuid
        self.location = location
        self.search_target = search_target
        self.os_version = os_version
        self.product_version = product_version
        self.max_age = max_age
        self.expiry = None
        self._expired = False

        self._task_runner = task_runner
        self._expiry_handler = lambda uuid: None
        self._task = None
        self._new_timeout(max_age)

    # Private Methods

    def _new_timeout(self, max_age):
        """Register a new liveness timeout for device."""
        # Cancel old timeout.
        if self._task:
            self._task.cancel()
        # Update expire
        self.expiry = time.time() + max_age
        # Create new timeout
        self._task = self._task_runner.add_delay_task(
            max_age, self._handle_timeout)
        
    def _handle_timeout(self):
        """Timeout handler."""
        self._expired = True
        self._expiry_handler(self.uuid)

    # Public Methods

    def set_expiry_handler(self, handler):
        """Set handler to be executed whenever device has been
        timed out without any signs of liveness."""
        self._expiry_handler = handler

    def alive(self, max_age):
        """Invoked whenever a signal is received that 
        suggests that the remote device is live and well."""
        self._new_timeout(max_age)

    def is_alive(self):
        """Check if device is alive (local view)."""
        return not self._expired

    def close(self):
        """Cancel timeout task associated with device, if any. """
        if self._task:
            self._task.cancel()
        

##############################################
# MAIN
##############################################

if __name__ == "__main__":
    

    class TestClient:
        """TestClient wraps SSDPClient to add some event handlers."""

        def __init__(self, ssdp_client):
            self._ssdp_client = ssdp_client
            self._ssdp_client.set_add_handler(self.add_handler)
            self._ssdp_client.set_remove_handler(self.remove_handler)

        def add_handler(self, uuid, location):
            """Executed when device with given uuid has been added."""
            print "ADD %s %s" % (uuid, location)

        def remove_handler(self, uuid):
            """Executed when device with given uuid has been removed."""
            print "REMOVE %s" % uuid

    class MockLogger:
        """Mockup Logger object."""
        def __init__(self):
            pass
        def log(self, log_tag, msg):
            """Log to std out."""
            print log_tag, msg

    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()
    CLIENT = SSDPClient(TR, MockLogger())
    TEST = TestClient(CLIENT)
    TR.add_task(CLIENT.startup)
    try:
        TR.run_forever()
    except KeyboardInterrupt:
        print
        CLIENT.close()
