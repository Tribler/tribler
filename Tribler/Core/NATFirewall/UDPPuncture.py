# Written by Gertjan Halkes
# see LICENSE.txt for license information
#
# NATSwarm implementation for testing NAT/firewall puncturing
# This module creates UDP "connections" and tries to connect to other
# peers in the NATSwarm. PEX is used to find more peers.

import guessip
import time
import socket
import sys
import errno
import random
from collections import deque
import TimeoutFinder

DEBUG = False

#NOTE: the current implementation allows PEX_ADD and PEX_DEL messages to name
#  the same peer. Although these events will be rare, we may want to do something
#  about it.


# Packet format definitions:
# Each packet starts with a single byte packet type. After this, the contents
# is type dependent:
# Connect: 1 byte version number, 4 byte ID, 1 byte NAT/fw state,
#    1 byte NAT/fw state version.
# Your IP: 4 bytes IPv4 address, 2 bytes port number.
# Forward connection request: 4 bytes ID.
# Reverse connect: 4 bytes ID, 4 bytes IPv4 address, 2 bytes port number,
#    1 byte NAT/fw state, 1 byte NAT/fw state version.
#  NAT/fw state may not yet be known through PEX, but we need it for future PEX.
#  Furthermore, we may not learn it through the remote peer's connect, as that may
#  not reach us due to filtering.
# PEX add: 1 byte number of addresses. Per address:
#    4 bytes ID, 4 bytes IPv4 address, 2 bytes port, 1 byte NAT/fw state,
#    1 byte NAT/fw state version.
# PEX del: 1 byte number of addresses. Per address:
#     4 bytes ID.
# Close: 1 byte reason
# Update NAT/fw state: 1 byte NAT/fw state, 1 byte NAT/fw state version.
# Peer unknown: 4 bytes ID.
#
# NAT/fw state is encoded as follows: the least significant 2 bits (0 and 1)
# encode the NAT state: 0 UNKNOWN, 1 NONE, 2 A(P)DM. Bits 2 and 3 encode
# the filtering state: 0 UNKNOWN, 1 EIF/NONE, 2 A(P)DF

# Packet sequence for connection setup through rendez-vous:
# A -> B  CONNECT (in all likelyhood dropped at NAT/fw)
# A -> R  FW_CONNECT_REQ
# R -> B  REV_CONNECT
# B -> A  CONNECT
# A -> B  YOUR_IP
# B -> A  YOUR_IP
#
# NOTE: it is important that three packets are exchanged on the connection,
# because some NAT/firewalls (most notably linux based ones) use an increased
# timeout if they detect that the 'connection' is more than a simple
# transaction.

# Information to keep for each peer:
# - IP/port/NATfw state
# - List of peers through which we heard of this peer
# - Whether a connection attempt was already made
# - To which other peers we have advertised this peer, and the FW state we
#   advertised so updates can be sent

# WARNING: copied from SocketHandler. An import would be better, to keep this
# definition in one place
if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE=10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE=errno.EWOULDBLOCK


