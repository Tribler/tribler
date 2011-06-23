# Written by George Milescu
# see LICENSE.txt for license information
#

from traceback import print_exc
import copy
import sys
from collections import deque
from threading import Lock

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, TorrentDBHandler
from Tribler.Core.Overlay.SecureOverlay import OverlayConnection
from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.ProxyService.ProxyServiceUtil import *
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint
from mailcap import show

# Print debug messages
DEBUG = False

class Doe:
    def __init__(self, infohash, num_pieces, btdownloader, proxydownloader, encoder):
        # Number of pieces in the torrent
        self.num_pieces = num_pieces
        
        # Torrent infohash
        self.infohash = infohash # readonly so no locking on this

        # List of proxies that have been asked to relay but have not confirmed yet 
        # deque is thread-safe
        self.asked_proxies = deque()
        
        # List of confirmed proxies 
        # deque is thread-safe
        self.confirmed_proxies = deque()
        
        # Dictionary for keeping evidence of proxies and the pieces requested to them
        # Key: permid of a proxy
        # Value: list of pieces requested to that proxy 
        self.requested_pieces = {}
        
        # Tribler overlay warm
        self.overlay_bridge = OverlayThreadingBridge.getInstance()
        
        # BT1Download object
        self.btdownloader = btdownloader
        self.proxydownloader = proxydownloader
        
        # Encoder object
        self.encoder = encoder


    #
    # Send messages
    # 
    def send_relay_request(self, permid_list, force = False):
        """ Asks all the peers in peerList (that have not been asked before) to relay data
        
        @param permid_list: A list of permids for the peers that will be contacted to relay
        @param force: If True, all the peers in peerList will be contacted to relay, regardless of previous relay requests being sent to them 
        """
        if DEBUG:
            for permid in permid_list:
                print >> sys.stderr, "doe: i was requested to send relay request to", show_permid_short(permid)
                
        try:
            # List of new proxies (maybe some of the proxies in permid_list are active proxies)
            new_proxies = []

            # TODO: if a candidate is in the asked_proxies list, remember the last time it was asked to relay
            # and wait for a timeout before asking it again
            
            # Check which of the candidate proxies is already a proxy
            for permid in permid_list:
                if not permid in self.confirmed_proxies:
                    # candidate has never been asked to relay
                    new_proxies.append(permid)
                    # Extend the list of asked proxies
                    # The list is extended and not appended because the candidate might already be in
                    # this list from previous attempts to contact it for relaying
                    self.asked_proxies.append(permid)

            # Send the relay request
            olthread_send_relay_request_lambda = lambda:self.olthread_send_relay_request(new_proxies)
            self.overlay_bridge.add_task(olthread_send_relay_request_lambda,0)
        except Exception,e:
            print_exc()
            print >> sys.stderr, "doe: Exception while sending a relay request", e

    def olthread_send_relay_request(self, permidlist):
        """ Creates a bridge connection for the relay request to be sent
        
        Called by the overlay thread.
        
        @param permidlist: A list of permids for the peers that will be contacted for relaying
        """
        
        def caller(permid):
            if DEBUG:
                print >> sys.stderr, "doe: olthread_send_relay_request connecting to", show_permid_short(permid)
            
            # Connect to the peer designated by permid
            self.overlay_bridge.connect(permid, self.olthread_relay_request_connect_callback)
        
        # workaround for using the lambda function in a separate namespace
        for permid in permidlist:
            caller(permid)

    def olthread_relay_request_connect_callback(self, exc, dns, permid, selversion):
        """ Sends the relay request message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the peer that is contacted for relaying
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_relay_request_connect_callback sending relay request to", show_permid_short(permid)
            
            # Create message according to protocol version
            message = RELAY_REQUEST + self.infohash
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_relay_request_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_relay_request_connect_callback: error connecting to", show_permid_short(permid), exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    def olthread_relay_request_send_callback(self,exc,permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for relaying
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_relay_request_send_callback: error sending to", show_permid_short(permid), exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)


    def send_stop_relaying(self, permid_list, force = False):
        """ Asks for all the peers in peerList to stop relaying
        
        @param permid_list: A list of permids for the peers that will be asked to stop relaying
        @param force: If True, all the peers in peerList will be asked to stop relaying, regardless of previous relay requests being sent to them 
        """
        if DEBUG:
            for permid in permid_list:
                print >> sys.stderr, "doe: i was requested to send a stop relaying request to", show_permid_short(permid)

        try:
            # Who in the peerList is actually a proxy currently?
            # List of peers that will be asked to stop relaying
            old_proxies = []
            
            # Search and update the confirmed_proxies list
            for permid in permid_list:
                # For each candidate
                # Search the candidate in the confirmed_proxies list
                if permid in self.confirmed_proxies: 
                    old_proxies.append(permid)
                    self.confirmed_proxies.remove(permid)
                
                if permid in self.asked_proxies:
                    old_proxies.append(permid)
                    self.asked_proxies.remove(permid)

            # Ask peers to stop relaying
            olthread_send_stop_relaying_lambda = lambda:self.olthread_send_stop_relaying(old_proxies)
            self.overlay_bridge.add_task(olthread_send_stop_relaying_lambda, 0)
        except Exception,e:
            print_exc()
            print >> sys.stderr, "doe: Exception in send_stop_relaying", e

    def olthread_send_stop_relaying(self, permidlist):
        """ Creates a bridge connection for the stop relaying request to be sent
        
        Called by the overlay thread.
        
        @param permidlist: list of the peer permid's to be asked to stop relaying
        """
        
        def caller(permid):
            if DEBUG:
                print >> sys.stderr, "doe: error connecting to", show_permid_short(permid), "for stop relaying"
            
            self.overlay_bridge.connect(permid, self.olthread_stop_relaying_connect_callback)
        
        # workaround for using the lambda function in a separate namespace
        for permid in permidlist:
            caller(permid)

    def olthread_stop_relaying_connect_callback(self, exc, dns, permid, selversion):
        """ Sends the stop relaying message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the peer that is contacted to stop relaying
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Peer is reachable
            ## Create message according to protocol version
            message = STOP_RELAYING + self.infohash
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_stop_relaying_send_callback)
        elif DEBUG:
            # Peer is not reachable
            print >> sys.stderr, "doe: olthread_stop_relaying_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_stop_relaying_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted to stop relaying
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: STOP_RELAYING: error sending to", show_permid_short(permid), exc
            
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)


    def send_download_piece(self, piece, proxy_permid):
        """ Send a message to request the piece to the proxy

        TODO: update the line below 
        Called by _request() in ProxyDownloader
        
        @param piece: The piece that will be requested to one of the proxies
        @param proxy_permid: The permid of the proxy that will be requested for the piece
        """
        if DEBUG:
            print >>sys.stderr, "doe: send_request_piece: will send a request for piece", piece, "to", show_permid_short(proxy_permid)
                
        try:
            # Store the proxy identification data and the piece requested to it
            if proxy_permid in self.requested_pieces.keys():
                # The peer is already in the dictionary: a previous request was sent to it
                # Check if the piece was not requested before
                if piece in self.requested_pieces[proxy_permid]:
                    # The piece has already been requested to that proxy. No re-requests in this version
                    if DEBUG:
                        print >> sys.stderr, "doe: send_request_piece: piece", piece, "was already requested to this proxy before"
                    return
                self.requested_pieces[proxy_permid].append(piece)
            else:
                # The peer is not in the dictionary: no previous requests were sent to it
                self.requested_pieces[proxy_permid] = deque([piece])

            # Sent the request message to the proxy
            olthread_send_download_piece_lambda = lambda:self.olthread_send_download_piece(piece, proxy_permid)
            self.overlay_bridge.add_task(olthread_send_download_piece_lambda,0)
            
            # ProxyService 90s Test_
            from Tribler.Core.Statistics.Status.Status import get_status_holder
            status = get_status_holder("Proxy90secondsTest")
            status.create_and_add_event("requested-piece-to-proxy", [show_permid_short(proxy_permid), piece])
            # _ProxyService 90s Test
            
        except Exception,e:
            print_exc()
            print >> sys.stderr, "doe: Exception while requesting piece", piece, e

    def olthread_send_download_piece(self, piece, permid):
        """ Creates a bridge connection for the piece request message to be sent
        
        Called by the overlay thread.
        
        @param piece: The piece that will be requested
        @param permid: The permid of the peer that will be contacted
        """
        if DEBUG:
            print >> sys.stderr, "doe: olthread_send_download_piece connecting to", show_permid_short(permid), "to request piece", piece
        
        # Connect to the peer designated by permid
        olthread_download_piece_connect_callback_lambda = lambda e,d,p,s:self.olthread_download_piece_connect_callback(e, d, p, s, piece)
        self.overlay_bridge.connect(permid, olthread_download_piece_connect_callback_lambda)

    def olthread_download_piece_connect_callback(self, exc, dns, permid, selversion, piece):
        """ Sends the download_piece message on the connection with the proxy
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the proxy that is requested a piece
        @param peice: the requested piece 
        @param selversion: selected Overlay protocol version
        """
        
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_download_piece_connect_callback sending download request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = DOWNLOAD_PIECE + self.infohash + tobinary(piece)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_download_piece_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_download_piece_connect_callback: error connecting to", show_permid_short(permid), exc
            
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    def olthread_download_piece_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted to download a piece
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_download_piece_send_callback: error sending to", show_permid_short(permid), exc
            
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)


    def send_cancel_downloading_piece(self, piece, proxy_permid):
        """ Send a cancel downloading message for the specified piece to the proxy
        
        Called by ProxyDownloader:check_outstanding_requests
        
        @param piece: The piece that will be canceled to the respective proxy
        @param proxy_permid: The permid of the proxy that will be requested to cancel the download
        """
        if DEBUG:
            print >> sys.stderr, "doe: i will cancel the download request for piece", piece, "to proxy", show_permid_short(proxy_permid)
            
        try:
            # Check if the piece was reserved before to that proxy
            if piece not in self.requested_pieces[proxy_permid]:
                if DEBUG:
                    print >> sys.stderr, "doe: piece", piece, "was not previously requested to this peer"
                return
            else:
                self.requested_pieces[proxy_permid].remove(piece)
            
            # Sent the cancel message to the proxy
            olthread_send_cancel_downloading_piece_lambda = lambda:self.olthread_send_cancel_downloading_piece(proxy_permid, piece)
            self.overlay_bridge.add_task(olthread_send_cancel_downloading_piece_lambda, 0)
        except Exception, e:
            print_exc()
            print >> sys.stderr, "doe: Exception while canceling request for piece", piece, e

    def olthread_send_cancel_downloading_piece(self, permid, piece):
        """ Creates a bridge connection for the piece cancel message to be sent
        
        Called by the overlay thread.
        
        @param permid: The permid of the peer that will be contacted
        @param piece: The piece that will be canceled
        """
        if DEBUG:
            print >> sys.stderr, "doe: olthread_send_cancel_downloading_piece connecting to", show_permid_short(permid), "to cancel piece", piece
        # Connect to the peer designated by permid
        olthread_cancel_downloading_piece_connect_callback_lambda = lambda e,d,p,s:self.olthread_cancel_downloading_piece_connect_callback(e, d, p, s, piece)
        self.overlay_bridge.connect(permid, olthread_cancel_downloading_piece_connect_callback_lambda)


    def olthread_cancel_downloading_piece_connect_callback(self, exc, dns, permid, selversion, piece):
        """ Sends the cancel piece message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the proxy that is requested to cancel downloading a piece
        @param peice: the canceled piece 
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_downloading_piece_connect_callback sending a cancel request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = CANCEL_DOWNLOADING_PIECE + self.infohash + tobinary(piece)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_cancel_downloading_piece_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_downloading_piece_connect_callback: error connecting to", show_permid_short(permid), exc

            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    def olthread_cancel_downloading_piece_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the proxy that is contacted to cancel downloading a piece
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_downloading_piece_send_callback: error sending to", show_permid_short(permid), exc

            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)


    def send_upload_piece(self, piece, piece_data, proxy_permid):
        """ Send a message to request the upload of a piece to the proxy

        TODO: update the line below 
        Called by _request() in ProxyDownloader
        
        @param piece: The piece that will be uploaded by one of the proxies
        @param piece_data: The piece data
        @param proxy_permid: The permid of the proxy that will be requested to upload the piece
        """
        if DEBUG:
            print >>sys.stderr, "doe: send_upload_piece: will send a request to upload piece", piece, "to", show_permid_short(proxy_permid)
                
        try:
            #TODO: piece management
            
            # Sent the request message to the proxy
            olthread_send_upload_piece_lambda = lambda:self.olthread_send_upload_piece(piece, piece_data, proxy_permid)
            self.overlay_bridge.add_task(olthread_send_upload_piece_lambda,0)
            
        except Exception,e:
            print_exc()
            print >> sys.stderr, "doe: Exception while requesting upload for piece", piece, e

    def olthread_send_upload_piece(self, piece, piece_data, permid):
        """ Creates a bridge connection for the piece upload request message to be sent
        
        Called by the overlay thread.
        
        @param piece: The piece that will be requested
        @param piece_data: The piece data 
        @param permid: The permid of the peer that will be contacted
        """
        if DEBUG:
            print >> sys.stderr, "doe: olthread_send_upload_piece connecting to", show_permid_short(permid), "to request piece", piece
        
        # Connect to the peer designated by permid
        olthread_upload_piece_connect_callback_lambda = lambda e,d,p,s:self.olthread_upload_piece_connect_callback(e, d, p, s, piece, piece_data)
        self.overlay_bridge.connect(permid, olthread_upload_piece_connect_callback_lambda)

    def olthread_upload_piece_connect_callback(self, exc, dns, permid, selversion, piece, piece_data):
        """ Sends the upload_piece message on the connection with the proxy
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the proxy that is requested a piece
        @param piece: the requested piece
        @param piece_data: The piece data 
        @param selversion: selected Overlay protocol version
        """
        
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_upload_piece_connect_callback sending upload request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = UPLOAD_PIECE + self.infohash + tobinary(piece) + piece_data[0:].tostring()
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_upload_piece_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_upload_piece_connect_callback: error connecting to", show_permid_short(permid), exc
            
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    def olthread_upload_piece_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted to upload a piece
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_upload_piece_send_callback: error sending to", show_permid_short(permid), exc
            
            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)


    def send_cancel_uploading_piece(self, piece, proxy_permid):
        """ Send a cancel uploading message for the specified piece to the proxy
        
        TODO: Called by ... 
        
        @param piece: The piece that will be canceled to the respective proxy
        @param proxy_permid: The permid of the proxy that will be requested to cancel the download
        """
        if DEBUG:
            print >> sys.stderr, "doe: i will cancel the upload request for piece", piece
            
        try:
            # TODO: piece management 
            
            # Sent the cancel message to the proxy
            olthread_send_cancel_uploading_piece_lambda = lambda:self.olthread_send_cancel_uploading_piece(proxy_permid, piece)
            self.overlay_bridge.add_task(olthread_send_cancel_uploading_piece_lambda, 0)
        except Exception, e:
            print_exc()
            print >> sys.stderr, "doe: Exception while canceling upload request for piece", piece, e

    def olthread_send_cancel_uploading_piece(self, permid, piece):
        """ Creates a bridge connection for the piece upload cancel message to be sent
        
        Called by the overlay thread.
        
        @param permid: The permid of the peer that will be contacted
        @param piece: The piece that will be canceled
        """
        if DEBUG:
            print >> sys.stderr, "doe: olthread_send_cancel_uploading_piece connecting to", show_permid_short(permid), "to cancel piece", piece
        # Connect to the peer designated by permid
        olthread_cancel_uploading_piece_connect_callback_lambda = lambda e,d,p,s:self.olthread_cancel_uploading_piece_connect_callback(e, d, p, s, piece)
        self.overlay_bridge.connect(permid, olthread_cancel_uploading_piece_connect_callback_lambda)

    def olthread_cancel_uploading_piece_connect_callback(self, exc, dns, permid, piece, selversion):
        """ Sends the cancel upload piece message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the proxy that is requested to cancel uploading a piece
        @param piece: the canceled piece number 
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_uploading_piece_connect_callback sending a cancel request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = CANCEL_UPLOADING_PIECE + self.infohash + tobinary(piece)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_cancel_uploading_piece_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_uploading_piece_connect_callback: error connecting to", show_permid_short(permid), exc

            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    def olthread_cancel_uploading_piece_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the proxy that is contacted to cancel uploading a piece
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "doe: olthread_cancel_uploading_piece_send_callback: error sending to", show_permid_short(permid), exc

            # Remove peer from the list of asked peers
            self.remove_unreachable_proxy(permid)

    
    #
    # Got (received) messages
    # 
    def got_relay_accepted(self, permid, selversion):
        """ Mark the peer as an active proxy
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a RELAY_ACCEPTED message from", show_permid_short(permid)

        #Search the peer in the asked_proxies list, remove it from there, and put it in the confirmed_proxies list.
        if permid in self.asked_proxies:
            self.asked_proxies.remove(permid)
        self.confirmed_proxies.append(permid)
        
        # Create a new SingleDownload instance in the ProxyDownloader
        self.proxydownloader.make_download(permid)


    def got_relay_dropped(self, permid, selversion):
        """ Remove the peer from the list of active proxies (and form the list of asked proxies)
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a RELAY_DROPPED message from", show_permid_short(permid)

        #Search the peer in the asked_proxies list and remove it from there
        if permid in self.asked_proxies:
            self.asked_proxies.remove(permid)

        #Search the peer in the confirmed_proxies list and remove it from there
        if permid in self.confirmed_proxies:
            self.confirmed_proxies.remove(permid)


    def got_dropped_piece(self, permid, selversion, piece):
        """ TODO:
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        @param peice: The piece that is dropped
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a DROPPED_PIECE message from", show_permid_short(permid)

        # TODO:
        pass


    def got_proxy_have(self, permid, selversion, aggregated_string):
        """ Take the list of pieces the proxy sent and combine it with the numhaves in the piece picker
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of available pieces built by the proxy based on HAVE messages it received
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a PROXY_HAVE message from", show_permid_short(permid)

        # TODO: make this test using a different approach
