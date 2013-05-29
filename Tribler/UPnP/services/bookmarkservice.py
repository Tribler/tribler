# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""
This module implements a Bookmark Service on the local
network, exported as a UPnP Service.
"""

import types
from Tribler.UPnP.upnpserver import UPnPService

_DEFAULT_SERVICE_ID = "Bookmarks"

_XML_DOC = '<?xml version="1.0"?>\n<bookmarks>\n%s</bookmarks>'
_XML_ITEM = '<item>%s</item>\n'


#
# BOOKMARK SERVICE
#

class BookmarkService(UPnPService):

    """
    This class implements a Bookmark Service.
    It is exported on the local network as an UPnP Service.

    Essentially the service maintains a list of bookmarks.

    Two actions:
    - GET(): return the complete list as xml data.
    - POST() : append a new url to the list

    Events:
    - UPDATE

    """

    def __init__(self, service_id=None, service_version=1):
        if service_id == None:
            service_id = _DEFAULT_SERVICE_ID
        UPnPService.__init__(self, service_id, service_version)

        self._bookmarks = []

        # Define Event Variable
        self._update_event = self.define_evented_variable("UPDATE",
                                                          bool, False)

        # Define Actions
        self.define_action(self.get,
                           out_args=[("BOOKMARKS", bytes)],
                           name="GET")
        self.define_action(self.post,
                           in_args=[("BOOKMARK", bytes)],
                           name="POST")

    def post(self, bookmark):
        self._bookmarks.append(bookmark)
        self._on_update()

    def get(self):
        """Get the xml string representation of the entire list."""
        items = ""
        for bookmark in self._bookmarks:
            items += _XML_ITEM % bookmark
        return _XML_DOC % items

    def _on_update(self):
        """
        Internal method: Toggles the value of update_event,
        in order to notify listeners. Used whenever the list of
        bookmarks is updated.
        """
        if self._update_event.get() == True:
            self._update_event.set(False)
        else:
            self._update_event.set(True)
