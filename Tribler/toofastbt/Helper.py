# Written by Pawel Garbacki
# see LICENSE.txt for license information

import sys
from traceback import print_exc, print_stack
from time import time

from Logger import get_logger
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
from BitTornado.bencode import bencode
from BitTornado.BT1.MessageID import RESERVE_PIECES

MAX_ROUNDS = 200
DEBUG = True

class Helper:
    def __init__(self, torrent_hash, num_pieces, coordinator_permid, coordinator = None):
        self.secure_overlay = SecureOverlay.getInstance()
        self.torrent_hash = torrent_hash
        self.coordinator_permid = coordinator_permid

        peerdb = PeerDBHandler()
        peer = peerdb.getPeer(coordinator_permid)
        if peer is None:
            self.coordinator_ip = None  # see is_coordinator()
            self.coordinator_port = -1
        else:
            self.coordinator_ip = peer['ip']
            self.coordinator_port = peer['port']

        self.reserved_pieces = [False] * num_pieces
        self.ignored_pieces = [False] * num_pieces
        self.coordinator = coordinator
        self.counter = 0
        self.completed = False
        self.distr_reserved_pieces = [False] * num_pieces
        self.marker = [True] * num_pieces
        self.round = 0
        self.encoder = None
        self.continuations = []
        self.outstanding = None
        self.last_req_time = 0

    def set_encoder(self,encoder):
        self.encoder = encoder
        self.encoder.set_coordinator_ip(self.coordinator_ip)
        # To support a helping user stopping and restarting a torrent
        if self.coordinator_permid is not None:
            self.start_data_connection()   

    def test(self):
        result = self.reserve_piece(10)
        print >> sys.stderr,"reserve piece returned: " + str(result)
        print >> sys.stderr,"Test passed"

    def _reserve_piece(self, piece):
        self.reserved_pieces[piece] = True
        self.distr_reserved_pieces[piece] = True
        self.ignored_pieces[piece] = False

    def _ignore_piece(self, piece):
        if not self.is_reserved(piece):
            self.ignored_pieces[piece] = True
            self.distr_reserved_pieces[piece] = True

    def is_coordinator(self,permid):
        # If we could get coordinator_ip, don't help
        if self.coordinator_ip is None:
            return False

        if self.coordinator_permid == permid:
            return True
        else:
            return False

### PiecePicker and Downloader interface
    def is_reserved(self, piece):
        if self.reserved_pieces[piece] or (self.coordinator is not None and self.is_complete()):
            return True
        return self.reserved_pieces[piece]

    def is_ignored(self, piece):
        if not self.ignored_pieces[piece] or (self.coordinator is not None and self.is_complete()):
            return False
        return self.ignored_pieces[piece]

    def is_complete(self):
        if self.completed:
            return True
        self.round = (self.round + 1) % MAX_ROUNDS
        if self.round != 0:
            return False
        if self.coordinator is not None:
            self.completed = (self.coordinator.reserved_pieces == self.marker)
        else:
            self.completed = (self.distr_reserved_pieces == self.marker)
        return self.completed

    def reserve_pieces(self, pieces, sdownload, all_or_nothing = False):
        pieces_to_send = []
        ex = "None"
        result = []
        for piece in pieces:
            if self.is_reserved(piece):
                result.append(piece)
            elif not self.is_ignored(piece):
                pieces_to_send.append(piece)

        #if DEBUG:
        #    print >> sys.stderr,"helper: reserve_pieces: result is",result,"to_send is",pieces_to_send

        if pieces_to_send == []:
            return result
        if self.coordinator is not None:
            new_reserved_pieces = self.coordinator.reserve_pieces(pieces_to_send, all_or_nothing)
            for piece in new_reserved_pieces:
                self._reserve_piece(piece)
        else:
            self.send_or_queue_reservation(sdownload,pieces_to_send,result)
            return []

        result = []
        for piece in pieces:
            if self.is_reserved(piece):
                result.append(piece)
            else:
                self._ignore_piece(piece)
        return result

    def reserve_piece(self, piece, sdownload):
        if self.coordinator is not None and self.is_complete():
            return True
        new_reserved_pieces = self.reserve_pieces([piece],sdownload)
        if new_reserved_pieces == []:
            return False
        else:
            return True


