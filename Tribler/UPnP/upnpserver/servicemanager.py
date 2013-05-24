# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""This module implements the servicemanager of the UPnP server.
The service manager manages all devices and services. Its reference
is given to all the other modules, so servicemanager is also used to
hold some global state. """

import socket
import platform

_SSDP_PORT = 44443
_HTTP_PORT = 44444

#
# SERVICE MANAGER
#


class ServiceManager:

    """
    Holds devices and services, identified by deviceName and
    serviceid, respectively.
    todo : ServiceManager should also implement a
    hierarchical name space
    where devices are internal nodes and services are
    Has some global state that is makes available for other modules.
    This is the core of the UPnP Service implementation.
    """

    def __init__(self, task_runner, ssdp_server, http_server,
                 event_dispatcher, root_device,
                 product_name, logger=None):

        self._task_runner = task_runner
        self._ssdp_server = ssdp_server
        self._http_server = http_server
        self._event_dispatcher = event_dispatcher

        self._services = {}
        self._root_device = root_device
        self._host = socket.gethostbyname(socket.gethostname())
        self._description_path = "description.xml"
        self._presentation_path = "presentation.html"
        self._os_version = platform.platform()
        self._product_version = product_name
        self._logger = logger

        self._root_device.set_service_manager(self)
        self._ssdp_server.set_service_manager(self)
        self._http_server.set_service_manager(self)

    def startup(self):
        """Startup http server and ssdp server."""
        self._http_server.startup()
        self._ssdp_server.startup()

    def get_http_port(self):
        """Return HTTP port used by UPnP server."""
        return self._http_server.get_port()

    def get_ssdp_port(self):
        """Return SSDP port used by UPnP server."""
        return self._ssdp_server.get_port()

    def get_base_url(self):
        """Return base url for UPnP server."""
        return "http://%s:%d/" % (self.get_host(), self.get_http_port())

    def get_description_path(self):
        """Return description path for UPnP server."""
        return self._description_path

    def get_presentation_path(self):
        """Return presentation path for UPnP server."""
        return self._presentation_path

    def get_description_url(self):
        """Return description url for UPnP server."""
        return self.get_base_url() + self._description_path

    def get_presentation_url(self):
        """Return presentation url for UPnP server."""
        return self.get_base_url() + self._presentation_path

    def get_host(self):
        """Return host for UPnP server."""
        return self._host

    def get_os_version(self):
        """Return OS version for UPnP server."""
        return self._os_version

    def get_product_version(self):
        """Return product name/version for UPnP server."""
        return self._product_version

    def get_logger(self):
        """Return the global logger for UPnP server."""
        return self._logger

    def set_root_device(self, device):
        """Register a device as root."""
        device.set_service_manager(self)
        self._root_device = device

    def get_root_device(self):
        """Returns the root device."""
        return self._root_device

    def get_device(self, name):
        """Get device by name."""
        if self._root_device.name == name:
            return self._root_device

    def add_service(self, service):
        """Add a new service to the UPnP Server."""
        service.set_service_manager(self)
        self._services[service.service_id] = service

    def get_service(self, service_id):
        """Get service by service_id."""
        return self._services.get(service_id, None)

    def get_service_ids(self):
        """Return a list of service ids."""
        return self._services.keys()

    def get_task_runner(self):
        """Get task runner."""
        return self._task_runner

    def get_event_dispatcher(self):
        """Get event dispatcher."""
        return self._event_dispatcher

    def get_devices_of_device(self, device):
        """Get subdevices of a device."""
        return []

    def get_services_of_device(self, device):
        """Get services contained within a device."""
        if device == self._root_device:
            return self._services.values()
        else:
            return []

    def close(self):
        """Close service manager."""
        for service in self._services.values():
            service.close()
        self._root_device.close()
