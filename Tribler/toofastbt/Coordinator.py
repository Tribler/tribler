# Written by Pawel Garbacki
# see LICENSE.txt for license information

from Tribler.toofastbt.Logger import get_logger
from Tribler.Overlay.SecureOverlay import SecureOverlay
from BitTornado.bencode import bencode
from BitTornado.BT1.MessageID import DOWNLOAD_HELP

from traceback import print_exc
import copy

class Coordinator:
        
    def __init__(self, info_hash, num_pieces, helpers_file = None):
        self.reserved_pieces = [False] * num_pieces
        self.info_hash = info_hash
        self.control_connections = []
        self.asked_helpers = []
        self.pending_helpers = []        
        # optimization
        self.reserved = []
        self.secure_overlay = SecureOverlay.getInstance()

        # read helpers from file
        if helpers_file is not None:

            print "Reading helpers from file currently not supported"

            f = open(helpers_file, 'r')
            while 1:
                lines = f.readlines(100000)
                if not lines:
                    break
                for line in lines:
                    line = line.strip()
                    #-- exclude comment and empty lines
                    if (len(line) > 0) and (line[0] != '#'):
                        [ip, port] = line.split()
                        port = int(port)
                        # Add a peer comparable to those from cachedb2.py
                        peer = {}
                        peer['name'] = 'John Doe'
                        peer['permid'] = None
                        peer['ip'] = ip
                        peer['port'] = port
                        self.pending_helpers.append(peer)
            f.close()

    def is_helper(self, peer_id):
        for con in self.control_connections:
            if con.get_id() == peer_id:
                return True
        return False

    def add_helper(self, control_con):
        assert not self.is_helper(control_con.get_id())
        get_logger().log(3, "coordinator.coordinator: helper id: '" + 
            str(control_con.get_id()) + "'")
        self.control_connections.append(control_con)

    def set_encoder(self, encoder):
        self.encoder = encoder

    def request_pending_callback(self):
        self.do_request_help(self.pending_helpers)
        self.pending_helpers = []

    def request_help(self,peerList,force = False):
        #print "dlhelp: REQUESTING HELP FROM",peerList
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
            self.do_request_help(toask_helpers)
        except Exception,e:
            print_exc()
            print "dlhelp: Exception while requesting help",e

    def do_request_help(self,peerList):
        for peer in peerList:
            self.asked_helpers.append(peer)
            print "dlhelp: Coordinator connecting to",peer['name'],peer['ip'],peer['port']," for help"
            dlhelp_request = self.info_hash
            self.secure_overlay.addTask(peer['permid'], DOWNLOAD_HELP + dlhelp_request)

    def stop_help(self,peerList, force = False):
        # print "dlhelp: STOPPING HELP FROM",peerList
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

        self.do_stop_help(tostop_helpers)
        self.asked_helpers = tokeep_helpers

    def stop_all_help(self):
        self.do_stop_help(self.asked_helpers)
        self.asked_helpers = []

    def do_stop_help(self,peerList):
        for peer in peerList:
            print "dlhelp: Coordinator connecting to",peer['name'],peer['ip'],peer['port']," for stopping help"
            stop_request = torrent_hash
            #self.secure_overlay.addTask(peer['permid'],(STOP_DOWNLOAD_HELP + stop_request)

    def get_asked_helpers_copy(self):
        # returns a COPY of the list. We need 'before' and 'after' info here,
        # so the caller is not allowed to update the current asked_helpers
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

### Connecter interface
    def get_reserved(self):
        return self.reserved

    def reserve_pieces(self, control_con, pieces, all_or_nothing = False):
        if not not self.pending_helpers:
            self.encoder.raw_server.add_task(self.request_pending_callback, 1)
#        if not control_connections.has_key(peer_id):
#            control_connections[peer_id] = connection
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
            print "EXCEPTION!"
            get_logger().log(3, "EXCEPTION: '" + str(e) + "'")
        return new_reserved
        