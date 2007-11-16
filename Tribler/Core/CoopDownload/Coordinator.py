# Written by Pawel Garbacki, Arno Bakker
# see LICENSE.txt for license information
#
# TODO: when DOWNLOAD_HELP cannot be sent, mark this in the interface

from traceback import print_exc
import copy
import sys

from Tribler.Core.Overlay.SecureOverlay import SecureOverlay,select_supported_protoversion
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.BitTornado.BT1.MessageID import DOWNLOAD_HELP, STOP_DOWNLOAD_HELP, PIECES_RESERVED

DEBUG = False
MAX_ROUNDS = 137


class Coordinator:
        
    def __init__(self, torrent_hash, num_pieces):
        self.reserved_pieces = [False] * num_pieces
        self.torrent_hash = torrent_hash
        self.asked_helpers = []
        # optimization
        self.reserved = []
        self.secure_overlay = SecureOverlay.getInstance()

    def is_helper_permid(self, permid):
        """ Used by HelperMessageHandler to check if RESERVE_PIECES is from good source """
        for peer in self.asked_helpers:
            if peer['permid'] == permid:
                return True
        return False

    def is_helper_ip(self, ip):
        """ Used by Coordinator's Downloader to see what connections are helpers """
        for peer in self.asked_helpers:
            if peer['ip'] == ip:
                return True
        return False

    def request_help(self,peerList,force = False):
        #print >> sys.stderr,"dlhelp: REQUESTING HELP FROM",peerList
        try:
            toask_helpers = []
            if force:
                toask_helpers = peerList
            else:
                # Who in peerList has not been asked already?
                for cand in peerList:
                    flag = 0
                    for asked in self.asked_helpers:
                        if self.samePeer(cand,asked):
                            flag = 1
                            break
                    if flag == 0:
                        toask_helpers.append(cand)

            self.asked_helpers.extend(toask_helpers)
            self.send_request_help(toask_helpers)
        except Exception,e:
            print_exc()
            print >> sys.stderr,"helpcoord: Exception while requesting help",e

    def send_request_help(self,peerList):
        for peer in peerList:
            peer['round'] = 0
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator connecting to",peer['name'],show_permid_short(peer['permid'])," for help"
            self.secure_overlay.connect(peer['permid'],self.request_help_connect_callback)

    def request_help_connect_callback(self,exc,dns,permid,selversion):
        if exc is None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator sending to",show_permid_short(permid)
            ## Create message according to protocol version
            dlhelp_request = self.torrent_hash
            self.secure_overlay.send(permid, DOWNLOAD_HELP + dlhelp_request,self.request_help_send_callback)
        else:
            if DEBUG:
                print >> sys.stderr,"dlhelp: DOWNLOAD_HELP: error connecting to",show_permid_short(permid),exc
            self.remove_unreachable_helper(permid)

    def remove_unreachable_helper(self,permid):
        # Remove peer that we could not connect to from asked helpers
        newlist = []
        for peer in self.asked_helpers:
            if peer['permid'] != permid:
                newlist.append(peer)
        self.asked_helpers = newlist

    def request_help_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: DOWNLOAD_HELP: error sending to",show_permid_short(permid),exc
            self.remove_unreachable_helper(permid)

    def stop_help(self,peerList, force = False):
        # print >> sys.stderr,"dlhelp: STOPPING HELP FROM",peerList
        if force:
            tostop_helpers = peerList
        else:
            # Who in the peerList is actually a helper currently?
            tostop_helpers = []
            for cand in peerList:
                for asked in self.asked_helpers:
                    if self.samePeer(cand,asked):
                        tostop_helpers.append(cand)
                        break

        # Who of the actual helpers gets to stay?
        tokeep_helpers = []
        for asked in self.asked_helpers:
            flag = 0
            for cand in tostop_helpers:
                if self.samePeer(cand,asked):
                    flag = 1
                    break
            if flag == 0:
                tokeep_helpers.append(asked)

        self.send_stop_help(tostop_helpers)
        self.asked_helpers = tokeep_helpers

    def stop_all_help(self):
        self.send_stop_help(self.asked_helpers)
        self.asked_helpers = []

    def send_stop_help(self,peerList):
        for peer in peerList:
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator connecting to",peer['name'],show_permid_short(peer['permid'])," for stopping help"
            self.secure_overlay.connect(peer['permid'],self.stop_help_connect_callback)

    def stop_help_connect_callback(self,exc,dns,permid,selversion):
        if exc is None:
            ## Create message according to protocol version
            stop_request = self.torrent_hash
            self.secure_overlay.send(permid,STOP_DOWNLOAD_HELP + stop_request,self.stop_help_send_callback)
        elif DEBUG:
            print >> sys.stderr,"dlhelp: STOP_DOWNLOAD_HELP: error connecting to",show_permid_short(permid),exc

    def stop_help_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: STOP_DOWNLOAD_HELP: error sending to",show_permid_short(permid),exc
            pass


    def get_asked_helpers_copy(self):
        # returns a COPY of the list. We need 'before' and 'after' info here,
        # so the caller is not allowed to update the current asked_helpers
        if DEBUG:
            print >> sys.stderr,"dlhelp: Coordinator: Asked helpers is #",len(self.asked_helpers)
        return copy.deepcopy(self.asked_helpers)

    def samePeer(self,a,b):
        if a.has_key('permid'):
            if b.has_key('permid'):
                if a['permid'] == b['permid']:
                    return True
        if a['ip'] == b['ip'] and a['port'] == b['port']:
            return True
        else:
            return False


### CoordinatorMessageHandler interface
    def got_reserve_pieces(self,permid,pieces,all_or_nothing,selversion):

        reserved_pieces = self.reserve_pieces(pieces, all_or_nothing)
        for peer in self.asked_helpers:
            if peer['permid'] == permid:
                peer['round'] = (peer['round'] + 1) % MAX_ROUNDS
                if peer['round'] == 0:
                    reserved_pieces.extend(self.get_reserved())
        self.send_pieces_reserved(permid,reserved_pieces,selversion)

    def reserve_pieces(self, pieces, all_or_nothing = False):
        try:
            new_reserved = []
            for piece in pieces:
                if not self.reserved_pieces[piece]:
                    new_reserved.append(piece)
                    if not all_or_nothing:
                        self.reserved_pieces[piece] = True
                        self.reserved.append(-piece)
                elif all_or_nothing: # there is no point of continuing
                    new_reserved = []
                    break
            if all_or_nothing:
                for piece in new_reserved:
                    self.reserved_pieces[piece] = True
                    self.reserved.append(-piece)
        except Exception, e:
            print_exc()
            print >> sys.stderr,"helpcoord: Exception in reserve_pieces",e
        return new_reserved

    def get_reserved(self):
        return self.reserved

    def send_pieces_reserved(self, permid, pieces, selversion):
        ## Create message according to protocol version
        payload = self.torrent_hash + bencode(pieces)
        # Optimization: we know we're connected
        self.secure_overlay.send(permid, PIECES_RESERVED + payload,self.pieces_reserved_send_callback)
    
    def pieces_reserved_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: PIECES_RESERVED: error sending to",show_permid_short(permid),exc
            pass
