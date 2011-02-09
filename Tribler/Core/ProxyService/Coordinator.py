# Written by Pawel Garbacki, Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# TODO: when ASK_FOR_HELP cannot be sent, mark this in the interface

from traceback import print_exc
import copy
import sys
from threading import Lock

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.CacheDB.CacheDBHandler import PeerDBHandler, TorrentDBHandler
#from Tribler.Core.Session import Session
from Tribler.Core.Overlay.SecureOverlay import OverlayConnection
from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.BitTornado.BT1.MessageID import ASK_FOR_HELP, STOP_HELPING, REQUEST_PIECES, CANCEL_PIECE, JOIN_HELPERS, RESIGN_AS_HELPER, DROPPED_PIECE
from Tribler.Core.ProxyService.ProxyServiceUtil import *
from mailcap import show

# Print debug messages
DEBUG = False
# ???
MAX_ROUNDS = 137


class Coordinator:

    def __init__(self, infohash, num_pieces):
        # Number of pieces in the torrent
        self.num_pieces = num_pieces 
        
        # Vector for reserved-state infromation per piece
        self.reserved_pieces = [False] * num_pieces
        # Torrent infohash
        self.infohash = infohash # readonly so no locking on this

        # List of sent challenges 
        self.sent_challenges_by_challenge = {}
        self.sent_challenges_by_permid = {}

        # List of asked helpers 
        self.asked_helpers_lock = Lock()
        self.asked_helpers = [] # protected by asked_helpers_lock
        
        # List of confirmed helpers 
        self.confirmed_helpers_lock = Lock()
        self.confirmed_helpers = [] # protected by confirmed_helpers_lock
        
        # Dictionary for keeping evidence of helpers and the pieces requested to them
        # Key: permid of a helper
        # Value: list of pieces requested to the helper 
        self.requested_pieces = {} 
        
        # optimization
        # List of reserved pieces ???
        self.reserved = []
        
        # Tribler overlay warm
        self.overlay_bridge = OverlayThreadingBridge.getInstance()
        
        # BT1Download object
        self.downloader = None
        
        # Encoder object
        self.encoder = None


    #
    # Send messages
    # 

    #
    # Interface for Core API. 
    # 
    def send_ask_for_help(self, peerList, force = False):
        """ Asks for help to all the peers in peerList that have not been asked before
        
        Called by ask_coopdl_helpers in SingleDownload
        
        @param peerList: A list of peer objects for the peers that will be contacted for helping, containing ['permid','ip','port']
        @param force: If True, all the peers in peerList will be contacted for help, regardless of previous help requests being sent to them 
        """
        if DEBUG:
            for peer in peerList:
                print >> sys.stderr, "coordinator: i was requested to send help request to", show_permid_short(peer['permid'])
                
        try:
            # List of helpers to be contacted for help
            newly_asked_helpers = []
            if force:
                # Contact all peers for help, regardless of previous help requests being sent to them
                newly_asked_helpers = peerList
            else:
                # TODO: optimize the search below
                # TODO: if a candidate is in the asked_helpers list, remember the last time it was asked for help
                # and wait for a timeout before asking it again
                # Check which of the candidate helpers is already a helper
                self.confirmed_helpers_lock.acquire()
                try:
                    for candidate in peerList:
                        flag = 0
                        for confirmed_helper in self.confirmed_helpers:
                            if self.samePeer(candidate,confirmed_helper):
                                # the candidate is already a helper 
                                flag = 1
                                break
                            
                        if flag == 0:
                            # candidate has never been asked for help
                            newly_asked_helpers.append(candidate)
                            # Extend the list of asked helpers
                            # The list is extended and not appended because the candidate might already be in
                            # this list from previous attempts to contact it for helping
                            self.asked_helpers.append(candidate)
                finally:
                    self.confirmed_helpers_lock.release()

            # List of permid's for the peers to be asked for help
            permidlist = []
            for peer in newly_asked_helpers:
                # ???
                peer['round'] = 0
                permidlist.append(peer['permid'])
                
                # Generate a random challenge - random number on 8 bytes (62**8 possible combinations)
                challenge = generate_proxy_challenge()
                
                # Save permid - challenge pair
                self.sent_challenges_by_challenge[challenge] = peer['permid']
                self.sent_challenges_by_permid[peer['permid']] = challenge
                
            # Send the help request
            olthread_send_request_help_lambda = lambda:self.olthread_send_ask_for_help(permidlist)
            self.overlay_bridge.add_task(olthread_send_request_help_lambda,0)
        except Exception,e:
            print_exc()
            print >> sys.stderr, "coordinator: Exception while requesting help",e
        

    def olthread_send_ask_for_help(self,permidlist):
        """ Creates a bridge connection for the help request to be sent
        
        Called by the overlay thread.
        
        @param permidlist: A list of permids for the peers that will be contacted for helping
        """
        for permid in permidlist:
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_send_ask_for_help connecting to",show_permid_short(permid)
            
            # Connect to the peer designated by permid
            self.overlay_bridge.connect(permid,self.olthread_ask_for_help_connect_callback)


    def olthread_ask_for_help_connect_callback(self,exc,dns,permid,selversion):
        """ Sends the help request message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the peer that is contacted for helping
        @param selversion 
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_ask_for_help_connect_callback sending help request to",show_permid_short(permid)
            
            # get the peer challenge
            challenge = self.sent_challenges_by_permid[permid]
            
            # Create message according to protocol version
            message = ASK_FOR_HELP + self.infohash + bencode(challenge)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_ask_for_help_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_ask_for_help_connect_callback: error connecting to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    def olthread_ask_for_help_send_callback(self,exc,permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for helping
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_ask_for_help_send_callback: error sending to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    def remove_unreachable_helper(self,permid):
        """ Remove a peer from the list of asked helpers
        
        Called by the overlay thread.
        
        @param permid: the permid of the peer to be removed from the list
        """
        self.asked_helpers_lock.acquire()
        try:
            # Search the peers with permid != from the given permid
            new_asked_helpers = []
            for peer in self.asked_helpers:
                if peer['permid'] != permid:
                    new_asked_helpers.append(peer)
            self.asked_helpers = new_asked_helpers
        except Exception,e:
            print_exc()
            print >> sys.stderr, "coordinator: Exception in remove_unreachable_helper",e
        finally:
            self.asked_helpers_lock.release()





    def send_stop_helping(self,peerList, force = False):
        """ Asks for all the peers in peerList to stop helping
        
        Called by stop_coopdl_helpers in SingleDownload
        
        @param peerList: A list of peer objects (containing ['permid','ip','port']) for the peers that will be asked to stop helping
        @param force: If True, all the peers in peerList will be asked to stop helping for help, regardless of previous help requests being sent to them 
        """
        if DEBUG:
            for peer in peerList:
                print >> sys.stderr, "coordinator: i was requested to send a stop helping request to", show_permid_short(peer)
                

        # TODO: optimize the search below
        try:
            if force:
                # Tell all peers in the peerList to stop helping, regardless of previous help requests being sent to them
                to_stop_helpers = peerList
            else:
                # Who in the peerList is actually a helper currently?
                # List of peers that will be asked to stop helping
                to_stop_helpers = []
                
                
                # Searchv and update the confirmed_helpers list
                self.confirmed_helpers_lock.acquire()
                try:
                    for candidate in peerList:
                        # For each candidate
                        # Search the candidate in the confirmed_helpers list
                        for confirmed_helper in self.confirmed_helpers:
                            if self.samePeer(candidate, confirmed_helper):
                                # candidate was asked for help
                                to_stop_helpers.append(candidate)
                                break
    
                    # Who of the confirmed helpers gets to stay?
                    to_keep_helpers = []
                    for confirmed_helper in self.confirmed_helpers:
                        flag = 0
                        for candidate in to_stop_helpers:
                            if self.samePeer(candidate,confirmed_helper):
                                # candidate was asked for help
                                flag = 1
                                break
                        if flag == 0:
                            # candidate was not asked for help
                            to_keep_helpers.append(confirmed_helper)
        
                    # Update confirmed_helpers
                    self.confirmed_helpers = to_keep_helpers
                finally:
                    self.confirmed_helpers_lock.release()

                
                # Search and update the asked_helpers list
                self.asked_helpers_lock.acquire()
                try:
                    for candidate in peerList:
                        # Search the candidate in the asked_helpers list
                        # TODO: if the same helper is both in confirmed_helpers and asked_helepers
                        # than it will be added twice to the to_stop_helpers list 
                        for asked_helper in self.asked_helpers:
                            if self.samePeer(candidate, asked_helper):
                                # candidate was asked for help
                                to_stop_helpers.append(candidate)
                                break
                    # Who of the confirmed helpers gets to stay?
                    to_keep_helpers = []
                    for asked_helper in self.asked_helpers:
                        flag = 0
                        for candidate in to_stop_helpers:
                            if self.samePeer(candidate,asked_helper):
                                # candidate was asked for help
                                flag = 1
                                break
                        if flag == 0:
                            # candidate was not asked for help
                            to_keep_helpers.append(asked_helper)
        
                    # Update confirmed_helpers
                    self.asked_helpers = to_keep_helpers
                finally:
                    self.asked_helpers_lock.release()

            # List of permid's for the peers that are asked to stop helping 
            permidlist = []
            for peer in to_stop_helpers:
                permidlist.append(peer['permid'])

            # Ask peers to stop helping
            olthread_send_stop_help_lambda = lambda:self.olthread_send_stop_help(permidlist)
            self.overlay_bridge.add_task(olthread_send_stop_help_lambda,0)
        except Exception,e:
            print_exc()
            print >> sys.stderr, "coordinator: Exception in send_stop_helping",e


    def olthread_send_stop_help(self,permidlist):
        """ Creates a bridge connection for the stop helping request to be sent
        
        Called by the overlay thread.
        
        @param permidlist: list of the peer permid's to be asked to stop helping
        """
        for permid in permidlist:
            if DEBUG:
                print >> sys.stderr, "coordinator: error connecting to", show_permid_short(permid), "for stopping help"
            self.overlay_bridge.connect(permid,self.olthread_stop_help_connect_callback)


    def olthread_stop_help_connect_callback(self,exc,dns,permid,selversion):
        """ Sends the help request message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the peer that is contacted to stop helping
        @param selversion:
        """
        if exc is None:
            # Peer is reachable
            ## Create message according to protocol version
            message = STOP_HELPING + self.infohash
            self.overlay_bridge.send(permid, message, self.olthread_stop_help_send_callback)
        elif DEBUG:
            # Peer is not reachable
            print >> sys.stderr, "coordinator: olthread_stop_help_connect_callback: error connecting to",show_permid_short(permid),exc


    def olthread_stop_help_send_callback(self,exc,permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted to stop helping
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: STOP_HELPING: error sending to",show_permid_short(permid),exc





    def send_request_pieces(self, piece, peerid):
        """ Send messages to helpers to request the pieces in pieceList
        
        Called by next() in PiecePicker
        
        @param piece: The piece that will be requested to one of the helpers
        @param peerid: The peerid of the helper that will be requested for the piece
        """
        if DEBUG:
            print >>sys.stderr, "coordinator: send_request_pieces: will send requests for piece", piece
                
        try:
            # Choose one of the confirmed helpers
            chosen_permid = self.choose_helper(peerid);
            
            # Store the helper identification data and the piece requested to it
            if chosen_permid in self.requested_pieces:
                # The peer is already in the dictionary: a previous request was sent to it
                current_requested_pieces = self.requested_pieces.get(chosen_permid)
                # Check if the piece was not requested before
                if piece in current_requested_pieces:
                    # The piece has already been requested to that helper. No re-requests in this version
                    if DEBUG:
                        print >> sys.stderr, "coordinator: send_request_pieces: piece", piece, "was already requested to another helper"
                    return
                current_requested_pieces.append(piece)
                self.requested_pieces[chosen_permid] = current_requested_pieces
            else:
                # The peer is not in the dictionary: no previous requests were sent to it
                self.requested_pieces[chosen_permid] = [piece]

            # Sent the request message to the helper
            olthread_send_request_help_lambda = lambda:self.olthread_send_request_pieces(chosen_permid, piece)
            self.overlay_bridge.add_task(olthread_send_request_help_lambda,0)
            
            # ProxyService 90s Test_
            #from Tribler.Core.Statistics.Status.Status import get_status_holder
            #status = get_status_holder("Proxy90secondsTest")
            #status.create_and_add_event("requested-piece-to-proxy", [show_permid_short(chosen_permid), piece])
            # ProxyService 90s Test_
            
        except Exception,e:
            print_exc()
            print >> sys.stderr, "coordinator: Exception while requesting piece",piece,e
        

    def olthread_send_request_pieces(self, permid, piece):
        """ Creates a bridge connection for the piece request message to be sent
        
        Called by the overlay thread.
        
        @param permid: The permid of the peer that will be contacted
        @param piece: The piece that will be requested
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: olthread_send_request_pieces connecting to", show_permid_short(permid), "to request piece", piece
        # Connect to the peer designated by permid
        olthread_reserve_pieces_connect_callback_lambda = lambda e,d,p,s:self.olthread_request_pieces_connect_callback(e,d,p,s,piece)
        self.overlay_bridge.connect(permid, olthread_reserve_pieces_connect_callback_lambda)


    def olthread_request_pieces_connect_callback(self, exc, dns, permid, selversion, piece):
        """ Sends the join_helpers message on the connection with the coordinator
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the helper that is requested a piece
        @param peice: the requested piece 
        @param selversion:
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_request_pieces_connect_callback sending help request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = REQUEST_PIECES + self.infohash + bencode(piece)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_request_pieces_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_request_pieces_connect_callback: error connecting to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    def olthread_request_pieces_send_callback(self,exc,permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for helping
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_request_pieces_send_callback: error sending to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    def choose_helper(self, peerid):
        """ The method returns one of the confirmed helpers, to be contacted for help for a specific piece
        
        Called by send_request_pieces
        @param peerid: The peerid of the helper that will be requested to download a piece
        @return: the permid of that peer
        """

        chosen_helper = None
        helper_challenge = decode_challenge_from_peerid(peerid)
        if helper_challenge in self.sent_challenges_by_challenge.keys():
            # I found the proxy permid in a connection opened by the proxy 
            chosen_helper = self.sent_challenges_by_challenge[helper_challenge]
        else:
            # I search the proxy permid in a connection opened by the doe
            for single_dl in self.downloader.downloads:
                remote_peer_id = single_dl.connection.get_id()
                if remote_peer_id == peerid:
                    # I found the connection with the proxy
                    chosen_helper = single_dl.connection.connection.get_proxy_permid()
        
        # Current proxy selection policy: choose a random helper from the confirmed helper list
#        chosen_helper = random.choice(self.confirmed_helpers)
        
        return chosen_helper





    def send_cancel_piece(self, piece):
        """ Send a cancel message for the specified piece
        
        Called by TODO
        
        @param piece: The piece that will be canceled to the respective helper
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: i will cancel the request for piece", piece
            
        try:
            # Check if the piece was reserved before
            all_requested_pieces = self.requested_pieces.values()
            if piece not in all_requested_pieces:
                if DEBUG:
                    print >> sys.stderr, "coordinator: piece", piece, "was not requested to any peer"
                return
            
            # Find the peer that was requested to download the piece
            for helper in self.requested_pieces.keys():
                his_pieces = self.requested_pieces[helper]
                if piece in his_pieces:
                    if DEBUG:
                        print >> sys.stderr, "coordinator: canceling piece", piece, "to peer", show_permid_short(helper)
                    # Sent the cancel message to the helper
                    olthread_send_cancel_piece_lambda = lambda:self.olthread_send_cancel_piece(chosen_permid, piece)
                    self.overlay_bridge.add_task(olthread_send_cancel_piece_lambda,0)
        except Exception,e:
            print_exc()
            print >> sys.stderr, "coordinator: Exception while requesting piece",piece,e
        

    def olthread_send_cancel_piece(self, permid, piece):
        """ Creates a bridge connection for the piece cancel message to be sent
        
        Called by the overlay thread.
        
        @param permid: The permid of the peer that will be contacted
        @param piece: The piece that will be canceled
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: olthread_send_cancel_piece connecting to", show_permid_short(permid), "to cancel piece", piece
        # Connect to the peer designated by permid
        self.overlay_bridge.connect(permid, piece, self.olthread_cancel_piece_connect_callback)


    def olthread_cancel_piece_connect_callback(self, exc, dns, permid, piece, selversion):
        """ Sends the cancel piece message on the connection with the peer
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param dns:
        @param permid: the permid of the helper that is requested a piece
        @param peice: the canceled piece 
        @param selversion:
        """
        if exc is None:
            # Peer is reachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_cancel_piece_connect_callback sending a cancel request to", show_permid_short(permid), "for piece", piece
            
            # Create message according to protocol version
            message = CANCEL_PIECE + self.infohash + bencode(piece)
            
            # Connect using Tribler Ovrlay Swarm
            self.overlay_bridge.send(permid, message, self.olthread_cancel_piece_send_callback)
        else:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_cancel_piece_connect_callback: error connecting to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    def olthread_cancel_piece_send_callback(self,exc,permid):
        """ Callback function for error checking in network communication
        
        Called by the overlay thread.
        
        @param exc: Peer reachable/unreachable information. None = peer reachable
        @param permid: the permid of the peer that is contacted for helping
        """
        if exc is not None:
            # Peer is unreachable
            if DEBUG:
                print >> sys.stderr, "coordinator: olthread_cancel_piece_send_callback: error sending to",show_permid_short(permid),exc
            # Remove peer from the list of asked peers
            self.remove_unreachable_helper(permid)


    
    
    
    #
    # Got (received) messages
    # 
    def got_join_helpers(self, permid, selversion):
        """ Mark the peer as an active helper
        
        @param permid: The permid of the node sending the message
        @param selversion:
        @param challenge: The challenge sent by the proxy
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: received a JOIN_HELPERS message from", show_permid_short(permid)

        #Search the peer in the asked_helpers list, remove it from there, and put it in the confirmed_helpers list.
        self.asked_helpers_lock.acquire()
        try:
            # Search the peers with permid != from the given permid
            new_asked_helpers = []
            for peer in self.asked_helpers:
                if peer['permid'] != permid:
                    new_asked_helpers.append(peer)
                else:
                    # Keep a reference to the peer, to add it to the confirmed_helpers list
                    #
                    # If there are more than one peer with the same peerid in the asked_helpers list
                    # than only add the last one to the confirmed_helpers list. 
                    confirmed_helper = peer
            self.asked_helpers = new_asked_helpers
        finally:
            self.asked_helpers_lock.release()
        
        self.confirmed_helpers_lock.acquire()
        self.confirmed_helpers.append(confirmed_helper)
        self.confirmed_helpers_lock.release()
        
        # Start a data connection to the helper
        self.start_data_connection(permid)




    def got_resign_as_helper(self,permid,selversion):
        """ Remove the peer from the list of active helpers (and form the list of asked helpers)
        
        @param permid: The permid of the node sending the message
        @param selversion:
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: received a RESIGN_AS_HELPER message from", show_permid_short(permid)

        #Search the peer in the asked_helpers list and remove it from there
        self.asked_helpers_lock.acquire()
        try:
            # Search the peers with permid != from the given permid
            new_asked_helpers = []
            for peer in self.asked_helpers:
                if peer['permid'] != permid:
                    new_asked_helpers.append(peer)
            self.asked_helpers = new_asked_helpers
        finally:
            self.asked_helpers_lock.release()

        #Search the peer in the confirmed_helpers list and remove it from there
        self.confirmed_helpers_lock.acquire()
        try:
            # Search the peers with permid != from the given permid
            new_confirmed_helpers = []
            for peer in self.confirmed_helpers:
                if peer['permid'] != permid:
                    new_confirmed_helpers.append(peer)
            self.confirmed_helpers = new_confirmed_helpers
        finally:
            self.confirmed_helpers_lock.release()





    def got_dropped_piece(self, permid, piece, selversion):
        """ TODO
        
        @param permid: The permid of the node sending the message
        @param peice: The piece that are dropped
        @param selversion:
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: received a DROPPED_PIECE message from", show_permid_short(permid)

        pass





    def got_proxy_have(self,permid,selversion, aggregated_string):
        """ Take the list of pieces the helper sent and combine it with the numhaves in the piece picker
        
        @param permid: The permid of the node sending the message
        @param selversion:
        @param aggregated_string: a bitstring of available pieces built by the helper based on HAVE messages it received
        """
        if DEBUG:
            print >> sys.stderr, "coordinator: received a PROXY_HAVE message from", show_permid_short(permid)

