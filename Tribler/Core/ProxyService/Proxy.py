# Written by George Milescu
# see LICENSE.txt for license information

import sys
import time
from traceback import print_exc
from collections import deque
from threading import Lock

from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.simpledefs import *

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, TorrentDBHandler 
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.ProxyService.ProxyServiceUtil import *
from Tribler.Core.BitTornado.BT1.convert import tobinary,toint

DEBUG = False

class Proxy:
    def __init__(self, infohash, num_pieces, btdownloader, proxydownloader, encoder):
        
        self.infohash = infohash
        self.num_pieces = num_pieces

        # The doe_nodes is a list that stores the permids if the doe nodes
        self.doe_nodes = deque()
        
        # Strores the pieces requested by each permid
        self.requested_pieces = {}
        
        # Stores the pieces sent to each permid
        self.delivered_pieces = {}
        
        # Stores the pieces dropped to each permid
        self.dropped_pieces = {}

        # list of pieces requested by the doe and not passed to the bittorrent engine yet
        # deque is thread-safe
        self.current_requests = deque()
        
        # list of pieces passed to the bittorrent engine for retrieving
        # deque is thread-safe
        self.currently_downloading_pieces = deque()

        self.counter = 0
        self.completed = False
        self.marker = [True] * num_pieces
        self.round = 0

        self.btdownloader = btdownloader
        self.proxydownloader = proxydownloader
        self.encoder = encoder
        
        self.overlay_bridge = OverlayThreadingBridge.getInstance()

