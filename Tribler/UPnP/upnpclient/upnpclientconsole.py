# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements a console interface to a UPnP Client.
"""

##############################################
# UPNP CLIENT CONSOLE
##############################################

from upnpclient import UPnPClient
from Tribler.UPnP.common.objectconsole import ObjectConsole
from Tribler.UPnP.common.taskrunner import TaskRunner

class UPnPClientConsole:

    """This class wraps ObjectConsole to implement a
    custom console for UPnP Client (Control Point)."""

    def __init__(self):

        # Task Runner
        self._task_runner = TaskRunner()

        # UPnP Client
        self._client = UPnPClient(self._task_runner)

        # Console Namespace
        name_space = {}
        name_space['get_device_uuids'] = self._client.get_device_uuids
        name_space['get_service_types'] = self._client.get_service_types
        name_space['get_service_ids'] = self._client.get_service_ids
        name_space['get_device'] = self._client.get_device
        name_space['get_services_by_type'] = self._client.get_services_by_type
        name_space['get_services_by_id'] = self._client.get_services_by_id
        name_space['get_services_by_short_id'] = \
            self._client.get_services_by_short_id
        name_space['get_service'] = self._client.get_service
        name_space['search'] = self._client.search

        self._console = ObjectConsole(self, name_space,
                                      run="_run",
                                      stop="_stop", name="UPnP Client")

    def _run(self):
        """Run the TaskRunner."""
        self._task_runner.run_forever()

    def _stop(self):
        """Stup UPnPClient and TaskRunner."""
        self._client.close()
        self._task_runner.stop()

    def run(self):
        """Runs the UPnP Console."""
        self._console.run()



##############################################
# MAIN
##############################################

if __name__ == '__main__':

    UPnPClientConsole().run()
