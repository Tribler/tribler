# Written by Arno Bakker
# see LICENSE.txt for license information
#
# All applications on top of the SecureOverlay should be started here.
#
from MetadataHandler import MetadataHandler
from threading import Lock
from threading import currentThread
from time import time
from traceback import print_exc
import sys

from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.CoopDownload.CoordinatorMessageHandler import CoordinatorMessageHandler
from Tribler.Core.CoopDownload.HelperMessageHandler import HelperMessageHandler
from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Core.NATFirewall.NatCheckMsgHandler import NatCheckMsgHandler
from Tribler.Core.SocialNetwork.FriendshipMsgHandler import FriendshipMsgHandler 
from Tribler.Core.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.SocialNetwork.SocialNetworkMsgHandler import SocialNetworkMsgHandler
from Tribler.Core.Statistics.Crawler import Crawler
from Tribler.Core.Statistics.DatabaseCrawler import DatabaseCrawler
from Tribler.Core.Statistics.FriendshipCrawler import FriendshipCrawler
from Tribler.Core.Statistics.SeedingStatsCrawler import SeedingStatsCrawler
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.simpledefs import *

DEBUG = False

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
        self.friendship_handler = None
        self.msg_handlers = {}
        self.connection_handlers = []
        self.text_mode = None
        self.requestPolicyLock = Lock()
        
    def getInstance(*args, **kw):
        if OverlayApps.__single is None:
            OverlayApps(*args, **kw)
        return OverlayApps.__single
    getInstance = staticmethod(getInstance)

    def register(self, overlay_bridge, session, launchmany, config, requestPolicy):
        self.overlay_bridge = overlay_bridge
        self.launchmany = launchmany
        self.requestPolicy = requestPolicy
        self.text_mode = config.has_key('text_mode')
        
        # OverlayApps gets all messages, and demultiplexes 
        overlay_bridge.register_recv_callback(self.handleMessage)
        overlay_bridge.register_conns_callback(self.handleConnection)

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
            self.help_handler = HelperMessageHandler()
            self.help_handler.register(session,self.metadata_handler,config['download_help_dir'],config.get('coopdlconfig', False))
            self.register_msg_handler(HelpCoordinatorMessages, self.help_handler.handleMessage)

        # Part 2:
        self.metadata_handler.register(overlay_bridge, self.help_handler, launchmany, config)
        self.register_msg_handler(MetadataMessages, self.metadata_handler.handleMessage)
        
        if not config['torrent_collecting']:
            self.torrent_collecting_solution = 0
        
        if config['buddycast']:
            # Create handler for Buddycast messages
            self.buddycast = BuddyCastFactory.getInstance(superpeer=config['superpeer'], log=config['overlay_log'])
            # Using buddycast to handle torrent collecting since they are dependent
            self.buddycast.register(overlay_bridge, launchmany, 
                                    launchmany.rawserver_fatalerrorfunc,
                                    self.metadata_handler, 
                                    config['buddycast_collecting_solution'],
                                    config['start_recommender'],config['buddycast_max_peers'])
            self.register_msg_handler(BuddyCastMessages, self.buddycast.handleMessage)
            self.register_connection_handler(self.buddycast.handleConnection)

        if config['dialback']:
            self.dialback_handler = DialbackMsgHandler.getInstance()
            # The Dialback mechanism needs the real rawserver, not the overlay_bridge
            self.dialback_handler.register(overlay_bridge, launchmany, launchmany.rawserver, config)
            self.register_msg_handler([DIALBACK_REQUEST],
                                      self.dialback_handler.olthread_handleSecOverlayMessage)
            self.register_connection_handler(self.dialback_handler.olthread_handleSecOverlayConnection)

        if config['socnet']:
            self.socnet_handler = SocialNetworkMsgHandler.getInstance()
            self.socnet_handler.register(overlay_bridge, launchmany, config)
            self.register_msg_handler(SocialNetworkMessages,self.socnet_handler.handleMessage)
            self.register_connection_handler(self.socnet_handler.handleConnection)

            self.friendship_handler = FriendshipMsgHandler.getInstance()
            self.friendship_handler.register(overlay_bridge, launchmany.session)
            self.register_msg_handler(FriendshipMessages,self.friendship_handler.handleMessage)
            self.register_connection_handler(self.friendship_handler.handleConnection)

        if config['rquery']:
            self.rquery_handler = RemoteQueryMsgHandler.getInstance()
            self.rquery_handler.register(overlay_bridge,launchmany,config,self.buddycast,log=config['overlay_log'])
            self.register_msg_handler(RemoteQueryMessages,self.rquery_handler.handleMessage)
            self.register_connection_handler(self.rquery_handler.handleConnection)

        if config['crawler']:
            crawler = Crawler.get_instance(session)
            self.register_msg_handler([CRAWLER_REQUEST], crawler.handle_request)

            # allows access to tribler database
            database_crawler = DatabaseCrawler.get_instance()
            crawler.register_crawl_initiator(database_crawler.query_initiator)
            crawler.register_message_handler(CRAWLER_DATABASE_QUERY, database_crawler.handle_crawler_request, database_crawler.handle_crawler_reply)

            # allows access to seeding statistics (Boxun)
            seeding_stats_crawler = SeedingStatsCrawler.get_instance()
            crawler.register_crawl_initiator(seeding_stats_crawler.query_initiator)
            crawler.register_message_handler(CRAWLER_SEEDINGSTATS_QUERY, seeding_stats_crawler.handle_crawler_request, seeding_stats_crawler.handle_crawler_reply)

            # allows access to friendship statistics (Ali)
            friendship_crawler = FriendshipCrawler.get_instance(session)
            crawler.register_crawl_initiator(friendship_crawler.query_initiator)
            crawler.register_message_handler(CRAWLER_FRIENDSHIP_STATS, friendship_crawler.handle_crawler_request, friendship_crawler.handle_crawler_reply)

            # allows access to nat-check statistics (Lucia)
            natcheck_handler = NatCheckMsgHandler.getInstance()
            natcheck_handler.register(launchmany)
            crawler.register_crawl_initiator(natcheck_handler.doNatCheck)
            crawler.register_message_handler(CRAWLER_NATCHECK, natcheck_handler.gotDoNatCheckMessage, natcheck_handler.gotNatCheckReplyMessage)

            if crawler.am_crawler():
                # we will only accept CRAWLER_REPLY messages when we are actully a crawler
                self.register_msg_handler([CRAWLER_REPLY], crawler.handle_reply)
                self.register_connection_handler(crawler.handle_connection)

                # 13/10/08 Boudewijn: a little test code to 'crawl' to a specific peer
                # this connect is only used to test the crawler!
