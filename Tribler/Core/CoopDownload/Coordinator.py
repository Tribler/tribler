# Written by Pawel Garbacki, Arno Bakker
# see LICENSE.txt for license information
#
# TODO: when DOWNLOAD_HELP cannot be sent, mark this in the interface

from traceback import print_exc
import copy
import sys
from threading import Lock

from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.BitTornado.BT1.MessageID import DOWNLOAD_HELP, STOP_DOWNLOAD_HELP, PIECES_RESERVED

DEBUG = False
MAX_ROUNDS = 137


class Coordinator:
        
    def __init__(self, infohash, num_pieces):
        self.reserved_pieces = [False] * num_pieces
        self.infohash = infohash # readonly so no locking on this
        
        self.lock = Lock()
        self.asked_helpers = [] # protected by lock
        # optimization
        self.reserved = []
        self.overlay_bridge = OverlayThreadingBridge.getInstance()

    #
    # Interface for Core API. 
    # 
    def network_request_help(self,peerList,force = False):
        #print >> sys.stderr,"dlhelp: REQUESTING HELP FROM",peerList
        self.lock.acquire()
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

            permidlist = []
            for peer in toask_helpers:
                peer['round'] = 0
                permidlist.append(peer['permid'])
            self.asked_helpers.extend(toask_helpers)
            self.network_send_request_help(permidlist)
        except Exception,e:
            print_exc()
            print >> sys.stderr,"helpcoord: Exception while requesting help",e
        self.lock.release()            

    def network_send_request_help(self,permidlist):
        olthread_send_request_help_lambda = lambda:self.olthread_send_request_help(permidlist)
        self.overlay_bridge.add_task(olthread_send_request_help_lambda,0)
        
    def olthread_send_request_help(self,permidlist):
        for permid in permidlist:
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator connecting to",show_permid_short(permid),"for help"
            self.overlay_bridge.connect(permid,self.olthread_request_help_connect_callback)

    def olthread_request_help_connect_callback(self,exc,dns,permid,selversion):
        if exc is None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator sending to",show_permid_short(permid)
            ## Create message according to protocol version
            dlhelp_request = self.infohash 
            self.overlay_bridge.send(permid, DOWNLOAD_HELP + dlhelp_request,self.olthread_request_help_send_callback)
        else:
            if DEBUG:
                print >> sys.stderr,"dlhelp: DOWNLOAD_HELP: error connecting to",show_permid_short(permid),exc
            self.olthread_remove_unreachable_helper(permid)

    def olthread_request_help_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: DOWNLOAD_HELP: error sending to",show_permid_short(permid),exc
            self.olthread_remove_unreachable_helper(permid)


    def olthread_remove_unreachable_helper(self,permid):
        # Remove peer that we could not connect to from asked helpers
        self.lock.acquire()
        try:
            newlist = []
            for peer in self.asked_helpers:
                if peer['permid'] != permid:
                    newlist.append(peer)
            self.asked_helpers = newlist
        finally:
            self.lock.release()


    def network_stop_help(self,peerList, force = False):
        # print >> sys.stderr,"dlhelp: STOPPING HELP FROM",peerList
        self.lock.acquire()
        try:
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

            permidlist = []
            for peer in tostop_helpers:
                permidlist.append(peer['permid'])
    
            self.network_send_stop_help(permidlist)
            self.asked_helpers = tokeep_helpers
        finally:
            self.lock.release()

    #def stop_all_help(self):
    #    self.send_stop_help(self.asked_helpers)
    #    self.asked_helpers = []

    def network_send_stop_help(self,permidlist):
        olthread_send_stop_help_lambda = lambda:self.olthread_send_stop_help(permidlist)
        self.overlay_bridge.add_task(olthread_send_stop_help_lambda,0)
        
    def olthread_send_stop_help(self,permidlist):
        for permid in permidlist:
            if DEBUG:
                print >> sys.stderr,"dlhelp: Coordinator connecting to",show_permid_short(permid),"for stopping help"
            self.overlay_bridge.connect(permid,self.olthread_stop_help_connect_callback)

    def olthread_stop_help_connect_callback(self,exc,dns,permid,selversion):
        if exc is None:
            ## Create message according to protocol version
            stop_request = self.infohash
            self.overlay_bridge.send(permid,STOP_DOWNLOAD_HELP + stop_request,self.olthread_stop_help_send_callback)
        elif DEBUG:
            print >> sys.stderr,"dlhelp: STOP_DOWNLOAD_HELP: error connecting to",show_permid_short(permid),exc

    def olthread_stop_help_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: STOP_DOWNLOAD_HELP: error sending to",show_permid_short(permid),exc
            pass


    def network_get_asked_helpers_copy(self):
        """ Returns a COPY of the list. We need 'before' and 'after' info here,
        so the caller is not allowed to update the current asked_helpers """
        if DEBUG:
            print >> sys.stderr,"dlhelp: Coordinator: Asked helpers is #",len(self.asked_helpers)
        self.lock.acquire()
        try:
            return copy.deepcopy(self.asked_helpers)
        finally:
            self.lock.release()


    def samePeer(self,a,b):
        if a.has_key('permid'):
            if b.has_key('permid'):
                if a['permid'] == b['permid']:
                    return True
        if a['ip'] == b['ip'] and a['port'] == b['port']:
            return True
        else:
            return False


    #
    # Interface for CoordinatorMessageHandler
    #
    def network_is_helper_permid(self, permid):
        """ Used by CoordinatorMessageHandler to check if RESERVE_PIECES is from good source """
        # called by overlay thread
        for peer in self.asked_helpers:
            if peer['permid'] == permid:
                return True
        return False
    
    def network_got_reserve_pieces(self,permid,pieces,all_or_nothing,selversion):
        self.lock.acquire()
        try:
            reserved_pieces = self.network_reserve_pieces(pieces, all_or_nothing)
            for peer in self.asked_helpers:
                if peer['permid'] == permid:
                    peer['round'] = (peer['round'] + 1) % MAX_ROUNDS
                    if peer['round'] == 0:
                        reserved_pieces.extend(self.network_get_reserved())
            self.network_send_pieces_reserved(permid,reserved_pieces,selversion)
        finally:
            self.lock.release()

    def network_reserve_pieces(self, pieces, all_or_nothing = False):
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

    def network_get_reserved(self):
        return self.reserved

    def network_send_pieces_reserved(self, permid, pieces, selversion):
        olthread_send_pieces_reserved_lambda = lambda:self.olthread_send_pieces_reserved(permid,pieces,selversion)
        self.overlay_bridge.add_task(olthread_send_pieces_reserved_lambda,0)
        
    def olthread_send_pieces_reserved(self, permid, pieces, selversion):
        ## Create message according to protocol version
        payload = self.infohash + bencode(pieces)
        # Optimization: we know we're connected
        self.overlay_bridge.send(permid, PIECES_RESERVED + payload,self.olthread_pieces_reserved_send_callback)
    
    def olthread_pieces_reserved_send_callback(self,exc,permid):
        if exc is not None:
            if DEBUG:
                print >> sys.stderr,"dlhelp: PIECES_RESERVED: error sending to",show_permid_short(permid),exc
            pass
        else:
            if DEBUG:
                print >> sys.stderr,"dlhelp: PIECES_RESERVED: Successfully sent to",show_permid_short(permid)
            pass


    #
    # Interface for Encrypter.Connection
    #
    def is_helper_ip(self, ip):
        """ Used by Coordinator's Downloader (via Encrypter) to see what 
        connections are helpers """
        # called by network thread
        self.lock.acquire()
        try:
            for peer in self.asked_helpers:
                if peer['ip'] == ip:
                    return True
            return False
        finally:
            self.lock.release()
            