# Written by Arno Bakker
# see LICENSE.txt for license information
#
# All applications on top of the SecureOverlay should be started here.
#
import sys
from traceback import print_exc
from threading import Lock

from time import time
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.CoopDownload.CoordinatorMessageHandler import CoordinatorMessageHandler
from Tribler.Core.CoopDownload.HelperMessageHandler import HelperMessageHandler
from MetadataHandler import MetadataHandler
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Core.SocialNetwork.SocialNetworkMsgHandler import SocialNetworkMsgHandler
from Tribler.Core.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.Utilities.utilities import show_permid_short

DEBUG = True

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
        self.dialback_handler = None
        self.socnet_handler = None
        self.rquery_handler = None
        self.msg_handlers = {}
        self.connection_handlers = []
        self.text_mode = None
        self.requestPolicyLock = Lock()
        
        
        
    def getInstance(*args, **kw):
        if OverlayApps.__single is None:
            OverlayApps(*args, **kw)
        return OverlayApps.__single
    getInstance = staticmethod(getInstance)

    def register(self, secure_overlay, launchmany, config, requestPolicy):
        self.secure_overlay = secure_overlay
        self.launchmany = launchmany
        self.requestPolicy = requestPolicy
        self.text_mode = config.has_key('text_mode')
        
        # OverlayApps gets all messages, and demultiplexes 
        secure_overlay.register_recv_callback(self.handleMessage)
        secure_overlay.register_conns_callback(self.handleConnection)

        # Create handler for metadata messages in two parts, as 
        # download help needs to know the metadata_handler and we need
        # to know the download helper handler.
        # Part 1:
        self.metadata_handler = MetadataHandler.getInstance()

        if config['download_help']:
            # Create handler for messages to dlhelp coordinator
            self.coord_handler = CoordinatorMessageHandler(launchmany)
            self.register_msg_handler(HelpHelperMessages, self.coord_handler.handleMessage)

            # Create handler for messages to dlhelp helper
            self.help_handler = HelperMessageHandler(launchmany, config)
            self.help_handler.register(self.metadata_handler,secure_overlay)
            self.register_msg_handler(HelpCoordinatorMessages, self.help_handler.handleMessage)

        # Part 2:
        self.metadata_handler.register(secure_overlay, self.help_handler, launchmany, config)
        self.register_msg_handler(MetadataMessages, self.metadata_handler.handleMessage)
        
        if not config['torrent_collecting']:
            self.torrent_collecting_solution = 0
        
        if config['buddycast']:
            # Create handler for Buddycast messages
            self.buddycast = BuddyCastFactory.getInstance(superpeer=config['superpeer'], log=config['overlay_log'])
            # Using buddycast to handle torrent collecting since they are dependent
            self.buddycast.register(secure_overlay, launchmany.rawserver, launchmany, 
                                    launchmany.rawserver_fatalerrorfunc, True,
                                    self.metadata_handler, config['buddycast_collecting_solution'], 
                                    config['start_recommender'], config['max_peers'])
            self.register_msg_handler(BuddyCastMessages, self.buddycast.handleMessage)
            self.register_connection_handler(self.buddycast.handleConnection)

        if config['dialback']:
            self.dialback_handler = DialbackMsgHandler.getInstance()
            self.dialback_handler.register(secure_overlay, launchmany, config)
            self.register_msg_handler([DIALBACK_REQUEST],
                                      self.dialback_handler.handleSecOverlayMessage)
            self.register_connection_handler(self.dialback_handler.handleSecOverlayConnection)

        if config['socnet']:
            self.socnet_handler = SocialNetworkMsgHandler.getInstance()
            self.socnet_handler.register(secure_overlay, launchmany, config)
            self.register_msg_handler(SocialNetworkMessages,self.socnet_handler.handleMessage)
            self.register_connection_handler(self.socnet_handler.handleConnection)

        if config['rquery']:
            self.rquery_handler = RemoteQueryMsgHandler.getInstance()
            self.rquery_handler.register(secure_overlay,launchmany,launchmany.rawserver,config,self.buddycast,log=config['overlay_log'])
            self.register_msg_handler(RemoteQueryMessages,self.rquery_handler.handleMessage)
            self.register_connection_handler(self.rquery_handler.handleConnection)
            
            self.rtorrent_handler = RemoteTorrentHandler.getInstance()
            self.rtorrent_handler.register(launchmany.rawserver,self.metadata_handler)
            self.metadata_handler.register2(self.rtorrent_handler)
            
            
        
    def register_msg_handler(self, ids, handler):
        """ 
        ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay
        swarm. Each ID can only be handled by one handler, but a handler can 
        handle multiple IDs
        """
        for id in ids:
            if DEBUG:
                print >> sys.stderr,"olapps: Handler registered for",getMessageName(id)
            self.msg_handlers[id] = handler
        
    def register_connection_handler(self, handler):
        """
            Register a handler for if a connection is established
            handler-function is called like:
            handler(exc,permid,selversion,locally_initiated)
        """
        assert handler not in self.connection_handlers, 'This connection_handler is already registered'
        self.connection_handlers.append(handler)
        

    def handleMessage(self,permid,selversion,message):
        """ demultiplex message stream to handlers """
        id = message[0]
        if DEBUG:
            print >> sys.stderr,"olapps: got_message",getMessageName(id),"v"+str(selversion)
        if not self.msg_handlers.has_key(id):
            if DEBUG:
                print >> sys.stderr,"olapps: No handler found for",getMessageName(id)
            return False
        else:
            if DEBUG:
                print >> sys.stderr,"secover: Giving message to handler for",getMessageName(id)
            try:
                return self.msg_handlers[id](permid,selversion,message)
            except:
                # Catch all
                print_exc()
                return False


    def handleConnection(self,exc,permid,selversion,locally_initiated):
        """ An overlay-connection was established. Notify interested parties. """

        if DEBUG:
            print >> sys.stderr,"olapps: handleConnection",exc,selversion,locally_initiated

        for handler in self.connection_handlers:
            try:
                #if DEBUG:
                #    print >> sys.stderr,"olapps: calling connection handler:",'%s.%s' % (handler.__module__, handler.__name__)
                handler(exc,permid,selversion,locally_initiated)
            except:
                print >> sys.stderr, 'olapps: Exception during connection handler calling'
                print_exc()
    
    def requestAllowed(self, permid, messageType):
        self.requestPolicyLock.acquire()
        try:
            rp = self.requestPolicy
        finally:
            self.requestPolicyLock.release()
        allowed = rp.allowed(permid, messageType)
        if DEBUG:
            if allowed:
                word = 'allowed'
            else:
                word = 'denied'
            print >> sys.stderr, 'opapps: Request type %s from %s was %s' % (getMessageName(messageType), show_permid_short(permid), word)
        return allowed
    
    def setRequestPolicy(self, requestPolicy):
        self.requestPolicyLock.acquire()
        try:
            self.requestPolicy = requestPolicy
        finally:
            self.requestPolicyLock.release()
        
    