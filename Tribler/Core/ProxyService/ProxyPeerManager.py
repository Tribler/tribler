# Written by George Milescu
# see LICENSE.txt for license information
#
# Proxy Peer Manager for the ProxyService
#
import sys
from traceback import print_exc

from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.simpledefs import *
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory

DEBUG = False

class ProxyPeerManager:
    def __init__(self, launchmany):
        self.launchmany = launchmany
        
        self.available_proxies={} #key=proxy_permid, value=ProxyDownloader instance. If value=None, the proxy is not used
        
        #Connectable/non-connectable information
        self.connectable=False
        
        from Tribler.Core.Session import Session
        session = Session.get_instance()
        session.add_observer(self.ol_connection_created_or_closed, NTFY_PEERS, [NTFY_CONNECTION], None)
        session.add_observer(self.ntfy_reachable,NTFY_REACHABLE,[NTFY_INSERT])

    def register(self):
        # Now trigger a buddycast exchange
        bc_core = BuddyCastFactory.getInstance().buddycast_core
        if bc_core:
            bc_core.register_proxy_peer_handler(self.proxy_peer_handler)
        else:
            if DEBUG:
                print >> sys.stderr, "ProxyPeerManager.register: the buddycast core was not initialized yet"

    def proxy_peer_handler(self, peer_permid):
        """ A proxy was discovered
            
            Called from buddycast.py when an peer with the proxyservice enabled is discovered.
        """
        if peer_permid not in self.available_proxies.keys():
            self.available_proxies[peer_permid] = None

            # notify the GUI
            from Tribler.Core.Session import Session
            session = Session.get_instance()
            session.uch.notify(NTFY_PROXYDISCOVERY, NTFY_INSERT, None, self.available_proxies.keys())

    def request_proxy(self, proxy_downloader):
        for proxy_permid in self.available_proxies.keys():
            if self.available_proxies[proxy_permid] == None:
                self.available_proxies[proxy_permid] = proxy_downloader
                return proxy_permid
        return None
    
    def release_proxy(self, proxy_permid):
        self.available_proxies[proxy_permid] = None

    def ol_connection_created_or_closed(self, subject, changeType, permid, *args):
        """  Handler registered with the session observer
        
        @param subject The subject to observe, one of NTFY_* subjects (see simpledefs).
        @param changeTypes The list of events to be notified of one of NTFY_* events.
        @param permid The specific object in the subject to monitor (e.g. a specific primary key in a database to monitor for updates.)
        @param args: A list of optional arguments.
        
        Called by callback threads with NTFY_CONNECTION, args[0] is boolean: connection opened/closed
        """

        if DEBUG:
            print >>sys.stderr, "ProxyPeerManager: ol_connection_created_or_closed"

        if not args[0]: # connection closed
            if permid in self.available_proxies.keys():
                proxy_downloader_instance = self.available_proxies[permid]
                if proxy_downloader_instance is not None:
                    proxy_downloader_instance.proxy_connection_closed(permid)
                    self.available_proxies[permid] = None
        else: # connection opened
            pass

    def ntfy_reachable(self, subject, changeType, permid, *args):
        """  Handler registered with the session observer. Halndler called when the NTFY_REACHABLE event is triggered.
        
        @param subject The subject to observe, one of NTFY_* subjects (see simpledefs).
        @param changeTypes The list of events to be notified of one of NTFY_* events.
        @param permid The specific object in the subject to monitor (e.g. a specific primary key in a database to monitor for updates.)
        @param args: A list of optional arguments.
        
        Called by callback threads with NTFY_CONNECTION, args[0] is boolean: connection opened/closed
        """

        if DEBUG:
            print >>sys.stderr, "ProxyPeerManager: ntfy_reachable"

        self.connectable = True
        
    def am_i_connectable(self):
        """ Called by home.py for the GUI debug panel
        """
        return self.connectable