class UDPHandler:
    TRACKER_ADDRESS = "m23trial-udp.tribler.org"
    #~ TRACKER_ADDRESS = "localhost"

    # Define message types
    CONNECT = chr(0)  # Connection request, directly sent to target
    YOUR_IP = chr(1)  # Information regarding remote ip as seen by local peer
    FW_CONNECT_REQ = chr(2)  # Request to forward a reverse connection request
    REV_CONNECT = chr(3)  # Reverse connection request, for NAT/firewall state setup
    PEX_ADD = chr(4)  # Notify peer of other known peers
    PEX_DEL = chr(5)  # Notify peer of peers that are no longer available
    CLOSE = chr(6)  # Close connection
    UPDATE_NATFW_STATE = chr(7)  # Notify peer of changed NAT state
    PEER_UNKNOWN = chr(8)  # Response to FW_CONNECT_REQ if the requested peer is unknown
    KEEP_ALIVE = chr(9)  # Simple keep-alive message

    # Connection reset error codes
    CLOSE_NORMAL = chr(0)
    CLOSE_TOO_MANY = chr(1)
    CLOSE_LEN = chr(2)
    CLOSE_PROTO_VER, = chr(3)
    CLOSE_GARBAGE = chr(4)
    CLOSE_NOT_CONNECTED = chr(5)
    CLOSE_STATE_CORRUPT = chr(6)

    # Enumerate NAT states
    # Note that the difference EIM and NONE is irrelevant for our purposes,
    # as both are connectable if combined with EIF
    NAT_UNKNOWN, NAT_NONE, NAT_APDM = range(0, 3)
    # There is a distinction between EIF and no filtering, because the latter
    # does not require keep-alives. However, we need keep-alives anyway for
    # the connections so the distinction is irrelevant.
    FILTER_UNKNOWN, FILTER_NONE, FILTER_APDF = range(0, 3)

    # Number of connections to be made before a decision is made about NAT/fw state
    RECV_CONNECT_THRESHOLD = 4
    # Number of connections before scaling the numbers (prevent overflow, allow change)
    RECV_CONNECT_SCALE_THRESHOLD = 64
    # Fixed threshold above which the filter state is assumed to be FILTER_NONE. This is to
    # make sure that a few (or rather quite a few) missing packets or TIVs don't screw up a
    # peer's idea of its filtering type.
    FIXED_THRESHOLD = 7

    def __init__(self, rawserver, port = 0):
        self.rawserver = rawserver
        self.socket = rawserver.create_udpsocket(port, "0.0.0.0")
        self.connections = {}
        self.known_peers = {}
        self.nat_type = UDPHandler.NAT_UNKNOWN
        self.filter_type = UDPHandler.FILTER_UNKNOWN
        self.max_connections = 100
        self.connect_threshold = 75
        self.recv_unsolicited = 0
        self.recv_connect_total = 0
        self.recv_address = 0
        self.recv_different_address = 0
        self.sendqueue = deque([])
        self.last_connect = 0
        self.last_info_dump = time.time()
        self.natfw_version = 1
        self.keepalive_intvl = 100
        self.done = False
        self.reporter = None
        self.last_sends = {}

        rawserver.start_listening_udp(self.socket, self)

        # Contact NATSwarm tracker peer after 5 seconds
        if port == 9473:
            self.tracker = True

            # Tracker needs a known ID, so set it to all zero
            self.id = "\0\0\0\0"
            # Tracker should accept many more connections than other nodes
            self.max_connections = 1000
            rawserver.add_task(self.check_for_timeouts, 10)
        else:
            self.tracker = False

            # Create a 4 byte random ID
            self.id = (chr(random.getrandbits(8)) + chr(random.getrandbits(8)) +
                chr(random.getrandbits(8)) + chr(random.getrandbits(8)))
            if DEBUG:
                debug("My ID: %s" % self.id.encode('hex'))
            rawserver.add_task(self.bootstrap, 5)
            TimeoutFinder.TimeoutFinder(rawserver, False, self.timeout_report)
            TimeoutFinder.TimeoutFinder(rawserver, True, self.timeout_report)

            from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
            if not DEBUG:
                self.reporter = get_reporter_instance()

        if self.reporter:
            my_wan_ip = guessip.get_my_wan_ip()
            if sys.platform == 'win32' and my_wan_ip == None:
                try:
                    import os
                    for line in os.popen("netstat -nr").readlines():
                        words = line.split()
                        if words[0] == '0.0.0.0':
                            my_wan_ip = words[3]
                            break
                except:
                    pass
            if my_wan_ip == None:
                my_wan_ip = 'Unknown'
            self.reporter.add_event("UDPPuncture", "ID:%s;IP:%s" % (self.id.encode('hex'), my_wan_ip))

    def shutdown(self):
        self.done = True
        for connection in self.connections.values():
            self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_NORMAL, connection.address)
            self.delete_closed_connection(connection)

    def data_came_in(self, address, data):
        if DEBUG:
            debug("Data came (%d) in from address %s:%d" % (ord(data[0]), address[0], address[1]))
        connection = self.connections.get(address)
        if not connection:
            if data[0] == UDPHandler.CLOSE:
                # Prevent stroms of packets, by not responding to this
                return
            if data[0] != UDPHandler.CONNECT:
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_NOT_CONNECTED, address)
                return
            if len(data) != 8:
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN, address)
                return
            if data[1] != chr(0):
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_PROTO_VER, address)
                return


            if self.check_connection_count():
                if self.reporter:
                    self.reporter.add_event("UDPPuncture", "OCTM:%s,%d,%s" % (address[0], address[1], data[2:6].encode('hex')))
                
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_TOO_MANY, address)
                return

            id = data[2:6]
            connection = self.known_peers.get(id)
            if not connection:
                # Create new connection state and add to table
                connection = UDPConnection(address, id, self)
                self.known_peers[id] = connection
            elif connection.address != address:
                if connection.connection_state == UDPConnection.CONNECT_ESTABLISHED:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_STATE_CORRUPT, address)
                    return

                # ADPM NAT-boxes will have different address, so if we sent a
                # connect already we will have done so to a different address.
                try:
                    del self.connections[connection.address]
                except:
                    pass
                # As we knew this peer under a different address, we have to
                # set the address to the one we actually use.
                connection.address = address

            if not address in self.last_sends:
                self.incoming_connect(address, True) # Update NAT and Filter states
            self.connections[address] = connection

        if not connection.handle_msg(data):
            self.delete_closed_connection(connection)

    def check_connection_count(self):
        # If we still have open slots, we can simply connect
        if len(self.connections) < self.max_connections:
            return False

        if DEBUG:
            debug("  Connection threshold reached, trying to find an old connection")
        # Find oldest connection, and close if it is older than 5 minutes
        oldest = None
        oldest_time = 1e308
        for connection in self.connections.itervalues():
            if (not connection.tracker) and connection.connected_since < oldest_time:
                oldest_time = connection.connected_since
                oldest = connection

        if not oldest:
            return True

        if (not self.tracker) and oldest.connected_since > time.time() - 300:
            if DEBUG:
                debug("  All connections are under 5 minutes old")
            return True

        if DEBUG:
            debug("  Closing connection to %s %s:%d" % (oldest.id.encode('hex'), oldest.address[0], oldest.address[1]))
        oldest.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_NORMAL)
        self.delete_closed_connection(oldest)
        return False

    def incoming_connect(self, address, unsolicited):
        if self.tracker:
            return

        if unsolicited:
            self.recv_unsolicited += 1
        self.recv_connect_total += 1

        if self.recv_connect_total > UDPHandler.RECV_CONNECT_SCALE_THRESHOLD:
            self.recv_connect_total >>= 1
            self.recv_unsolicited >>= 1
        # Check if we have enough data-points to say something sensible about
        # our NAT/fw state.
        if self.recv_connect_total > UDPHandler.RECV_CONNECT_THRESHOLD:
            if DEBUG:
                debug("Setting filter state (recv total %d, recv unsol %d)" %
                    (self.recv_connect_total, self.recv_unsolicited))
            update_filter = False
            if self.recv_unsolicited > self.recv_connect_total / 2 or self.recv_unsolicited > UDPHandler.FIXED_THRESHOLD:
                if self.filter_type != UDPHandler.FILTER_NONE or self.nat_type != UDPHandler.NAT_NONE:
                    update_filter = True
                    self.filter_type = UDPHandler.FILTER_NONE
                    self.nat_type = UDPHandler.NAT_NONE
            elif self.filter_type != UDPHandler.FILTER_APDF:
                update_filter = True
                self.filter_type = UDPHandler.FILTER_APDF

            if update_filter:
                self.natfw_version += 1
                if self.natfw_version > 255:
                    self.natfw_version = 0
                if self.reporter:
                    self.reporter.add_event("UDPPuncture", "UNAT:%d,%d,%d" % (self.nat_type,
                        self.filter_type, self.natfw_version))
                map(lambda x: x.readvertise_nat(), self.connections.itervalues())

    def incoming_ip(self, address):
        if self.tracker:
            return

        self.recv_address += 1
        if self.recv_address == 1:
            self.reported_wan_address = address
            return

        if self.recv_address > UDPHandler.RECV_CONNECT_SCALE_THRESHOLD:
            self.recv_address >>= 1
            self.recv_different_address >>= 1

        if self.reported_wan_address != address:
            self.reported_wan_address = address
            self.recv_different_address += 1

        # Check if we have enough data-points to say something sensible about
        # our NAT/fw state.
        if self.recv_address > UDPHandler.RECV_CONNECT_THRESHOLD:
            if DEBUG:
                debug("Setting nat state (recv addr %d, recv diff %d)" %
                    (self.recv_address, self.recv_different_address))
            update_nat = False
            if self.recv_different_address > self.recv_address / 2:
                if self.nat_type != UDPHandler.NAT_APDM:
                    update_nat = True
                    self.nat_type = UDPHandler.NAT_APDM
                    self.filter_type = UDPHandler.FILTER_APDF
            elif self.nat_type != UDPHandler.NAT_NONE:
                update_nat = True
                self.nat_type = UDPHandler.NAT_NONE

            if update_nat:
                self.natfw_version += 1
                if self.natfw_version > 255:
                    self.natfw_version = 0
                if self.reporter:
                    self.reporter.add_event("UDPPuncture", "UNAT:%d,%d,%d" % (self.nat_type,
                        self.filter_type, self.natfw_version))
                map(lambda x: x.readvertise_nat(), self.connections.itervalues())

    def bootstrap(self):
        if DEBUG:
            debug("Starting bootstrap")
        tracker = UDPConnection((socket.gethostbyname(UDPHandler.TRACKER_ADDRESS), 9473), "\0\0\0\0", self)
        # Make sure this is never removed, by setting an address that we will never receive
        tracker.advertised_by[("0.0.0.0", 0)] = 1e308
        tracker.nat_type = UDPHandler.NAT_NONE
        tracker.filter_type = UDPHandler.FILTER_NONE
        tracker.tracker = True
        self.known_peers[tracker.id] = tracker
        self.check_for_timeouts()

    def sendto(self, data, address):
        if DEBUG:
            debug("Sending data (%d) to address %s:%d" % (ord(data[0]), address[0], address[1]))
        if len(self.sendqueue) > 0:
            self.sendqueue.append((data, address))
            return

        try:
            self.socket.sendto(data, address)
        except socket.error, error:
            if error[0] == SOCKET_BLOCK_ERRORCODE:
                self.sendqueue.append((data, address))
                self.rawserver.add_task(self.process_sendqueue, 0.1)

    def process_sendqueue(self):
        while len(self.sendqueue) > 0:
            data, address = self.sendqueue[0]
            try:
                self.socket.sendto(data, address)
            except socket.error, error:
                if error[0] == SOCKET_BLOCK_ERRORCODE:
                    self.rawserver.add_task(self.process_sendqueue, 0.1)
                    return
            self.sendqueue.popleft()

    def check_nat_compatible(self, peer):
        #~ if self.filter_type == UDPHandler.FILTER_APDF and peer.nat_type == UDPHandler.NAT_APDM:
            #~ return False
        if self.nat_type == UDPHandler.NAT_APDM and peer.filter_type == UDPHandler.FILTER_APDF:
            return False
        return True

    def check_for_timeouts(self):
        if self.done:
            return

        now = time.time()
        
        # Remove info about last sends after 5 minutes
        close_list = []
        for address in self.last_sends.iterkeys():
            if self.last_sends[address] < now - 300:
                close_list.append(address)
        for address in close_list:
            del self.last_sends[address]

        # Close connections older than 10 minutes, if the number of connections is more
        # than the connect threshold. However, only discard upto 1/3 of the connect
        # threshold.
        if (not self.tracker) and len(self.connections) >= self.connect_threshold:
            if DEBUG:
                debug("Closing connections older than 10 minutes")
            close_list = []
            for connection in self.connections.itervalues():
                if (not connection.tracker) and connection.connected_since < now - 600:
                    if DEBUG:
                        debug("  Closing connection to %s %s:%d" % (connection.id.encode('hex'),
                            connection.address[0], connection.address[1]))
                    close_list.append(connection)

            for connection in close_list:
                connection.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_NORMAL)
                self.delete_closed_connection(connection)
                if len(self.connections) < self.connect_threshold / 1.5:
                    break

        # Check to see if we should try to make new connections
        if ((not self.tracker) and len(self.connections) < self.connect_threshold and
                self.last_connect < now - 20):
            unconnected_peers = list(set(self.known_peers.iterkeys()) - set(ConnectionIteratorByID(self.connections)))
            random.shuffle(unconnected_peers)
            while len(unconnected_peers) > 0:
                peer = self.known_peers[unconnected_peers.pop()]
                # Only connect to peers that are not connected (should be all, but just in case)
                if peer.connection_state != UDPConnection.CONNECT_NONE:
                    continue
                if not self.check_nat_compatible(peer):
                    continue
                # Don't connect to peers with who we have communicated in the last five minutes
                if peer.last_comm > now - 300:
                    continue

                if not self.try_connect(peer):
                    continue
                self.last_connect = now
                break

        need_advert_time = now - self.keepalive_intvl
        timeout_time = now - 250
        can_advert_time = now - 30

        close_list = []
        pex_only = 0

        # Find all the connections that have timed out and put them in a separate list
        for connection in self.connections.itervalues():
            if (connection.connection_state == UDPConnection.CONNECT_SENT and
                    connection.last_received < can_advert_time):
                if connection.connection_tries < 0:
                    if DEBUG:
                        debug("Dropping connection with %s:%d (timeout)" %
                            (connection.address[0], connection.address[1]))
                    close_list.append(connection)
                elif not self.try_connect(connection):
                    if DEBUG:
                        debug("Too many retries %s:%d" % (connection.address[0], connection.address[1]))
                    close_list.append(connection)
            elif connection.last_received < timeout_time:
                if DEBUG:
                    debug("Dropping connection with %s:%d (timeout)" %
                        (connection.address[0], connection.address[1]))
                close_list.append(connection)

        # Close all the connections
        for connection in close_list:
            self.delete_closed_connection(connection)

        # Check whether we need to send keep-alives or PEX messages
        for connection in self.connections.itervalues():
            if connection.last_send < need_advert_time:
                # If there is a need for a keep-alive, first check if we also
                # have PEX info or changed NAT/fw state, because we might as
                # well send that instead of an empty keep-alive
                if (connection.advertise_nat or len(connection.pex_add) != 0 or len(connection.pex_del) != 0):
                    connection.send_pex() or connection.sendto(UDPHandler.KEEP_ALIVE)
                else:
                    connection.sendto(UDPHandler.KEEP_ALIVE)
            elif (connection.advertise_nat or (len(connection.pex_add) != 0 or len(connection.pex_del) != 0) and
                    connection.last_advert < can_advert_time and pex_only < 35):
                if connection.send_pex():
                    pex_only += 1

        # Reschedule this task in 10 seconds
        self.rawserver.add_task(self.check_for_timeouts, 10)

        # Debug info
        if DEBUG:
            if self.last_info_dump + 60 < now:
                self.last_info_dump = now
                for connection in self.known_peers.itervalues():
                    msg = "Peer %d %s %s:%d,%d,%d: Advertisers:" % (connection.connection_state,
                        connection.id.encode('hex'), connection.address[0],
                        connection.address[1], connection.nat_type, connection.filter_type)
                    for advertiser in connection.advertised_by.iterkeys():
                        msg += " %s:%d" % (advertiser[0], advertiser[1])
                    debug(msg)

    def try_connect(self, peer):
        # Don't try to connect to peers that we can't arange a rendez-vous for
        # when we think we need it
        if peer.filter_type != UDPHandler.FILTER_NONE and len(peer.advertised_by) == 0:
            return False
        
        if peer.connection_tries > 2:
            return False
        peer.connection_tries += 1

        if DEBUG:
            debug("Found compatible peer at %s:%d attempt %d" % (peer.address[0], peer.address[1], peer.connection_tries))

        # Always send connect, to ensure the other peer's idea of its firewall
        # is maintained correctly
        if self.reporter:
            self.reporter.add_event("UDPPuncture", "OCON%d:%s,%d,%s,%d,%d,%d" % (peer.connection_tries, peer.address[0],
                peer.address[1], peer.id.encode('hex'), peer.nat_type, peer.filter_type, peer.natfw_version))
        peer.sendto(UDPHandler.CONNECT + chr(0) + self.id +
            natfilter_to_byte(self.nat_type, self.filter_type) + chr(self.natfw_version))

        # Request a rendez-vous
        if peer.filter_type != UDPHandler.FILTER_NONE:
            if DEBUG:
                debug("Rendez-vous needed")
            # Pick a random advertising peer for rendez vous
            rendezvous_peers = list(peer.advertised_by.iterkeys())
            random.shuffle(rendezvous_peers)
            rendezvous_addr = rendezvous_peers[0]
            rendezvous = self.connections.get(rendezvous_addr)
            if rendezvous:
                if self.reporter:
                    self.reporter.add_event("UDPPuncture", "OFWC:%s,%d,%s,%s" % (rendezvous.address[0],
                        rendezvous.address[1], rendezvous.id.encode('hex'), peer.id.encode('hex')))
                rendezvous.sendto(UDPHandler.FW_CONNECT_REQ + peer.id)

        peer.connection_state = UDPConnection.CONNECT_SENT
        peer.last_received = time.time()
        self.connections[peer.address] = peer
        return True

    def delete_closed_connection(self, connection):
        del self.connections[connection.address]
        orig_state = connection.connection_state
        connection.connection_state = UDPConnection.CONNECT_NONE
        connection.last_comm = time.time()
        # Save the fact that we have sent something to this address, to ensure that retries won't be
        # counted as proper incomming connects without prior communication
        if connection.last_send > time.time() - 300:
            self.last_sends[connection.address] = connection.last_send
        connection.last_send = 0
        connection.last_received = 0
        connection.last_advert = 0
        if connection.id == "\0\0\0\0":
            connection.nat_type = UDPHandler.NAT_NONE
            connection.filter_type = UDPHandler.FILTER_NONE
            connection.natfw_version = 0
        else:
            connection.nat_type = UDPHandler.NAT_UNKNOWN
            connection.filter_type = UDPHandler.FILTER_UNKNOWN
            connection.natfw_version = 0
        connection.pex_add.clear()
        connection.pex_del.clear()
        connection.connection_tries = -1
        if len(connection.advertised_by) == 0:
            try:
                del self.known_peers[connection.id]
            except:
                pass
        map(lambda x: x.remove_advertiser(connection.address), self.known_peers.itervalues())
        if orig_state == UDPConnection.CONNECT_ESTABLISHED:
            map(lambda x: x.pex_del.append(connection), self.connections.itervalues())

    def timeout_report(self, timeout, initial_ping):
        if DEBUG:
            debug("Timeout reported: %d %d" % (timeout, initial_ping))
        if self.reporter:
            self.reporter.add_event("UDPPuncture", "TOUT:%d,%d" % (timeout, initial_ping))
        if initial_ping:
            # Don't want to set the timeout too low, even if the firewall is acting funny
            if timeout > 45 and timeout - 15 < self.keepalive_intvl:
                self.keepalive_intvl = timeout - 15

