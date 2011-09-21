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
from Tribler.Core.dispersy.callback import Callback
from Tribler.Core.dispersy.community import Community, HardKilledCommunity
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.crypto import ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.conversion import BinaryConversion

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

class BinaryTrackerConversion(BinaryConversion):
    pass

class TrackerCommunity(Community):
    """
    This community will only use dispersy-candidate-request and dispersy-candidate-response messages.
    """

    def _initialize_meta_messages(self):
        super(TrackerCommunity, self)._initialize_meta_messages()

        # remove all messages that we should not be using
        meta_messages = self._meta_messages
        self._meta_messages = {}
        for name in [u"dispersy-candidate-request",
                     u"dispersy-candidate-response",
                     u"dispersy-identity",
                     u"dispersy-missing-identity"]:
            self._meta_messages[name] = meta_messages[name]

    @property
    def dispersy_sync_initial_delay(self):
        # we should not sync ever as we will receive messages that we
        # do not understand
        return 0.0

    @property
    def dispersy_candidate_request_interval(self):
        # as a tracker we mostly rely on incoming candidate requests
        return 300.0

    def initiate_meta_messages(self):
        return []

    def initiate_conversions(self):
        return [BinaryTrackerConversion(self, "\x00")]

    def get_conversion(self, prefix=None):
        if not prefix in self._conversions:

            # the dispersy version MUST BE available.  Currently we
            # only support \x00: BinaryConversion
            if prefix[0] == "\x00":
                self._conversions[prefix] = BinaryTrackerConversion(self, prefix[1])

            else:
                raise KeyError("Unknown conversion")

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
        kargs["singleton_placeholder"] = Dispersy
        return super(TrackerDispersy, cls).get_instance(*args, **kargs)

    def __init__(self, rawserver, statedir):
        super(TrackerDispersy, self).__init__(rawserver, statedir)

        # get my_member, the key pair that we will use when we join a new community
        keypair = read_keypair(os.path.join(statedir, u"ec.pem"))
        self._my_member = Member(ec_to_public_bin(keypair), ec_to_private_bin(keypair))

    def get_community(self, cid, load=False, auto_load=True):
        try:
            return super(TrackerDispersy, self).get_community(cid, load, auto_load)
        except KeyError:
            self._communities[cid] = TrackerCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member)
            return self._communities[cid]

class DispersySocket(object):
    def __init__(self, rawserver, dispersy, port, ip="0.0.0.0"):
        while True:
            try:
                self.socket = rawserver.create_udpsocket(port, ip)
                if __debug__: dprint("Dispersy listening at ", port, force=True)
            except socket.error, error:
                port += 1
                continue
            break

        self.rawserver = rawserver
        self.rawserver.start_listening_udp(self.socket, self)
        self.dispersy = dispersy
        self.sendqueue = []

    def get_address(self):
        return self.socket.getsockname()

    def data_came_in(self, packets):
        # the rawserver SUCKS.  every now and then exceptions are not shown and apparently we are
        # sometimes called without any packets...
        if packets:
            try:
                self.dispersy.data_came_in(packets)
            except:
                traceback.print_exc()
                raise

    def send(self, address, data):
        try:
            self.socket.sendto(data, address)
        except socket.error, error:
            if error[0] == SOCKET_BLOCK_ERRORCODE:
                self.sendqueue.append((data, address))
                self.rawserver.add_task(self.process_sendqueue, 0.1)

    def process_sendqueue(self):
        sendqueue = self.sendqueue
        self.sendqueue = []

        while sendqueue:
            data, address = sendqueue.pop(0)
            try:
                self.socket.sendto(data, address)
            except socket.error, error:
                if error[0] == SOCKET_BLOCK_ERRORCODE:
                    self.sendqueue.append((data, address))
                    self.sendqueue.extend(sendqueue)
                    self.rawserver.add_task(self.process_sendqueue, 0.1)

def main():
    def on_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    def on_non_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    def start():
        # start Dispersy
        dispersy = TrackerDispersy.get_instance(callback, unicode(opt.statedir))
        dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

        schedule = []
        schedule.append((HardKilledCommunity, (), {}))
        schedule.append((TrackerCommunity, (), {}))

        # load
        for cls, args, kargs in schedule:
            counter = 0
            for counter, master in enumerate(cls.get_master_members(), 1):
                cls.load_community(master, *args, **kargs)
            print "Restored", counter, cls.get_classification(), "communities"

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=6421)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=60.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start threads
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)
    callback = Callback()
    callback.start(name="Dispersy")
    callback.register(start)

    def watchdog():
        while True:
            try:
                yield 333.3
            except GeneratorExit:
                rawserver.shutdown()
                session_done_flag.set()
                break
    callback.register(watchdog)
    rawserver.listen_forever(None)
    callback.stop()

if __name__ == "__main__":
    main()