#                 def _tmp(exc, dns, permid, selversion):
#                     self.handleConnection(exc, permid, selversion, True)
#                 self.overlay_bridge.connect_dns(("130.161.158.24", 7762), _tmp)
            
        self.rtorrent_handler = RemoteTorrentHandler.getInstance()
        self.rtorrent_handler.register(overlay_bridge,self.metadata_handler,session)
        self.metadata_handler.register2(self.rtorrent_handler)

        # Add notifier as connection handler
        self.register_connection_handler(self.notifier_handles_connection)
        
        if config['buddycast']:
            # Arno: to prevent concurrency between mainthread and overlay
            # thread where BuddyCast schedules tasks
            self.buddycast.register2()
    
    def early_shutdown(self):
        """ Called as soon as Session shutdown is initiated. Used to start
        shutdown tasks that takes some time and that can run in parallel
        to checkpointing, etc.
        """
        # Called by OverlayThread
        if self.friendship_handler is not None:
            self.friendship_handler.shutdown()
            
        
    def register_msg_handler(self, ids, handler):
        """ 
        ids is the [ID1, ID2, ..] where IDn is a sort of message ID in overlay
        swarm. Each ID can only be handled by one handler, but a handler can 
        handle multiple IDs
        """
        for id in ids:
            if DEBUG:
                print >> sys.stderr,"olapps: Message handler registered for",getMessageName(id)
            self.msg_handlers[id] = handler

    def register_connection_handler(self, handler):
        """
            Register a handler for if a connection is established
            handler-function is called like:
            handler(exc,permid,selversion,locally_initiated)
        """
        assert handler not in self.connection_handlers, 'This connection_handler is already registered'
        if DEBUG:
            print >> sys.stderr, "olapps: Connection handler registered for", handler
        self.connection_handlers.append(handler)

    def handleMessage(self,permid,selversion,message):
        """ demultiplex message stream to handlers """
        
        # Check auth
        if not self.requestAllowed(permid, message[0]):
            return False

        if message[0] in self.msg_handlers:
            # This is a one byte id. (For instance a regular
            # BitTorrent message)
            id_ = message[0]
        else:
            if DEBUG:
                print >> sys.stderr, "olapps: No handler found for", getMessageName(message[0:2])
            return False

        if DEBUG:
            print >> sys.stderr, "olapps: handleMessage", getMessageName(id_), "v" + str(selversion)

        try:
            if DEBUG:
                st = time()
                ret = self.msg_handlers[id_](permid, selversion, message)
                et = time()
                diff = et - st
                if diff > 0:
                    print >> sys.stderr,"olapps: ",getMessageName(id_),"TOOK %.5f" % diff
                return ret
            else:
                return self.msg_handlers[id_](permid, selversion, message)
        except:
            # Catch all
            print_exc()
            return False

    def handleConnection(self,exc,permid,selversion,locally_initiated):
        """ An overlay-connection was established. Notify interested parties. """

        if DEBUG:
            print >> sys.stderr,"olapps: handleConnection",exc,selversion,locally_initiated,currentThread().getName()

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
            print >> sys.stderr, 'olapps: Request type %s from %s was %s' % (getMessageName(messageType), show_permid_short(permid), word)
        return allowed
    
    def setRequestPolicy(self, requestPolicy):
        self.requestPolicyLock.acquire()
        try:
            self.requestPolicy = requestPolicy
        finally:
            self.requestPolicyLock.release()
        
    
    def notifier_handles_connection(self, exc,permid,selversion,locally_initiated):
        # Notify interested parties (that use the notifier/observer structure) about a connection
        self.launchmany.session.uch.notify(NTFY_PEERS, NTFY_CONNECTION, permid, True)