class ConnectionIteratorByID:
    def __init__(self, connections):
        self.value_iterator = connections.itervalues()

    def __iter__(self):
        return self

    def next(self):
        value = self.value_iterator.next()
        return value.id

class UDPConnection:
    CONNECT_NONE, CONNECT_SENT, CONNECT_ESTABLISHED = range(0, 3)

    def __init__(self, address, id, handler):
        self.address = address
        self.handler = handler
        self.connection_state = UDPConnection.CONNECT_NONE
        self.nat_type = UDPHandler.NAT_UNKNOWN
        self.filter_type = UDPHandler.FILTER_UNKNOWN
        self.natfw_version = 0
        self.advertised_by = {}
        self.pex_add = deque([])
        self.pex_del = deque([])
        self.last_comm = 0
        self.last_send = 0
        self.last_advert = 0
        self.last_received = 0
        self.connected_since = 0
        self.advertise_nat = False
        self.tracker = False
        self.id = id
        self.connection_tries = -1

    def sendto(self, data):
        self.handler.sendto(data, self.address)
        self.last_send = time.time()

    def handle_msg(self, data):
        self.last_received = time.time()
        if data[0] == UDPHandler.CONNECT:
            if DEBUG:
                debug("  Message %d" % ord(data[0]))
            if len(data) != 8:
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                return False

            if ord(data[1]) != 0:
                # Protocol version mismatch
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_PROTO_VER)
                return False

            if data[2:6] != self.id or self.connection_state == UDPConnection.CONNECT_ESTABLISHED:
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_STATE_CORRUPT)
                return False
                
            if self.handler.reporter:
                self.handler.reporter.add_event("UDPPuncture", "ICON-AC:%s,%d,%s" % (self.address[0],
                    self.address[1], data[2:6].encode('hex')))

            if self.handler.tracker:
                peers = self.handler.connections.values()
                random.shuffle(peers)
                self.pex_add.extend(peers)
            else:
                self.pex_add.extend(self.handler.connections.itervalues())

            self.connected_since = time.time()

            message = UDPHandler.YOUR_IP + address_to_string(self.address)
            message += self.pex_string(self.pex_add, 1024 - len(message), True)
            self.sendto(message)
            self.last_advert = self.connected_since
            self.nat_type, self.filter_type = byte_to_natfilter(data[6])
            self.natfw_version = ord(data[7])

            self.connection_state = UDPConnection.CONNECT_ESTABLISHED
            map(lambda x: x.pex_add.append(self), self.handler.connections.itervalues())
            self.pex_add.pop() # Remove ourselfves from our own pex_add list
            return True

        if self.connection_state == UDPConnection.CONNECT_NONE:
            # Other messages cannot be the first message in the stream. Drop this connection
            return False

        while len(data) > 0:
            if DEBUG:
                debug("  Message %d len %d" % (ord(data[0]), len(data)))
            if data[0] == UDPHandler.YOUR_IP:
                if len(data) < 7:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                my_addres = string_to_address(data[1:7])
                if DEBUG:
                    debug("    My IP: %s:%d" % (my_addres[0], my_addres[1]))
                if self.handler.reporter:
                    self.handler.reporter.add_event("UDPPuncture", "IYIP:%s,%d,%s" % (my_addres[0], my_addres[1], self.id.encode('hex')))

                self.handler.incoming_ip(my_addres)

                if self.connection_state == UDPConnection.CONNECT_SENT:
                    self.pex_add.extend(self.handler.connections.itervalues())

                    message = UDPHandler.YOUR_IP + address_to_string(self.address)
                    message += self.pex_string(self.pex_add, 1024 - len(message), True)
                    self.sendto(message)
                    self.last_advert = time.time()
                    self.connected_since = time.time()

                    self.connection_state = UDPConnection.CONNECT_ESTABLISHED

                    map(lambda x: x.pex_add.append(self), self.handler.connections.itervalues())
                    self.pex_add.pop() # Remove ourselfves from our own pex_add list
                data = data[7:]

            elif data[0] == UDPHandler.FW_CONNECT_REQ:
                if len(data) < 5:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                remote = data[1:5]
                connection = self.handler.known_peers.get(remote)
                if connection:
                    if DEBUG:
                        debug("    Rendez vous requested for peer %s %s:%d" % (
                            remote.encode('hex'), connection.address[0], connection.address[1]))
                    if self.handler.reporter:
                        self.handler.reporter.add_event("UDPPuncture", "IFRQ:%s,%d,%s,%s,%d,%s" % (self.address[0],
                            self.address[1], self.id.encode('hex'), connection.address[0], connection.address[1],
                            remote[1:5].encode('hex')))
                else:
                    if DEBUG:
                        debug("    Rendez vous requested for peer %s (unknown)" % (
                            remote.encode('hex')))
                    if self.handler.reporter:
                        self.handler.reporter.add_event("UDPPuncture", "IFRQ:%s,%d,%s,Unknown,Unknown,%s" % (self.address[0],
                            self.address[1], self.id.encode('hex'), remote[1:5].encode('hex')))

                if connection:
                    #FIXME: should we delay this action by some time to ensure the direct connect arives first?
                    # If we do, we should recheck whether we are connected to the requested peer!
                    connection.sendto(UDPHandler.REV_CONNECT + self.id + address_to_string(self.address) +
                        natfilter_to_byte(self.nat_type, self.filter_type) +
                        chr(self.natfw_version))
                else:
                    self.sendto(UDPHandler.PEER_UNKNOWN + remote)

                data = data[5:]

            elif data[0] == UDPHandler.REV_CONNECT:
                if len(data) < 13:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                remote = string_to_address(data[5:11])
                if self.handler.reporter:
                    self.handler.reporter.add_event("UDPPuncture", "IRRQ:%s,%d,%s,%s,%d,%s" % (self.address[0],
                        self.address[1], self.id.encode('hex'), remote[0], remote[1], data[1:5].encode('hex')))
                connection = self.handler.connections.get(remote)
                if connection:
                    pass
                elif self.handler.check_connection_count():
                    if self.handler.reporter:
                        self.handler.reporter.add_event("UDPPuncture", "OCTM-IRRQ:%s,%d,%s" % (connection.address[0],
                            connection.address[1], connection.id.encode('hex')))
                    self.handler.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_TOO_MANY, remote)
                else:
                    self.handler.incoming_connect(remote, False) # Update NAT and Filter states
                    remote_id = data[1:5]
                    connection = self.handler.known_peers.get(remote_id)
                    if not connection:
                        connection = UDPConnection(remote, remote_id, self.handler)
                        self.handler.known_peers[remote_id] = connection
                    elif connection.address != remote:
                        self.sendto(UDPHandler.PEER_UNKNOWN + remote_id)
                        data = data[13:]
                        continue

                    if compare_natfw_version(ord(data[12]), connection.natfw_version):
                        connection.nat_type, connection.filter_type = byte_to_natfilter(data[11])
                        connection.natfw_version = ord(data[12])

                    self.handler.connections[remote] = connection
                    connection.connection_state = UDPConnection.CONNECT_SENT
                    if self.handler.reporter:
                        self.handler.reporter.add_event("UDPPuncture", "OCON-IRRQ:%s,%d,%s" % (connection.address[0],
                            connection.address[1], connection.id.encode('hex')))
                    connection.sendto(UDPHandler.CONNECT + chr(0) + self.handler.id +
                        natfilter_to_byte(self.handler.nat_type, self.handler.filter_type) +
                        chr(self.natfw_version))
                data = data[13:]

            elif data[0] == UDPHandler.PEX_ADD:
                if len(data) < 2:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                addresses = ord(data[1])
                if len(data) < 2 + 12 * addresses:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                for i in range(0, addresses):
                    id = data[2 + i * 12:2 + i * 12 + 4]
                    address = string_to_address(data[2 + i * 12 + 4:2 + i * 12 + 10])
                    peer = self.handler.known_peers.get(id)
                    if not peer:
                        peer = UDPConnection(address, id, self.handler)
                        peer.natfw_version = ord(data[2 + i * 12 + 11])
                        peer.nat_type, peer.filter_type = byte_to_natfilter(data[2 + i * 12 + 10])
                        self.handler.known_peers[id] = peer
                    #FIXME: should we check the received address here as well?

                    peer.advertised_by[self.address] = time.time()
                    if DEBUG:
                        nat_type, filter_type = byte_to_natfilter(data[2 + i * 12 + 10])
                        debug("    Received peer %s %s:%d NAT/fw:%d,%d" % (id.encode('hex'),
                            address[0], address[1], nat_type, filter_type))
                    if compare_natfw_version(ord(data[2 + i * 12 + 11]), peer.natfw_version):
                        peer.natfw_version = ord(data[2 + i * 12 + 11])
                        peer.nat_type, peer.filter_type = byte_to_natfilter(data[2 + i * 12 + 10])
                        if peer.connection_state == UDPConnection.CONNECT_ESTABLISHED:
                            map(lambda x: x.pex_add.append(peer), self.handler.connections.itervalues())
                            peer.pex_add.pop() # Remove ourselfves from our own pex_add list

                data = data[2 + addresses * 12:]

            elif data[0] == UDPHandler.PEX_DEL:
                if len(data) < 2:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                addresses = ord(data[1])
                if len(data) < 2 + 4 * addresses:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                for i in range(0, addresses):
                    id = data[2 + i * 6:2 + i * 6 + 4]
                    if DEBUG:
                        debug("    Received peer %s" % (id.encode('hex')))
                    peer = self.handler.known_peers.get(id)
                    if not peer or not self.address in peer.advertised_by:
                        continue

                    del peer.advertised_by[self.address]
                    if len(peer.advertised_by) == 0 and peer.connection_state == UDPConnection.CONNECT_NONE:
                        del self.handler.known_peers[id]

                data = data[2 + addresses * 6:]

            elif data[0] == UDPHandler.CLOSE:
                if DEBUG:
                    debug("    Reason %d" % ord(data[1]))
                if len(data) == 2 and data[1] == UDPHandler.CLOSE_TOO_MANY and self.handler.reporter:
                    self.handler.reporter.add_event("UDPPuncture", "ICLO:%s,%d,%s" % (self.address[0],
                        self.address[1], self.id.encode('hex')))
                return False
            elif data[0] == UDPHandler.UPDATE_NATFW_STATE:
                if len(data) < 3:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False
                if compare_natfw_version(ord(data[2]), self.natfw_version):
                    self.natfw_version = ord(data[2])
                    self.nat_type, self.filter_type = byte_to_natfilter(data[1])
                    if DEBUG:
                        debug("    Type: %d, %d" % (self.nat_type, self.filter_type))
                    map(lambda x: x.pex_add.append(self), self.handler.connections.itervalues())
                    self.pex_add.pop() # Remove ourselfves from our own pex_add list
                data = data[3:]

            elif data[0] == UDPHandler.PEER_UNKNOWN:
                # WARNING: there is a big security issue here: we trust the
                # remote peer to send us the address that we sent it. However,
                # if the peer is malicious it may send us another address. This
                # can all be verified, but then we need to keep track of lots
                # more state which I don't want to do for the current
                # implementation.
                if len(data) < 5:
                    self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_LEN)
                    return False

                remote = data[1:5]
                peer = self.handler.known_peers.get(remote)
                if not peer:
                    data = data[5:]
                    continue

                if self.address in peer.advertised_by:
                    del peer.advertised_by[self.address]
                    if len(peer.advertised_by) == 0 and peer.connection_state == UDPConnection.CONNECT_NONE:
                        del self.handler.known_peers[remote]
                        data = data[5:]
                        continue

                if len(peer.advertised_by) > 0 and peer.connection_state == UDPConnection.CONNECT_SENT:
                    rendezvous_addr = peer.advertised_by.iterkeys().next()
                    rendezvous = self.handler.connections.get(rendezvous_addr)
                    #FIXME: handle unconnected peers! I.e. delete from advertised_by list and goto next
                    if rendezvous:
                        if self.handler.reporter:
                            self.handler.reporter.add_event("UDPPuncture", "OFWC-RTR:%s,%d,%s,%s" % (rendezvous.address[0],
                                rendezvous.address[1], rendezvous.id.encode('hex'), peer.id.encode('hex')))
                        rendezvous.sendto(UDPHandler.FW_CONNECT_REQ + remote)

                data = data[5:]
            elif data[0] == UDPHandler.KEEP_ALIVE:
                data = data[1:]
            else:
                self.sendto(UDPHandler.CLOSE + UDPHandler.CLOSE_GARBAGE)
                return False

        return True

    def readvertise_nat(self):
        self.advertise_nat = True

    def remove_advertiser(self, address):
        try:
            del self.advertised_by[address]
        except:
            pass

    def send_pex(self):
        self.last_advert = time.time()

        message = ""
        if self.advertise_nat:
            self.advertise_nat = False
            message += (UDPHandler.UPDATE_NATFW_STATE +
                natfilter_to_byte(self.handler.nat_type, self.handler.filter_type) +
                chr(self.handler.natfw_version))

        if self.tracker:
            self.pex_add.clear()
            self.pex_del.clear()
        else:
            if len(self.pex_add) > 0:
                message += self.pex_string(self.pex_add, 1023, True)
            if len(self.pex_del) > 0:
                message += self.pex_string(self.pex_del, 1023 - len(message), False)
        if len(message) > 0:
            self.sendto(message)
            return True
        return False

    def pex_string(self, items, max_size, add):
        retval = ""
        num_added = 0
        added = set()
        if add:
            max_size = (max_size - 2) / 12
        else:
            max_size = (max_size - 2) / 4

        while len(items) > 0 and max_size > num_added:
            connection = items.popleft()
            if DEBUG:
                debug("- peer %s:%d (%d, %d) state %d" % (connection.address[0], connection.address[1],
                    connection.nat_type, connection.filter_type, connection.connection_state))
            if connection != self and (not connection.tracker) and (not connection.address in added) and (
                    (add and connection.connection_state == UDPConnection.CONNECT_ESTABLISHED) or
                    ((not add) and connection.connection_state != UDPConnection.CONNECT_ESTABLISHED)):
                added.add(connection.address)
                if add:
                    retval += (connection.id + address_to_string(connection.address) +
                        natfilter_to_byte(connection.nat_type, connection.filter_type) +
                        chr(connection.natfw_version))
                else:
                    retval += connection.id
                num_added += 1

        if DEBUG:
            debug("- created pex string: " + retval.encode('hex'))
        if num_added == 0:
            return ""
        if add:
            return UDPHandler.PEX_ADD + chr(num_added) + retval
        else:
            return UDPHandler.PEX_DEL + chr(num_added) + retval

