# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""This module implements a URL UPnP Service."""

import types
from Tribler.UPnP.upnpserver import UPnPService

DEFAULT_URL = "http://vg.no"


#
# URL SERVICE
#

class URLService(UPnPService):

    """This class implements a simple URL service."""

    def __init__(self, service_id):
        UPnPService.__init__(self, service_id, 'URLService',
                             service_version=1)

        # Define Evented Variable
        self._url = self.define_evented_variable("URL", bytes,
                                                 DEFAULT_URL)

        # Define Actions
        self.define_action(self.get_url,
                           out_args=[("URL", bytes)],
                           name="GetURL")
        self.define_action(self.set_url,
                           in_args=[("URL", bytes)],
                           name="SetURL")

    def get_url(self):
        """Get the URL."""
        return self._url.get()

    def set_url(self, new_url):
        """Set the URL."""
        self._url.set(new_url)
