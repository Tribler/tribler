# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements a console interface to a UPnP server.
"""

#
# UPNP SERVER CONSOLE
#

from upnpserver import UPnPServer
from Tribler.UPnP.services import SwitchPower, URLService
from Tribler.UPnP.services import BookmarkService
from Tribler.UPnP.common.objectconsole import ObjectConsole
from Tribler.UPnP.common.taskrunner import TaskRunner


class UPnPServerConsole:

    """This class wraps ObjectConsole to implement a
    custom console for UPnP server."""

    def __init__(self):

        # Task Runner
        self._task_runner = TaskRunner()

        # UPnP Server
        self._server = UPnPServer(self._task_runner, "Product 1.0")

        # Switch Power Service
        service_id = "SwitchPower"
        service = SwitchPower(service_id)
        self._server.add_service(service)

        # URL Service
        service_id_2 = "URLService"
        service_2 = URLService(service_id_2)
        self._server.add_service(service_2)

        # Bookmark Service
        service_3 = BookmarkService()
        self._server.add_service(service_3)

        # Console Namespace
        name_space = {}
        root_device = self._server.get_root_device()
        name_space[root_device.name] = root_device
        name_space[service_id] = service
        name_space[service_id_2] = service_2
        name_space[service_3.get_short_service_id()] = service_3
        name_space['add_service'] = self._server.add_service
        name_space['get_service'] = self._server.get_service
        name_space['get_services'] = self._server.get_service_ids
        name_space['announce'] = self._server.announce

        self._console = ObjectConsole(self, name_space,
                                      run="_run",
                                      stop="_stop", name="UPnP Server")

    def _run(self):
        """Start TaskRunner."""
        self._task_runner.run_forever()

    def _stop(self):
        """Stop UPnPServer and TaskRunner"""
        self._server.close()
        self._task_runner.stop()

    def run(self):
        """Runs the UPnP Console."""
        self._console.run()


#
# MAIN
#
if __name__ == '__main__':

    UPnPServerConsole().run()
