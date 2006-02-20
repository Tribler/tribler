# Written by Arno Bakker
# see LICENSE.txt for license information
#
# All applications on top of the SecureOverlay should be started here.
#

from BitTornado.BT1.MessageID import HelpCoordinatorMessages,  HelpHelperMessages,  MetadataMessages,  BuddyCastMessages
from Tribler.toofastbt.CoordinatorMessageHandler import CoordinatorMessageHandler
from Tribler.toofastbt.HelperMessageHandler import HelperMessageHandler
from MetadataHandler import MetadataHandler
from Tribler.BuddyCast.buddycast import BuddyCastFactory
from Tribler.BuddyCast.TorrentCollecting import TorrentCollecting

class OverlayApps:
    # Code to make this a singleton
    __single = None

    def __init__(self):
        if OverlayApps.__single:
            raise RuntimeError, "OverlayApps is Singleton"
        OverlayApps.__single = self 
        self.coord_handler = None
        self.help_handler = None
        self.metadata_handler = None
        self.buddycast = None
        self.collect = None

    def getInstance(*args, **kw):
        if OverlayApps.__single is None:
            OverlayApps(*args, **kw)
        return OverlayApps.__single
    getInstance = staticmethod(getInstance)

    def register(self, secure_overlay, launchmany, enable_recommender, enable_dlhelp, enable_collect):
        if enable_dlhelp:
            # Create handler for messages to dlhelp coordinator
            self.coord_handler = CoordinatorMessageHandler(launchmany)
            secure_overlay.registerHandler(HelpHelperMessages, self.coord_handler)

            # Create handler for messages to dlhelp helper
            self.help_handler = HelperMessageHandler(launchmany)
            secure_overlay.registerHandler(HelpCoordinatorMessages, self.help_handler)

        if enable_recommender:
            # Create handler for Buddycast messages
            self.buddycast = BuddyCastFactory.getInstance()
            self.buddycast.register(secure_overlay, launchmany.rawserver, launchmany.listen_port, launchmany.exchandler)
            secure_overlay.registerHandler(BuddyCastMessages, self.buddycast)
            
        if enable_collect:
            self.collect = TorrentCollecting.getInstance()

        if enable_collect or enable_dlhelp:
            # Create handler for metadata messages
            self.metadata_handler = MetadataHandler.getInstance()
            self.metadata_handler.register(secure_overlay, self.help_handler, launchmany)
            secure_overlay.registerHandler(MetadataMessages, self.metadata_handler)
            
            if self.help_handler is not None:
                self.help_handler.register(self.metadata_handler)
                
            if self.collect is not None:
                self.collect.register(secure_overlay, launchmany.rawserver, self.metadata_handler)
                