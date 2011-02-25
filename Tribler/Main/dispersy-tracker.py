#!/usr/bin/python

"""
Run Dispersy in standalone tracker mode.  Tribler will not be started.
"""

import errno
import socket
import sys
import time
import traceback
import threading
import optparse

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

class TrackerCommunity(Community):
    """
    This community will only use dispersy-routing-request and dispersy-routing-response messages.
    """
    def __init__(self, cid):
        super(TrackerCommunity, self).__init__(cid)

        # remove all messages that we should not be using
        meta_messages = self._meta_messages
        self._meta_messages = {}
        for name in [u"dispersy-routing-request",
                     u"dispersy-routing-response",
                     u"dispersy-identity",
                     u"dispersy-identity-request",
                     u"dispersy-destroy-community"]:
            self._meta_messages[name] = meta_messages[name]

    @property
    def dispersy_sync_interval(self):
        # because there is nothing to sync in this community, we will only 'sync' once per hour
        return 3600.0

    def get_conversion(self, prefix=None):
        # pick the default conversion if none match
        if not prefix in self._conversions:
            assert None in self._conversions
            prefix = None
        return self._conversions[prefix]

    @classmethod
    def join_community(cls, cid, my_member, *args, **kargs):
        assert isinstance(cid, str)
        assert len(cid) == 20
        database = DispersyDatabase.get_instance()
        database.execute(u"INSERT INTO community(user, cid, classification, public_key) VALUES(?, ?, ?, ?)",
                         (my_member.database_id, buffer(cid), cls.get_classification(), buffer("-unknown-")))

        # new community instance
        community = cls(cid, *args, **kargs)

        return community

class TrackerDispersy(Dispersy):
    def get_community(self, cid):
        # return an existing TrackerCommunity or create a new one
        if not cid in self._communities:
            self._communities[cid] = TrackerCommunity.join_community(cid)
        return self._communities[cid]

class DispersySocket(object):
    def __init__(self, rawserver, dispersy, port, ip="0.0.0.0"):
        while True:
            if __debug__: dprint("Dispersy listening at ", port)
            try:
                self.socket = rawserver.create_udpsocket(port, ip)
            except socket.error as error:
                port += 1
                continue
            break

        self.rawserver = rawserver
        self.rawserver.start_listening_udp(self.socket, self)
        self.dispersy = dispersy

    def get_address(self):
        return self.socket.getsockname()

    def data_came_in(self, address, data):
        self.dispersy.on_incoming_packets([(address, data)])

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
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=u".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=12345)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=60.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start RawServer
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)

    # start Dispersy
    dispersy = TrackerDispersy.get_instance(rawserver, opt.statedir)
    dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

    # load the existing Tracker communities
    print "Restored", len(TrackerCommunity.load_communities()), "tracker communities"

    rawserver.listen_forever(None)
    session_done_flag.set()
    time.sleep(1)

if __name__ == "__main__":
    main()