#        if len(aggregated_string) != self.num_pieces:
#            print >> sys.stderr, "doe: got_proxy_have: invalid payload in received PROXY_HAVE message. self.num_pieces=", self.num_pieces, "len(aggregated_string)=", len(aggregated_string)

        # Search for the SingleDownload object that has the connection with this peer
        if DEBUG:
            debug_found_connection = False
        
        for single_dl in self.proxydownloader.downloads:
            if permid == single_dl.proxy_permid:
                # If the connection is found, replace the bitfield information
                single_dl.proxy_have = Bitfield(length=self.btdownloader.numpieces, bitstring=aggregated_string)
                sys.stdout.flush()
                if DEBUG:
                    debug_found_connection = True
                break

        if DEBUG:
            if debug_found_connection:
                print >> sys.stderr, "doe: got_proxy_have: found a single_dl for the received PROXY_HAVE"
            else:
                print >> sys.stderr, "doe: got_proxy_have: no single_dl for the received PROXY_HAVE has been found"


    def got_proxy_unhave(self, permid, selversion, aggregated_string):
        """ Take the list of pieces the proxy sent and combine it with the numhaves in the piece picker
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of available pieces built by the proxy based on UNHAVE messages it received
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a PROXY_UNHAVE message from", show_permid_short(permid)

        # TODO: make this test using a different approach
#        if len(aggregated_string) != self.num_pieces:
#            print >> sys.stderr, "doe: got_proxy_have: invalid payload in received PROXY_HAVE message. self.num_pieces=", self.num_pieces, "len(aggregated_string)=", len(aggregated_string)

        # Search for the SingleDownload object that has the connection with this peer
        if DEBUG:
            debug_found_connection = False
        
        for single_dl in self.proxydownloader.downloads:
            if permid == single_dl.proxy_permid:
                # If the connection is found, add the piece_list information to the d.have information
                single_dl.proxy_have = Bitfield(length=self.btdownloader.numpieces, bitstring=aggregated_string)
                if DEBUG:
                    debug_found_connection = True
                break

        if DEBUG:
            if debug_found_connection:
                print >> sys.stderr, "doe: got_proxy_unhave: found a data connection for the received PROXY_UNHAVE"
            else:
                print >> sys.stderr, "doe: got_proxy_unhave: no data connection for the received PROXY_UNHAVE has been found"


    def got_piece_data(self, permid, selversion, piece, piece_data):
        """ Find the SingleDownload object for the sending permid and pass the data to it.
        
        @param permid: The permid of the node sending the message
        @param selversion: selected Overlay protocol version
        @param piece: The piece number that is sent 
        @param piece_data: The piece data that is sent
        """
        if DEBUG:
            print >> sys.stderr, "doe: received a PIECE_DATA message from", show_permid_short(permid)

        # Search for the SingleDownload object that has the connection with this peer
        if DEBUG:
            debug_found_connection = False
        
        for single_dl in self.proxydownloader.downloads:
            if permid == single_dl.proxy_permid:
                # If the connection is found, add the piece_list information to the d.have information
                single_dl.received_data[piece] = piece_data
                single_dl.request_finished(piece)

                # ProxyService 90s Test_
                from Tribler.Core.Statistics.Status.Status import get_status_holder
                status = get_status_holder("Proxy90secondsTest")
                status.create_and_add_event("downloaded-piece", [piece, show_permid_short(permid)])
                # _ProxyService 90s Test
                
                if DEBUG:
                    debug_found_connection = True
                break

        if DEBUG:
            if debug_found_connection:
                print >> sys.stderr, "doe: got_piece_data: found a data connection for the received PIECE_DATA"
            else:
                print >> sys.stderr, "doe: got_piece_data: no data connection for the received PIECE_DATA has been found"


    #
    # Util functions
    # 
    def remove_unreachable_proxy(self, permid):
        """ Remove a proxy that is no loger reachable
        
        Called by the overlay thread.
        
        @param permid: the permid of the peer to be removed from the list
        """
        if permid in self.asked_proxies:
            self.asked_proxies.remove(permid)
            
        if permid in self.confirmed_proxies:
            self.confirmed_proxies.remove(permid)
            
        if permid in self.requested_pieces.keys():
            del(self.requested_pieces[permid])


    def network_get_asked_proxies_copy(self):
        """ Returns a COPY of the list.
        
        Called by SingleDownload.get_stats()
        """
        if DEBUG:
            print >> sys.stderr, "doe: network_get_asked_proxies_copy: Number of proxies:", len(self.confirmed_proxies)
        return list(self.confirmed_proxies)

    def get_nr_used_proxies(self):
        """ Called by home.py for the GUI debug panel
        """
        return len(self.confirmed_proxies)