#        if len(aggregated_string) != self.num_pieces:
#            print >> sys.stderr, "coordinator: got_proxy_have: invalid payload in received PROXY_HAVE message. self.num_pieces=", self.num_pieces, "len(aggregated_string)=", len(aggregated_string)

        # Get the recorded peer challenge
        peer_challenge = self.sent_challenges_by_permid[permid]
        
        # Search for the connection that has this challenge
        if DEBUG:
            debug_found_connection = False
        for single_dl in self.downloader.downloads:
            # Search in the connections opened by the proxy
            peer_id = single_dl.connection.get_id()
            if DEBUG:
                print >> sys.stderr, "peer_challenge=",peer_challenge,"decode_challenge_from_peerid(peer_id)=",decode_challenge_from_peerid(peer_id)
            if peer_challenge == decode_challenge_from_peerid(peer_id):
                # If the connection is found, add the piece_list information to the d.have information
                single_dl.proxy_have = Bitfield(length=self.downloader.numpieces, bitstring=aggregated_string)
                if DEBUG:
                    debug_found_connection = True
                break

            # Search in the connections opened by the doe
            proxy_permid = single_dl.connection.connection.get_proxy_permid()
            if permid == proxy_permid:
                # If the connection is found, add the piece_list information to the d.have information
                single_dl.proxy_have = Bitfield(length=self.downloader.numpieces, bitstring=aggregated_string)
                if DEBUG:
                    debug_found_connection = True
                break

        if DEBUG:
            if debug_found_connection:
                print >> sys.stderr, "coordinator: got_proxy_have: found a data connection for the received PROXY_HAVE"
            else:
                print >> sys.stderr, "coordinator: got_proxy_have: no data connection for the received PROXY_HAVE has been found"



    # Returns a copy of the asked helpers lit
    def network_get_asked_helpers_copy(self):
        """ Returns a COPY of the list. We need 'before' and 'after' info here,
        so the caller is not allowed to update the current confirmed_helpers """
        if DEBUG:
            print >> sys.stderr, "coordinator: network_get_asked_helpers_copy: Number of helpers:",len(self.confirmed_helpers)
        self.confirmed_helpers_lock.acquire()
        try:
            return copy.deepcopy(self.confirmed_helpers)
        finally:
            self.confirmed_helpers_lock.release()

    # Compares peers a and b 
    def samePeer(self,a,b):
        """ Compares peers a and b
        
        @param a: First peer to compare
        @param b: Second peer to compare
        @return: True, if the peers are identical. False, if the peers are different
        """
        if a.has_key('permid'):
            if b.has_key('permid'):
                if a['permid'] == b['permid']:
                    return True
        # TODO: Why, if permid's are different, the function returns True ???
        if a['ip'] == b['ip'] and a['port'] == b['port']:
            return True
        else:
            return False


    # Open data connections
    def start_data_connection(self, helper_permid):
        """ Start a data connection with the helper agreeing to proxy for us
        
        @param helper_permid: The permid of the helper that sent a JOIN_HELPERS message
        """

        if DEBUG:
            print >> sys.stderr,"coordinator: start_data_connection: Going to start data connection to helper at", show_permid_short(helper_permid)
        
        # if start_data_connection is called too early, and the encoder is not set yet, return
        if self.encoder is None:
            if DEBUG:
                print >> sys.stderr,"coordinator: start_data_connection: No encoder found. Exiting."
            return
        
        # Do this always, will return quickly when connection already exists
        for peer in self.confirmed_helpers:
            if peer['permid'] == helper_permid:
                ip = peer['ip']
                port = peer['port']
                dns = (ip, port)
                
                if DEBUG:
                    print >> sys.stderr,"coordinator: start_data_connection: Starting data connection to helper at", dns
                
                self.encoder.start_connection(dns, id = None, proxy_con = True, proxy_permid = helper_permid)
                break

    def set_encoder(self, encoder):
        """ Sets the current encoder.
        
        Called from download_bt1.py
        
        @param encoder: the new encoder that will be set
        """
        self.encoder = encoder


    #
    # Interface for Encrypter.Connection
    #
    # TODO: rename this function
    # TODO: change ip param to permid
    # Returns true if the peer with the IP ip is a helper
    def is_helper_ip(self, ip):
        """ Used by Coordinator's Downloader (via Encrypter) to see what 
        connections are helpers """
        # called by network thread
        self.confirmed_helpers_lock.acquire()
        try:
            for peer in self.confirmed_helpers:
                if peer['ip'] == ip:
                    return True
            return False
        finally:
            self.confirmed_helpers_lock.release()





    #
    # Interface for CoordinatorMessageHandler
    #
    # TOSO: rename this function
    # Return True if the peer is a helper
    # permid = permid of the peer
    def network_is_helper_permid(self, permid):
        """ Used by CoordinatorMessageHandler to check if RESERVE_PIECES is from good source (if the permid is a helper) """
        # called by overlay thread
        for peer in self.confirmed_helpers:
            if peer['permid'] == permid:
                return True
        return False








    # TODO: rename this function
    # Returns the list of reserved pieces
    def network_get_reserved(self):
        return self.reserved





    # Set download object
    def set_downloader(self, downloader):
        """ Method used to set a reference to the downloader object
        
        Called by BT1Download, after it creates the Downloader object
        
        @param downloader: A reference to the downloader object for the current download
        """
        self.downloader = downloader
