#!/usr/bin/python

"""
Run Dispersy in standalone tracker mode.  Tribler will not be started.
"""

import hashlib
import os
import errno
import socket
import sys
import time
import traceback
import threading
import optparse

from Tribler.Core.Overlay.permid import read_keypair
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.member import MyMember
from Tribler.Core.dispersy.crypto import ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.conversion import BinaryConversion

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

class TrackerConversion(BinaryConversion):
    pass

class TrackerCommunity(Community):
    """
    This community will only use dispersy-candidate-request and dispersy-candidate-response messages.
    """
    @classmethod
    def join_community(cls, cid, master_key, my_member, *args, **kargs):
        assert isinstance(cid, str)
        assert len(cid) == 20
        assert isinstance(master_key, str)
        assert not master_key or cid == sha1(master_key).digest()
        assert isinstance(my_member, MyMember)

        database = DispersyDatabase.get_instance()
        database.execute(u"INSERT INTO community(user, classification, cid, public_key) VALUES(?, ?, ?, ?)",
                         (my_member.database_id, cls.get_classification(), buffer(cid), buffer(master_key)))

        print "Join community", cid.encode("HEX")

        # new community instance
        community = cls(cid, master_key, *args, **kargs)

        # send out my initial dispersy-identity
        community.create_dispersy_identity()

        return community

    def __init__(self, cid, master_key):
        super(TrackerCommunity, self).__init__(cid, master_key)

    def _initialize_meta_messages(self):
        super(TrackerCommunity, self)._initialize_meta_messages()

        # remove all messages that we should not be using
        meta_messages = self._meta_messages
        self._meta_messages = {}
        for name in [u"dispersy-candidate-request",
                     u"dispersy-candidate-response",
                     u"dispersy-identity",
                     u"dispersy-identity-request",
                     u"dispersy-destroy-community"]:
            self._meta_messages[name] = meta_messages[name]

    @property
    def dispersy_sync_initial_delay(self):
        # we should not sync ever as we will receive messages that we
        # do not understand
        return 0.0

    def initiate_meta_messages(self):
        return []

    def get_conversion(self, prefix=None):
        if not prefix in self._conversions:
            self._conversions[prefix] = TrackerConversion(self, prefix[20:22])

            # use highest version as default
            if None in self._conversions:
                if self._conversions[None].version < self._conversions[prefix].version:
                    self._conversions[None] = self._conversions[prefix]
            else:
                self._conversions[None] = self._conversions[prefix]

        return self._conversions[prefix]

class TrackerDispersy(Dispersy):
    @classmethod
    def get_instance(cls, *args, **kargs):
        kargs["singleton_superclass"] = Dispersy
        return super(TrackerDispersy, cls).get_instance(*args, **kargs)

    def __init__(self, rawserver, statedir):
        super(TrackerDispersy, self).__init__(rawserver, statedir)

        # get my_member, the key pair that we will use when we join a new community
        keypair = read_keypair(os.path.join(statedir, u"ec.pem"))
        self._my_member = MyMember(ec_to_public_bin(keypair), ec_to_private_bin(keypair))

    def get_community(self, cid):
        if not cid in self._communities:
            self._communities[cid] = TrackerCommunity.join_community(cid, "", self._my_member)
        return self._communities[cid]

class DispersySocket(object):
    def __init__(self, rawserver, dispersy, port, ip="0.0.0.0"):
        while True:
            if __debug__: dprint("Dispersy listening at ", port)
            try:
                self.socket = rawserver.create_udpsocket(port, ip)
            except socket.error, error:
                port += 1
                continue
            break

        self.rawserver = rawserver
        self.rawserver.start_listening_udp(self.socket, self)
        self.dispersy = dispersy

    def get_address(self):
        return self.socket.getsockname()

    def data_came_in(self, packets):
        self.dispersy.on_incoming_packets(packets)

    def send(self, address, data):
        try:
            self.socket.sendto(data, address)
        except socket.error, error:
            if error[0] == SOCKET_BLOCK_ERRORCODE:
                self.sendqueue.append((data, address))
                self.rawserver.add_task(self.process_sendqueue, 0.1)

def main():
    def on_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    def on_non_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=6421)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=60.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start RawServer
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)

    # start Dispersy
    dispersy = TrackerDispersy.get_instance(rawserver, unicode(opt.statedir))
    dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

    # load the existing Tracker communities
    print "Restored", len(TrackerCommunity.load_communities()), "tracker communities"

    rawserver.listen_forever(None)
    session_done_flag.set()
    time.sleep(1)

if __name__ == "__main__":
    main()
