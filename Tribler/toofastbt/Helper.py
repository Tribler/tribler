# Written by Pawel Garbacki
# see LICENSE.txt for license information

from sys import exc_info, exit
from traceback import print_exc

from Logger import get_logger
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
from Tribler.toofastbt.WaitForReplyException import WaitForReplyException
from Tribler.toofastbt.intencode import toint, tobinary
from BitTornado.bencode import bencode
from BitTornado.BT1.MessageID import RESERVE_PIECES

MAX_ROUNDS = 200
DEBUG = False

class Helper:
    def __init__(self, torrent_hash, num_pieces, coordinator_permid, coordinator = None):
        print "CREATING HELPER FOR COORDINATOR",`coordinator_permid`
        self.secure_overlay = SecureOverlay.getInstance()
        self.torrent_hash = torrent_hash
        self.coordinator_permid = coordinator_permid

        peerdb = PeerDBHandler()
        peer = peerdb.getPeer(coordinator_permid)
        if peer is None:
            self.coordinator_ip = None  # see is_coordinator()
        else:
            self.coordinator_ip = peer['ip']

        self.reserved_pieces = [False] * num_pieces
        self.ignored_pieces = [False] * num_pieces
        self.coordinator = coordinator
        self.counter = 0
        self.completed = False
        self.distr_reserved_pieces = [False] * num_pieces
        self.marker = [True] * num_pieces
        self.round = 0
        self.encoder = None
        self.requestid = 0
        self.continuations = {}

    def set_encoder(self,encoder):
        self.encoder = encoder
        self.encoder.set_coordinator_ip(self.coordinator_ip)
    
    def test(self):
        result = self.reserve_piece(10)
        print "reserve piece returned: " + str(result)
        print "Test passed"

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
        print "helper: reserve_pieces: Want to reserve",pieces
        pieces_to_send = []
        ex = "None"
        result = []
        for piece in pieces:
            if self.is_reserved(piece):
                result.append(piece)
            elif not self.is_ignored(piece):
                pieces_to_send.append(piece)

        print "helper: reserve_pieces: result is",result,"to_send is",pieces_to_send

        if pieces_to_send == []:
            return result
        if self.coordinator is not None:
            new_reserved_pieces = self.coordinator.reserve_pieces(pieces_to_send, all_or_nothing)
            for piece in new_reserved_pieces:
                self._reserve_piece(piece)
        else:
            self.counter += 1
            ex = "self.send_reserve_pieces(pieces_to_send)"
            self.requestid += 1
            if self.requestid == (2 ** 32)-1:
                self.requestid = 1
            self.send_reserve_pieces(self.requestid,pieces_to_send)
            # Can't do much until reservation received
            self.wait(self.requestid,sdownload)
            
            print "helper: result has length",len(result)
            if len(result) != 0:
                raise WaitForReplyException

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

    def wait(self,reqid,sdownload):
        self.continuations[reqid] = sdownload

    def notify(self,reqid):
        if self.continuations.has_key(reqid):
            print "helper: notify: Waking downloader for reqid",reqid
            sdownload = self.continuations[reqid]
            del self.continuations[reqid]
            sdownload._request_more()
        else:
            print "helper: notify: no downloader for reqid",reqid

## Coordinator comm.       
    def send_reserve_pieces(self, reqid, pieces, all_or_nothing = False):
        if all_or_nothing:
            all_or_nothing = chr(1)
        else:
            all_or_nothing = chr(0)
        payload = self.torrent_hash + tobinary(reqid) + all_or_nothing + bencode(pieces)
        self.secure_overlay.addTask(self.coordinator_permid, RESERVE_PIECES + payload )

### HelperMessageHandler interface
    def got_pieces_reserved(self, permid, pieces):
        self.handle_pieces_reserved(pieces)
        # Do this always, will return quickly when connection already exists
        dns = self.secure_overlay.findDNSByPermid(permid)
        if dns:
            print "helpmsg: Starting data connection to coordinator",dns
            self.encoder.start_connection(dns,id = None,coord_con = True)

    def handle_pieces_reserved(self,pieces):
        print "helper: COORDINATOR REPLIED",pieces
        try:
            for piece in pieces:
                if piece > 0:
                    print "helper: COORDINATOR LET US RESERVE",piece
                    self._reserve_piece(piece)
                else:
                    print "helper: COORDINATOR SAYS IGNORE",-piece
                    self._ignore_piece(-piece)
            self.counter -= 1

        except Exception,e:
            print_exc()
            print "helper: Exception in handle_pieces_reserved",e

      