# Utility functions for often used conversions
def address_to_string(address):
    return socket.inet_aton(address[0]) + chr(address[1] >> 8) + chr(address[1] & 255)

def string_to_address(address):
    return socket.inet_ntoa(address[0:4]), (ord(address[4]) << 8) + ord(address[5])

def natfilter_to_byte(nat_type, filter_type):
    return chr((nat_type & 3) + ((filter_type & 3) << 2))

def byte_to_natfilter(byte):
    return ord(byte) & 3, (ord(byte) >> 2) & 3

def compare_natfw_version(a, b):
    return ((a - b + 256) % 256) < ((b - a + 256) % 256)

if __name__ == "__main__":
    import Tribler.Core.BitTornado.RawServer as RawServer
    from threading import Event
    import thread
    from traceback import print_exc
    import os

    def fail(e):
        print "Fatal error: " + str(e)
        print_exc()

    def error(e):
        print "Non-fatal error: " + str(e)

    DEBUG = True
    def debug(msg):
        if 'log' in globals():
            log.write("%.2f: %s\n" % (time.time(), msg))
            log.flush()
        print "%.2f: %s" % (time.time(), msg)
        sys.stdout.flush()

    if len(sys.argv) == 2:
        log = open("log-%s.txt" % sys.argv[1], "w")
    else:
        log = open("log-%d.txt" % os.getpid(), "w")

    rawserver = RawServer.RawServer(Event(),
                           60.0,
                           300.0,
                           False,
                           failfunc = fail,
                           errorfunc = error)
    thread.start_new_thread(rawserver.listen_forever, (None,))
    if len(sys.argv) < 2:
        port = 0
    else:
        port = int(sys.argv[1])
    udp_handler = UDPHandler(rawserver, port)
    
    if sys.argv == "12345":
        udp_handler.connect_threshold = 0

    print "UDPHandler started, press enter to quit"
    sys.stdin.readline()
    udp_handler.shutdown()
    print "Log left in " + log.name
