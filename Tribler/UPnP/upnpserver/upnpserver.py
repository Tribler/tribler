# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""This module implements a UPnP Server."""

from Tribler.UPnP.ssdp.ssdpserver import SSDPServer
import upnpdevice
from httpserver import HTTPServer
from servicemanager import ServiceManager
from upnpeventdispatcher import EventDispatcher

DEFAULT_ROOT_DEVICE_CONFIG = {
    'device_type': "Basic",
    'device_version': 1,
    'name': "Basic",
    'device_domain': 'schemas-upnp-org',
    'manufacturer': "Manufacturer",
    'manufacturer_url': 'http://manufacturer.com',
    'model_description': 'Model description',
    'model_name': 'Model 1',
    'model_number': '1.0',
    'model_url': 'http://manufacturer.com/model_1',
    'serial_number': '123456',
    'upc': '012345678912',
}

_LOG_TAG = "UPnPServer"


class _Logger:

    """Internal Logger presented to modules within the UPnP Server."""
    def __init__(self, logger):
        self._logger = logger

    def log(self, log_tag, msg):
        """Log module tag and msg. UPnPServer logtag is added."""
        if self._logger:
            self._logger.log(_LOG_TAG, log_tag, msg)


#
# UPNP SERVER
#

class UPnPServer:

    """This class implements an extensible UPnP Server."""

    def __init__(self, task_runner, product_name,
                 root_device_config=None, logger=None):

        # TaskRunner
        self._tr = task_runner

        # Logger
        self._logger = _Logger(logger)

        # Initalise Root Device
        if not root_device_config:
            self._root_device_config = DEFAULT_ROOT_DEVICE_CONFIG
        else:
            self._root_device_config = root_device_config
        device = upnpdevice.UPnPDevice(self._root_device_config)
        device.set_is_root(True)

        # Event Dispatcher (HTTP Client)
        self._ed = EventDispatcher(self._tr, logger=self._logger)

        # HTTP Server
        self._http_server = HTTPServer(self._tr, logger=self._logger)

        # SSDP Server
        self._ssdp_server = SSDPServer(self._tr, logger=self._logger)

        # ServiceManager (The Core)
        self._sm = ServiceManager(self._tr, self._ssdp_server,
                                  self._http_server, self._ed, device,
                                  product_name, logger=self._logger)

        # Export Service Manager API
        self.add_service = self._sm.add_service
        self.get_service = self._sm.get_service
        self.get_service_ids = self._sm.get_service_ids

        # Export Internals
        self.get_root_device = self._sm.get_root_device

        # Startup done by TaskRunner
        self._tr.add_task(self._sm.startup)

    def get_presentation_url(self):
        root = self.get_root_device()
        return root.base_url + root.get_presentation_url()

    def announce(self):
        """Causes underlying SSDPServer to re-announce itself."""
        self._tr.add_task(self._ssdp_server.announce)

    def close(self):
        """Close the UPnP server."""
        self._sm.close()
        self._ssdp_server.close()
        self._http_server.close()
        self._ed.close()


#
# MAIN
#

if __name__ == '__main__':

    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()

    import Tribler.UPnP.common.upnplogger as upnplogger
    LOGGER = upnplogger.get_logger()

    SERVER = UPnPServer(TR, "Product 1.0", logger=LOGGER)

    from Tribler.UPnP.services.switchpower import SwitchPower
    from Tribler.UPnP.services.urlservice import URLService
    from Tribler.UPnP.services import BookmarkService
    SERVICE_1 = SwitchPower("MySwitchPower")
    SERVICE_2 = URLService("URLService")
    SERVICE_3 = BookmarkService()
    SERVER.add_service(SERVICE_1)
    SERVER.add_service(SERVICE_2)
    SERVER.add_service(SERVICE_3)
    try:
        TR.run_forever()
    except KeyboardInterrupt:
        print
    SERVER.close()
    TR.stop()
