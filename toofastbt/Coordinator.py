# Written by Pawel Garbacki
# see LICENSE.txt for license information

from thread import allocate_lock
from toofastbt.Logger import get_logger

class Coordinator:
        
    def __init__(self, info_hash, num_pieces, helpers_file = None):
        self.reserved_pieces = [False] * num_pieces
        self.info_hash = info_hash
        self.control_connections = []
        self.encoder = None
        # optimization
        self.reserved = []

        self.pending_helpers = []
        # read helpers from file
        if helpers_file is not None:
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
                        self.pending_helpers.append((ip, port))
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

    def request_help(self):
        for (ip, port) in self.pending_helpers:
            self.encoder.overlay_swarm.connect_peer(ip, port)
            self.encoder.overlay_swarm.add_os_task2(ip, port, ['DOWNLOAD_HELP', self.info_hash])
        self.pending_helpers = []

### Connecter interface
    def get_reserved(self):
        return self.reserved

    def reserve_pieces(self, control_con, pieces, all_or_nothing = False):
        if not not self.pending_helpers:
            self.encoder.raw_server.add_task(self.request_help, 1)
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
        