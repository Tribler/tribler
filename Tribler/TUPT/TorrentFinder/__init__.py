# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""
This implements a UPnP package facilitating implementation of
python UPnPServers and UPnPClients (ControlPoints).

The module implements one extensible UPnPServer and one
extensible UPnPClient. They are independent, so both may be
run without the other. However, if they are both run at the same
time, the UPnPClient will discover the UPnPServer, as expected.

A referance to the UPnPServer may be obtained by invoking
- get_server()
A referance to the UPnPClient may be obtained by invoking
- get_client()

Both the UPnPServer and the UPnPClient are implemented in
an event-based fashion. One benefit of this is that they may
share the same thread (event loop == TaskRunner).
This thread and stopped by invoking.
-start()
-stop()

Limitations and Weaknesses

Generally
- Nested devices not supported.

UPnPServer
- UPnPService implementations can not be generated from xml
  service descriptions.
- Only boolean, int and string data types supported.

UPnPClient:
- Could have a browser interface.
- ServiceStubs are not disabled after SSDP device is removed.
- Does not discover added services.
- Only boolean, int, string and unsigned int supported.
- Action invokations only available in synchronized form.

"""
import threading
from common import get_logger

_LOGGER = None
#_LOGGER = get_logger()

SERVER_PRODUCT_NAME = "NextShare"
SERVER_ROOT_DEVICE_CONFIG = {
    'device_type' : "Basic",
    'device_version': 1,
    'name': "NextShare",
    'device_domain': 'p2p-next.org',
    'manufacturer': "P2P Next",
    'manufacturer_url': 'http://p2p-next.org/',
    'model_description': 'NextShare',
    'model_name': 'Model 1',
    'model_number': '1.0',
    'model_url': 'http://p2p-next.org/',
    'serial_number': '123456',
    'upc': '012345678910',
    }

##############################################
# UPNP
##############################################

class _UPnP:
    """
    UPnP class holds instances of TaskRunner, UPnPServer
    and UPnPClient.
    """

    def __init__(self):
        self._task_runner = None
        self._task_runner_thread = None
        self._upnp_server = None
        self._upnp_client = None

        # Real close methods
        self._real_client_close = None
        self._real_server_close = None

    def _get_task_runner(self):
        """Get referance to TaskRunner instance"""
        if self._task_runner == None:
            from Tribler.UPnP.common import TaskRunner
            self._task_runner = TaskRunner()
        return self._task_runner

    def start(self, stop_event):
        """Starts the Task Runner Thread"""
        if self._task_runner_thread == None:
            task_runner = self._get_task_runner()
            run = lambda: task_runner.run_forever(stop_event=stop_event)
            self._task_runner_thread = threading.Thread(
                group=None,
                target=run,
                name= "TaskRunnerThread")
            self._task_runner_thread.setDaemon(True)
            self._task_runner_thread.start()

    def is_running(self):
        """Return true if the TaskRunner is executing in a thread."""
        if self._task_runner_thread != None and \
                self._task_runner_thread.is_alive():
            return True
        else:
            return False

    def stop(self):
        """
        Stops both client and server,
        before stopping the Task Runner Thread.
        """
        self._wrap_client_close()
        self._wrap_server_close()
        if self._task_runner:
            self._task_runner.stop()
            self._task_runner = None
            self._task_runner_thread.join()
            self._task_runner_thread = None

    def get_upnp_server(self):
        """Get a referance to the UPnPServer instance."""
        if self._upnp_server == None:
            task_runner = self._get_task_runner()
            from Tribler.UPnP.upnpserver import UPnPServer
            self._upnp_server = UPnPServer(task_runner,
                                           SERVER_PRODUCT_NAME,
                                           SERVER_ROOT_DEVICE_CONFIG,
                                           logger=_LOGGER)
            # Wrap close method
            self._real_server_close = self._upnp_server.close
            self._upnp_server.close = self._wrap_server_close
        return self._upnp_server

    def get_upnp_client(self):
        """Get a referance to the UPnPClient intance."""
        if self._upnp_client == None:
            task_runner = self._get_task_runner()
            from Tribler.UPnP.upnpclient import UPnPClient
            self._upnp_client = UPnPClient(task_runner,
                                           logger=_LOGGER)
            # Wrap close method
            self._real_client_close = self._upnp_client.close
            self._upnp_client.close = self._wrap_client_close
        return self._upnp_client

    def _wrap_client_close(self):
        """Internal method: Replaces the close() method of the
        UPnPClient instance."""
        if self._upnp_client != None:
            self._upnp_client = None
            self._real_client_close()

    def _wrap_server_close(self):
        """Internal method: Replaces the close() method of the
        UPnPServer instance."""
        if self._upnp_server != None:
            self._upnp_server = None
            self._real_server_close()

_INSTANCE = _UPnP()

##############################################
# PUBLIC API
##############################################

def start(stop_event=None):
    """Starts the UPnPServer and/or UPnPClient."""
    _INSTANCE.start(stop_event)

def stop():
    """Stops the UPnPServer and/or UPnPClient."""
    _INSTANCE.stop()

def get_server():
    """Get referance to UPnPServer."""
    return _INSTANCE.get_upnp_server()

def get_client():
    """Get referance to UPnPClient."""
    return _INSTANCE.get_upnp_client()

def is_running():
    """Check if UPnPServer and/or UPnPClient is running."""
    return _INSTANCE.is_running()

import atexit
atexit.register(stop)