## Synchronization interface

    def send_or_queue_reservation(self,sdownload,pieces_to_send,result):
        """ Records the fact that a SingleDownload wants to reserve a
            piece with the coordinator. If it's the first, send the
            actual reservation request.
        """
        if sdownload not in self.continuations:
            if DEBUG:
                print >> sys.stderr,"helper: Queuing reservation for",pieces_to_send
            self.continuations.append(sdownload)
            sdownload.helper_set_freezing(True)
        if len(self.continuations) > 0:
            self.send_reservation(pieces_to_send)

    def send_reservation(self,pieces_to_send):
        # Arno: I sometimes see no reply to a RESERVE_PIECE and the client
        # stops acquiring new pieces. The last_req_time is supposed
        # to fix this.
        waited = int(time())-self.last_req_time
        if self.outstanding is None or waited > 60:
            self.counter += 1
            self.last_req_time = int(time())
            if DEBUG:
                if self.outstanding is None:
                    print >> sys.stderr,"helper: Sending reservation for",pieces_to_send,"because none"
                else:
                    print >> sys.stderr,"helper: Sending reservation for",pieces_to_send,"because timeout"
            sdownload = self.continuations.pop(0)
            self.outstanding = sdownload            
            ex = "self.send_reserve_pieces(pieces_to_send)"
            self.send_reserve_pieces(pieces_to_send)


    def notify(self):
        """ Called by HelperMessageHandler to "wake up" the download that's
            waiting for its coordinator to reserve it a piece 
        """
        if self.outstanding is None:
            if DEBUG:
                print >> sys.stderr,"helper: notify: No continuation waiting???"
        else:
            if DEBUG:
                print >> sys.stderr,"helper: notify: Waking downloader"
            sdownload = self.outstanding
            self.outstanding = None # must be not before calling self.restart!
            self.restart(sdownload)
            
            #self.send_reservation()
            list = self.continuations[:] # copy just to be sure
            self.continuations = []
            for sdownload in list:
                self.restart(sdownload)

    def restart(self,sdownload):
        # Chokes can get in while we're waiting for reply from coordinator. 
        # But as we were called from _request_more() we were not choked 
        # just before, so pretend we didn't see the message yet.
        if sdownload.is_choked():
            sdownload.helper_forces_unchoke()
        sdownload.helper_set_freezing(False)
        sdownload._request_more()

## Coordinator comm.       
    def send_reserve_pieces(self, pieces, all_or_nothing = False):
        if all_or_nothing:
            all_or_nothing = chr(1)
        else:
            all_or_nothing = chr(0)
        payload = self.torrent_hash + all_or_nothing + bencode(pieces)
        self.secure_overlay.addTask(self.coordinator_permid, RESERVE_PIECES + payload )

### HelperMessageHandler interface
    def got_pieces_reserved(self, permid, pieces):
        self.handle_pieces_reserved(pieces)
        self.start_data_connection()

    def handle_pieces_reserved(self,pieces):
        if DEBUG:
            print >> sys.stderr,"helper: Coordinator replied",pieces
        try:
            for piece in pieces:
                if piece > 0:
                    self._reserve_piece(piece)
                else:
                    self._ignore_piece(-piece)
            self.counter -= 1

        except Exception,e:
            print_exc()
            print >> sys.stderr,"helper: Exception in handle_pieces_reserved",e

    def start_data_connection(self):
        # Do this always, will return quickly when connection already exists
        dns = (self.coordinator_ip, self.coordinator_port)
        if DEBUG:
            print >> sys.stderr,"helper: Starting data connection to coordinator",dns
        self.encoder.start_connection(dns,id = None,coord_con = True)
      