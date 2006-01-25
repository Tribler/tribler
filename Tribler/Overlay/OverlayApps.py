# Written by Arno Bakker
# see LICENSE.txt for license information
#
# All applications on top of the SecureOverlay should be started here.
#

from BitTornado.BT1.MessageID import HelpCoordinatorMessages, HelpHelperMessages, MetadataMessages
from Tribler.toofastbt.CoordinatorMessageHandler import CoordinatorMessageHandler
from Tribler.toofastbt.HelperMessageHandler import HelperMessageHandler
from MetadataHandler import MetadataHandler

class OverlayApps:
    # Code to make this a singleton
    __single = None

    def __init__(self):
        if OverlayApps.__single:
            raise RuntimeError, "OverlayApps is Singleton"
        OverlayApps.__single = self 

    def getInstance(*args, **kw):
        if OverlayApps.__single is None:
            OverlayApps(*args, **kw)
        return OverlayApps.__single
    getInstance = staticmethod(getInstance)

    def register(self,secure_overlay,launchmany):
        # Create handler for messages to dlhelp coordinator
        self.coordinator = CoordinatorMessageHandler(launchmany)
        secure_overlay.registerHandler(HelpHelperMessages,self.coordinator)

        # Create handler for messages to dlhelp helper
        self.helper = HelperMessageHandler(launchmany)
        secure_overlay.registerHandler(HelpCoordinatorMessages,self.helper)

        # Create handler for metadata messages
        self.metadata_handler = MetadataHandler.getInstance()
        self.metadata_handler.register(secure_overlay,self.helper,launchmany)
        secure_overlay.registerHandler(MetadataMessages,self.metadata_handler)
        self.helper.register(self.metadata_handler)

#    def start_buddycast(self):
#        self.buddycast = BuddyCast.getInstance()
#        self.buddycast.set_rawserver(self.rawserver)
#        self.buddycast.set_listen_port(self.listen_port)
#        self.buddycast.set_errorfunc(self.errorfunc)
#        self.buddycast.startup()
#        self.start_metadata_handler()
        
#    def start_metadata_handler(self):
#        self.metadata_handler = MetadataHandler.getInstance()
#        self.metadata_handler.set_rawserver(self.rawserver)
#        self.metadata_handler.set_dlhelper(Helper.getInstance())
#        self.metadata_handler.startup()