#        self.continuations = []
#        self.outstanding = None
        self.last_req_time = 0
        
        
    def test(self):
        result = self.reserve_piece(10, None)
        print >> sys.stderr,"reserve piece returned: " + str(result)
        print >> sys.stderr,"Test passed"

    #
    # Send messages
    # 
    def send_relay_accepted(self, permid):
        """ Send a confirmation to the doe that the current node will provide proxy services
        
        Called by self.got_relay_request()
        
        @param permid: The permid of the node that will become a doe
        """

        if DEBUG:
            print >> sys.stderr,"proxy: send_relay_accepted: sending a RELAY_ACCEPTED message to", show_permid_short(permid)

        olthread_send_relay_accepted_lambda = lambda:self.olthread_send_relay_accepted(permid)
        self.overlay_bridge.add_task(olthread_send_relay_accepted_lambda,0)
        
    def olthread_send_relay_accepted(self, permid):
        """ Creates a bridge connection for the relay accepted message to be sent
        
        Called by the overlay thread.
        """
        # TODO: ??? We need to create the message according to protocol version, so need to pass all info.
        olthread_relay_accepted_connect_callback_lambda = lambda e,d,p,s:self.olthread_request_accepted_connect_callback(e, d, p, s)
        self.overlay_bridge.connect(permid,olthread_relay_accepted_connect_callback_lambda)

    def olthread_request_accepted_connect_callback(self, exc, dns, permid, selversion):
        """ Sends the relay accepted message on the connection with the doe
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Create the piece status data structures
            self.requested_pieces[permid] = [False] * self.num_pieces
            self.delivered_pieces[permid] = [False] * self.num_pieces
            self.dropped_pieces[permid] = [False] * self.num_pieces
            
            # Create message according to protocol version
            message = RELAY_ACCEPTED + self.infohash

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_request_accepted_connect_callback: Sending RELAY_ACCEPTED to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_relay_accepted_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_request_accepted_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_relay_accepted_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the doe
        """

        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_relay_accepted_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    def send_relay_dropped(self, permid):
        """ Send a message to the doe that the current node will stop providing proxy services
        
        Called by TODO:
        
        @param permid: The permid of the doe
        """

        if DEBUG:
            print "proxy: send_relay_dropped: sending a RELAY_DROPPED message to", permid

        olthread_send_relay_dropped_lambda = lambda:self.olthread_send_relay_dropped(permid)
        self.overlay_bridge.add_task(olthread_send_relay_dropped_lambda,0)
        
    def olthread_send_relay_dropped(self, permid):
        """ Creates a bridge connection for the relay dropped message to be sent
        
        Called by the overlay thread.
        """
        olthread_relay_dropped_connect_callback_lambda = lambda e,d,p,s:self.olthread_relay_dropped_connect_callback(e, d, p, s)
        self.overlay_bridge.connect(permid,olthread_relay_dropped_connect_callback_lambda)

    def olthread_relay_dropped_connect_callback(self, exc, dns, permid, selversion):
        """ Sends the relay dropped message on the connection with the doe
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        """
        if exc is None:
            # Create message according to protocol version
            message = RELAY_DROPPED + self.infohash

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_relay_dropped_connect_callback: Sending RELAY_DROPPED to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_relay_dropped_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_relay_dropped_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_relay_dropped_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the doe
        """
        
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_relay_dropped_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    def send_dropped_piece(self, permid, piece):
        """ Send a message to the doe that the current node has dropped relaying a piece
        
        Called by TODO:
        
        @param permid: The permid of the doe
        @param piece: The number of the piece that will not be relayed
        """

        if DEBUG:
            print "proxy: send_dropped_piece: sending a DROPPED_PIECE message to", permid

        olthread_send_dropped_piece_lambda = lambda:self.olthread_send_dropped_piece(permid, piece)
        self.overlay_bridge.add_task(olthread_send_dropped_piece_lambda, 0)
        
    def olthread_send_dropped_piece(self, permid, piece):
        """ Creates a bridge connection for the dropped piece message to be sent
        
        Called by the overlay thread.
        @param permid: The permid of the doe
        @param piece: The number of the piece that will not be relayed
        """
        olthread_dropped_piece_connect_callback_lambda = lambda e,d,p,s:self.olthread_dropped_piece_connect_callback(e, d, p, s, piece)
        self.overlay_bridge.connect(permid, olthread_dropped_piece_connect_callback_lambda)

    def olthread_dropped_piece_connect_callback(self, exc, dns, permid, selversion, piece):
        """ Sends the dropped piece message on the connection with the doe
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        @param piece: The number of the piece that will not be relayed
        """
        if exc is None:
            # Store the piece status
            self.dropped_pieces[permid][piece] = True
            
            # Create message according to protocol version
            message = DROPPED_PIECE + self.infohash + tobinary(piece)

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_dropped_piece_connect_callback: Sending DROPPED_PIECE to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_dropped_piece_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_relay_dropped_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_dropped_piece_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the doe
        """
        
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_dropped_piece_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    def send_proxy_have(self, aggregated_haves):
        """ Send a list of aggregated have and bitfield information
        
        Called by Downloader.aggregate_and_send_haves
        
        @param aggregated_haves: A Bitfield object, containing an aggregated list of stored haves
        """

        if DEBUG:
            print >> sys.stderr, "proxy: send_proxy_have: sending a proxy_have message to all", len(self.doe_nodes), "doe nodes"

        aggregated_string = aggregated_haves.tostring()
        olthread_send_proxy_have_lambda = lambda:self.olthread_send_proxy_have(list(self.doe_nodes), aggregated_string)
        self.overlay_bridge.add_task(olthread_send_proxy_have_lambda,0)
        
    def olthread_send_proxy_have(self, permid_list, aggregated_string):
        """ Creates a bridge connection for the PROXY_HAVE message to be sent
        
        Called by the overlay thread.
        
        @param permid_list: a list of doe permids
        @param aggregated_string: a bitstring of available piesces
        """

        def caller(permid):
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_send_proxy_have: Sending PROXY_HAVE to", show_permid_short(permid)
    
            # TODO: ??? We need to create the message according to protocol version, so need to pass all info.
            olthread_proxy_have_connect_callback_lambda = lambda e,d,p,s:self.olthread_proxy_have_connect_callback(e, d, p, s, aggregated_string)
            self.overlay_bridge.connect(permid, olthread_proxy_have_connect_callback_lambda)
        
        # workaround for using the lambda function in a separate namespace
        for permid in permid_list:
            caller(permid)

    def olthread_proxy_have_connect_callback(self, exc, dns, permid, selversion, aggregated_string):
        """ Sends the proxy_have message on the connection with the doe
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of available pieces
        """
        if exc is None:
            # Create message according to protocol version
            message = PROXY_HAVE + self.infohash + bencode(aggregated_string)

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_proxy_have_connect_callback: Sending PROXY_HAVE to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_proxy_have_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_proxy_have_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_proxy_have_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for relaying
        """

        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_proxy_have_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    def send_proxy_unhave(self, aggregated_haves):
        """ Send a list of aggregated have and bitfield information
        
        Called by TODO:
        
        @param aggregated_haves: A Bitfield object, containing an aggregated list of stored haves
        """

        if DEBUG:
            print >> sys.stderr, "proxy: send_proxy_unhave: sending a proxy_unhave message to all", len(self.doe_nodes), "doe nodes"

        aggregated_string = aggregated_haves.tostring()
        olthread_send_proxy_unhave_lambda = lambda:self.olthread_send_proxy_unhave(list(self.doe_nodes), aggregated_string)
        self.overlay_bridge.add_task(olthread_send_proxy_unhave_lambda,0)
        
    def olthread_send_proxy_unhave(self, permid_list, aggregated_string):
        """ Creates a bridge connection for the PROXY_UNHAVE message to be sent
        
        Called by the overlay thread.
        
        @param permid_list: a list of doe permids
        @param aggregated_string: a bitstring of available piesces
        """

        def caller(permid):
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_send_proxy_unhave: Sending PROXY_UNHAVE to", show_permid_short(permid)
    
            # TODO: ??? We need to create the message according to protocol version, so need to pass all info.
            olthread_proxy_unhave_connect_callback_lambda = lambda e,d,p,s:self.olthread_proxy_unhave_connect_callback(e, d, p, s, aggregated_string)
            self.overlay_bridge.connect(permid, olthread_proxy_unhave_connect_callback_lambda)
        
        # workaround for using the lambda function in a separate namespace
        for permid in permid_list:
            caller(permid)

    def olthread_proxy_unhave_connect_callback(self, exc, dns, permid, selversion, aggregated_string):
        """ Sends the proxy_unhave message on the connection with the doe
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        @param aggregated_string: a bitstring of available pieces
        """
        if exc is None:
            # Create message according to protocol version
            message = PROXY_HAVE + self.infohash + bencode(aggregated_string)

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_proxy_unhave_connect_callback: Sending PROXY_UNHAVE to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_proxy_unhave_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_proxy_unhave_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_proxy_unhave_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for relaying
        """

        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_proxy_unhave_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    def send_piece_data(self, permid_list, piece_number, piece_data):
        """ Send the piece_data to the doe nodes in permid_list
        
        Called by self.retrieved_piece:
        
        @param permid_list: A list of doe permids
        @param piece_number: The number of the transmitted piece
        @param piece_data: The piece data
        """
        if DEBUG:
            for permid in permid_list:
                print >> sys.stderr,"proxy: send_piece_data: sending a PIECE_DATA message for", piece_number, "to", show_permid_short(permid)

        olthread_send_piece_data_lambda = lambda:self.olthread_send_piece_data(permid_list, piece_number, piece_data)
        self.overlay_bridge.add_task(olthread_send_piece_data_lambda,0)
        
    def olthread_send_piece_data(self, permid_list, piece_number, piece_data):
        """ Creates a bridge connection for the piece data message to be sent
        
        Called by the overlay thread.

        @param permid_list: A list of doe permids
        @param piece_number: The number of the transmitted piece
        @param piece_data: The piece data
        """
        def caller(permid):
            # TODO: ??? We need to create the message according to protocol version, so need to pass all info.
            olthread_piece_data_connect_callback_lambda = lambda e,d,p,s:self.olthread_piece_data_connect_callback(e, d, p, s, piece_number, piece_data)
            self.overlay_bridge.connect(permid, olthread_piece_data_connect_callback_lambda)
            
        # workaround for using the lambda function in a separate namespace
        for permid in permid_list:
            caller(permid)

    def olthread_piece_data_connect_callback(self, exc, dns, permid, selversion, piece_number, piece_data):
        """ Sends the piece data message on the connections with the doe nodes
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the doe
        @param selversion: selected Overlay protocol version
        @param piece_number: The number of the transmitted piece
        @param piece_data: The piece data
        """

        if exc is None:
            # Update delivered_pieces informatio
            self.delivered_pieces[permid][piece_number] = True
            
            # Create message according to protocol version
            message = PIECE_DATA + self.infohash + tobinary(piece_number) + piece_data[0:].tostring()

            if DEBUG:
                print >> sys.stderr,"proxy: olthread_piece_data_connect_callback: Sending PIECE_DATA to", show_permid_short(permid)

            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_piece_data_send_callback)
        elif DEBUG:
            # The doe is unreachable
            print >> sys.stderr,"proxy: olthread_piece_data_connect_callback: error connecting to", show_permid_short(permid), exc

    def olthread_piece_data_send_callback(self, exc, permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the doe
        """

        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"proxy: olthread_piece_data_send_callback: error sending message to", show_permid_short(permid), exc
        pass


    #
    # Got (received) messages
    # 
    def got_relay_request(self, permid, infohash):
        """ Start relaying for a doe
        
        @param permid: The permid of the node sending the relay request message
        @param infohash: the infohash of the torrent for which relay is requested
        """
        if DEBUG:
            print >>sys.stderr, "proxy: got_relay_request: will answer to the relay request from", show_permid_short(permid)

        # Get doe ip and address
        self.doe_nodes.append(permid)
        
        # Send RELAY_ACCEPTED
        if DEBUG:
            print >>sys.stderr, "proxy: got_relay_request: received a relay request, going to send relay_accepted"
        
        self.send_relay_accepted(permid)
        
        if DEBUG:
            print >>sys.stderr,"proxy: got_relay_request: sending haves to all doe nodes"

        if self.btdownloader is not None:
            self.btdownloader.aggregate_and_send_haves()
            
        # Mark the current download as a proxy download
        self.proxydownloader.dlinstance.set_proxyservice_role(PROXYSERVICE_ROLE_PROXY)

        return True


    def got_stop_relaying(self, permid, infohash):
        """ Stop relaying for a doe
        
        @param permid: The permid of the node sending the message
        @param infohash: the infohash of the torrent for which relay is needed 
        """        
        #TODO: decide what to do here
        # if the number of doe nodes is 0 after removing permid
        # * self.proxydownloader.dlobject.set_proxyservice_role(PROXYSERVICE_ROLE_NONE)
        # * notify ProxyDownloader
        # * notify ProxuMessageHandler
        # * delete the singledownload if policy requires it
        return True


    def got_download_piece(self, permid, piece):
        """ A doe requested a piece
        
        @param permid: The permid of the node requesting the piece
        @param piece: a piece number, that will be downloaded 
        """
        if DEBUG:
            print "proxy: got_download_piece: received download_piece for piece", piece

        # Mark the piece as requested in the local data structures
        self.requested_pieces[permid][piece] = True
        
        if self.btdownloader.storage.do_I_have(piece):
            # The piece (actual piece, not chunk) is complete
            if DEBUG:
                print >>sys.stderr, "proxy: got_download_piece: the requested piece", piece, "is already downloaded"

            [piece_data, hash_list] = self.btdownloader.storage.get_piece(piece, 0, -1)
            self.retrieved_piece(piece, piece_data)
        else:
            # The piece must be downloaded
            # current_requests is a collections.deque, and hence is thread-safe
            self.current_requests.append(piece)
        

    def got_cancel_downloading_piece(self, permid, piece):
        """ Cancel downloading a piece for a doe
        
        @param permid: The permid of the node sending the message
        @param piece: a piece number, that will be cancelled from downloading 
        """        
        if DEBUG:
            print "proxy: got_cancel_downloading_piece: received cancel_downloading_piece for piece", piece

        # Mark the piece as not requested in the local data structures
        self.requested_pieces[permid][piece] = False
        
        to_remove = True
        for permid in self.requested_pieces.keys():
            if self.requested_pieces[permid][piece] == True:
                to_remove = False
        
        if to_remove:
            try:
                self.current_requests.remove(piece)
            except ValueError, strerror:
                # the piece was already removed from the list.
                # probably the piece was delivered while the cancel_downloading_piece
                # was sent 
                pass
        
        return True


    def got_upload_piece(self, permid, piece_number, piece_data):
        """ Start uploading a piece for a doe
        
        @param permid: The permid of the node sending the message
        @param piece_number: a piece number, that will be uploaded
        @param piece_data: the data that will be uploaded
        """        
        #TODO: decide what to do here
        return True


    def got_cancel_uploading_piece(self, permid, piece):
        """ Stop uploading a piece for a doe
        
        @param permid: The permid of the node sending the message
        @param piece: a piece number, that will be cancelled from uploading 
        """        
        #TODO: decide what to do here
        return True


    #
    # Util functions
    #
    def is_doe(self, permid):
        """ Check if the permid is among the current doe nodes
        
        @param permid: The permid to be checked if it is a doe
        @return: True, if the permid is among the current doe nodes; False, if the permid is not among the current doe nodes
        """
        
        if permid in self.doe_nodes:
            return True
        else:
            return False


    def next_request(self):
        """ Returns the next piece in the list of doe-requested pieces
        
        Called by the PiecePicker
        
        @return: a piece number, if there is a requested piece pending download; None, if there is no pending piece
        """
        if len(self.current_requests) == 0:
            if DEBUG:
                print >>sys.stderr,"proxy: next_request: currently i have no requested pieces. Returning None"
            return None
        else:
            # take a piece index from the queue
            next_piece = self.current_requests[0]
            
            if next_piece not in self.currently_downloading_pieces:
                # it is the first time this index was popped from the requests list
                self.currently_downloading_pieces.append(next_piece)

                if DEBUG:
                    print >>sys.stderr,"proxy: next_request: Returning piece number", next_piece
                    
                return next_piece
            
            # this next_piece is already in self.currently_downloading_pieces.
            # I started downloading it before
            if self.btdownloader.storage.do_I_have_requests(next_piece):
                # The piece is not completly downloaded
                if DEBUG:
                    print >>sys.stderr,"proxy: next_request: Returning piece number", next_piece

                return next_piece
            else:
                # the piece was downloaded, it will arrive shortly. Put it back at the end of the queue. 
                self.current_requests.rotate(1)

                if DEBUG:
                    print >>sys.stderr,"proxy: next_request: Returning piece number", None
                
                return None
             
        return None


    def retrieved_piece(self, index, piece_data):
        """ Piece number index was downloaded completly. Send it to the doe.
        
        Called from Downloader:got_piece
        """

        if DEBUG:
            print >>sys.stderr, "proxy: retrieved_piece: piece number", index, "was retrieved. Sending it to proxy."

        if index in self.currently_downloading_pieces:
            # The index may not be in this list if the piece was already downloaded before the doe requested it
            self.currently_downloading_pieces.remove(index)
        if index in self.current_requests:
            self.current_requests.remove(index)

        # send data to doe node
        dest = []
        for permid in self.requested_pieces.keys():
            if self.requested_pieces[permid][index] == True and self.delivered_pieces[permid][index] == False:
                dest.append(permid)

        self.send_piece_data(dest, index, piece_data)
