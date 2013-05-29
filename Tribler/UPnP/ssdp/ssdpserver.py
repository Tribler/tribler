# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements the SSDP Server deamon,
part of the UPnP archictecture.
"""
import ssdpmessage
import ssdpdaemon

# SSDP Message Configuration

_ROOT_CONF_TEMPL = {
    'target': "upnp:rootdevice",
    'usn': "uuid:%(uuid)s::upnp:rootdevice",
}

_DEVICE_CONF_TEMPL_1 = {
    'target': "uuid:%(uuid)s",
    'usn': "uuid:%(uuid)s",
}

_DEVICE_CONF_TEMPL_2 = {
    'target': "urn:%(device_domain)s:device:" +
        "%(device_type)s:%(device_version)s",
    'usn': "uuid:%(uuid)s::urn:%(device_domain)s:device:" +
        "%(device_type)s:%(device_version)s",
}

_SERVICE_CONF_TEMPL = {
    'target': "urn:schemas-upnp-org:service:" +
        "%(service_type)s:%(service_version)s",
    'usn': "uuid:%(uuid)s::urn:schemas-upnp-org:service:" +
        "%(service_type)s:%(service_version)s",
}

_MAX_DELAY = 4
_MAX_AGE = 1800
_REANNOUNCE_AGE = _MAX_AGE * 0.9
_SSDP_SERVER_CONFIG = {
    'max_delay': _MAX_DELAY,
    'max_age': _MAX_AGE,
    }

_LOG_TAG = "SSDPServer"


def _create_msg_config(config_template, kwargs):
    """Create a single message config dict from a template and
    some keywords."""
    return {
        'target': config_template['target'] % kwargs,
        'usn': config_template['usn'] % kwargs
        }


def _create_msg_configs(root_device):
    """Create all message configs for all devices and services."""
    # Expect rootdevice to be the root of a dictionary hierarchy,
    # representing the nested organisation of devices and services.
    # Create 1 special message config for root device
    configs = [_create_msg_config(_ROOT_CONF_TEMPL, root_device.__dict__)]
    # Walk the device/service hierarchy (incl. rootdevice)
    device_queue = [root_device]
    while device_queue:
        device = device_queue.pop()
        # Iterate recursively over all devices (top-down/breath-first)
        device_queue += device.get_devices()
        # Create two messages configs per device
        conf_1 = _create_msg_config(_DEVICE_CONF_TEMPL_1, device.__dict__)
        conf_2 = _create_msg_config(_DEVICE_CONF_TEMPL_2, device.__dict__)
        configs += [conf_1, conf_2]
        # Create one message config per service in device
        # todo : should really only create one message per service type
        for service in device.get_services():
            service.uuid = device.uuid
            conf = _create_msg_config(_SERVICE_CONF_TEMPL, service.__dict__)
            configs.append(conf)
    return configs


def _initialise_message(ssdp_config, msg):
    """Utility method for initialising SSDP messages with common data."""
    msg.init(
        location=ssdp_config['location'],
        osversion=ssdp_config['osversion'],
        productversion=ssdp_config['productversion'],
        max_age=ssdp_config['max_age']
        )
    return msg


#
# SSDP SERVER
#

class SSDPServer(ssdpdaemon.SSDPDaemon):

    """
    This implements the SSDP server deamon, part of the UPnP architecture.

    This class is implemented in a non-blocking, event-based manner.
    Execution is outsourced to the given task_runner.
    """

    def __init__(self, task_runner, logger=None):
        ssdpdaemon.SSDPDaemon.__init__(self, task_runner, logger)
        # Service Manager
        self._sm = None
        # Announce Timeout Task
        self._timeout_task = None

        self._root_device = None
        self._config = None

    def set_service_manager(self, service_manager):
        """The service manger initialises SSDPServer with a
        reference to itself."""
        self._sm = service_manager

    #
    # PRIVATE PROTOCOL OPERATIONS
    #

    def startup(self):
        """Extends superclass startup  when taskrunner starts."""
        ssdpdaemon.SSDPDaemon.startup(self)
        # RootDevice
        self._root_device = self._sm.get_root_device()
        # Config
        self._config = _SSDP_SERVER_CONFIG
        self._config['location'] = self._sm.get_description_url()
        self._config['osversion'] = self._sm.get_os_version()
        self._config['productversion'] = self._sm.get_product_version()
        # Initial Announce
        self.announce()

    #
    # OVERRIDE HANDLERS
    #

    def handle_search(self, msg, sock_addr):
        """Handles the receipt of a SSDP Search message."""

        # Create Reply Message
        reply_message = ssdpmessage.ReplyMessage()
        _initialise_message(self._config, reply_message)

        # Decide the number of reply messages, and their configuration.

        if msg.st == "ssdp:all":
            # Reply messages for all devices and services
            configs = _create_msg_configs(self._root_device)
        elif msg.st == "upnp:rootdevice":
            # Reply only single special message for root device
            configs = [_create_msg_config(_ROOT_CONF_TEMPL,
                                          self._root_device.__dict__)]
        else:
            device_type = msg.st.split(':')[-2]
            self.log("IGNORE %s %s [%s]" % (msg.type,
                                            device_type, sock_addr[0]))
            return

        device_type = msg.st.split(':')[-2]
        self.log("RECEIVE %s %s [%s]" % (msg.type,
                                         device_type, sock_addr[0]))

        # Send Replies
        for conf in configs:
            reply_message.st = conf['target']
            reply_message.usn = conf['usn']
            self.unicast(reply_message, sock_addr)

    def _handle_reply(self, msg, sock_addr):
        """Handles the receipt of a SSDP Reply message."""
        self.log("IGNORE %s from %s" % (msg.type, sock_addr))

    def _handle_announce(self, msg, sock_addr):
        """Handles the receipt of a SSDP Announce message."""

        self.log("IGNORE %s from %s" % (msg.type, sock_addr))

    def _handle_unannounce(self, msg, sock_addr):
        """Handles the receipt of a SSDP UnAnnounce message."""
        self.log("IGNORE %s from %s" % (msg.type, sock_addr))

    #
    # PUBLIC API
    #

    def announce(self):
        """Multicast SSDP announce messages."""
        # Reset timeout task for next announce
        if self._timeout_task:
            self._timeout_task.cancel()
        # Register new announce timeout
        self._timeout_task = self.task_runner.add_delay_task(
            _REANNOUNCE_AGE,
            self.announce
            )

        msg = ssdpmessage.AnnounceMessage()
        _initialise_message(self._config, msg)
        for conf in _create_msg_configs(self._root_device):
            msg.nt = conf['target']
            msg.usn = conf['usn']
            self.multicast(msg)

    def unannounce(self):
        """Multicast SSDP unannounce messages."""
        msg = ssdpmessage.UnAnnounceMessage()
        for conf in _create_msg_configs(self._root_device):
            msg.nt = conf['target']
            msg.usn = conf['usn']
            self.multicast(msg)

    def close(self):
        """Close the SSDP Server deamon. Send unannounce messages."""
        self.unannounce()
        ssdpdaemon.SSDPDaemon.close(self)


#
# MAIN
#

if __name__ == '__main__':

    import uuid

    class MockRootDevice:

        """Mockup root device."""
        def __init__(self):
            self.uuid = uuid.uuid1()
            self.device_domain = "schemas-upnp-org"
            self.device_type = "Basic"
            self.device_version = 1

        def get_devices(self):
            """Get mock devices."""
            return []

        def get_services(self):
            """Get mock services."""
            return []

    class MockServiceManager:

        """Mock up service manager."""
        def __init__(self):
            pass

        def get_root_device(self):
            """Get mock root device."""
            return MockRootDevice()

        def get_description_url(self):
            """Get mock description URL."""
            return "http://192.168.1.235:44444/description.xml"

        def get_os_version(self):
            """Get mock os version."""
            return "linux 1.0"

        def get_product_version(self):
            """Get mock product version."""
            return "product 1.0"

        def set_ssdp_port(self, port):
            """Set mock Port."""
            pass

    class MockLogger:

        """MockLogger object."""
        def __init__(self):
            pass

        def log(self, log_tag, msg):
            """Log to std out."""
            print log_tag, msg

    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()
    SM = MockServiceManager()
    SERVER = SSDPServer(TR, logger=MockLogger())
    SERVER.set_service_manager(SM)
    TR.add_task(SERVER.startup)
    try:
        TR.run_forever()
    except KeyboardInterrupt:
        print
    TR.stop()
    SERVER.close()
