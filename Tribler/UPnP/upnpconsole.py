# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This class implements a console interface to both UPnPServer
and UPnPClient.
"""
##############################################
# UPNP CONSOLE
##############################################

from Tribler.UPnP.common import TaskRunner
from Tribler.UPnP.common import ObjectConsole
from Tribler.UPnP.upnpserver import UPnPServer
from Tribler.UPnP.upnpclient import UPnPClient
from Tribler.UPnP.services import SwitchPower, URLService
from Tribler.UPnP.services import BookmarkService
from Tribler.UPnP import SERVER_PRODUCT_NAME
from Tribler.UPnP import SERVER_ROOT_DEVICE_CONFIG

class UPnPConsole:

    """This class wraps ObjectConsole to implement a
    custom UPnP console."""

    def __init__(self):

        self._task_runner = TaskRunner()
        self._server = UPnPServer(self._task_runner,
                            SERVER_PRODUCT_NAME,
                            SERVER_ROOT_DEVICE_CONFIG)
        self._client = UPnPClient(self._task_runner)

        # Add a couple of services
        self._server.add_service(SwitchPower("SwitchPower"))
        self._server.add_service(URLService("URLService"))
        self._server.add_service(BookmarkService())

        # Console Namespace
        namespace = {}
        namespace['S'] = self._server
        namespace['C'] = self._client

        self._console = ObjectConsole(self, namespace,
                                      run="_run",
                                      stop="_stop",
                                      name="UPnP")


    def _run(self):
        """Run the TaskRunner."""
        self._task_runner.run_forever()

    def _stop(self):
        """
        Internal: Stop the UPnPClient, UPnPServer and the
        TaskRunner.
        """
        self._client.close()
        self._server.close()
        self._task_runner.stop()

    def run(self):
        """Runs the UPnP Console."""
        self._console.run()



##############################################
# MAIN
##############################################

if __name__ == '__main__':
    UPnPConsole().run()
