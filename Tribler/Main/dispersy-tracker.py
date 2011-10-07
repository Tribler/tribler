#!/usr/bin/python

"""
Run Dispersy in standalone tracker mode.  Tribler will not be started.
"""

import errno
import socket
import sys
import traceback
import threading
import optparse

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.callback import Callback
from Tribler.Core.dispersy.community import SyncRange, Community
from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.member import Member

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

class BinaryTrackerConversion(BinaryConversion):
    pass

class TrackerSyncRange(SyncRange):
    def __init__(self):
        self.time_low = 1
        self.space_freed = 0
        self.bloom_filters = [BloomFilter("\xff", 1, 8, prefix="\x00")]
        self.space_remaining = self.capacity = 2 ** 64 - 1

    def add(self, packet):
        pass

    def free(self):
        pass

    def clear(self):
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
        for name in [u"dispersy-introduction-request",
                     u"dispersy-introduction-response",
                     u"dispersy-puncture-request",
                     u"dispersy-puncture",
                     u"dispersy-identity",
                     u"dispersy-missing-identity"]:
            self._meta_messages[name] = meta_messages[name]

    def initiate_meta_messages(self):
        return []

    def initiate_conversions(self):
        return [BinaryTrackerConversion(self, "\x00")]

    def _initialize_sync_ranges(self):
        self._sync_ranges.insert(0, TrackerSyncRange())
    
    def dispersy_claim_sync_bloom_filter(self, identifier):
        # the tracker doesn't want any data... so our bloom filter must be full
        return 1, 1, self._sync_ranges[0].bloom_filters[0]
    
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

    def __init__(self, callback, statedir):
        super(TrackerDispersy, self).__init__(callback, statedir)

        # generate a new my-member
        ec = ec_generate_key(u"very-low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))

        callback.register(self._unload_communities)
        callback.register(self._stats)

    def get_community(self, cid, load=False, auto_load=True):
        try:
            return super(TrackerDispersy, self).get_community(cid, True, True)
        except KeyError:
            self._communities[cid] = TrackerCommunity.join_community(Member.get_instance(cid, public_key_available=False), self._my_member)
            return self._communities[cid]

    def _unload_communities(self):
        def has_candidates(community):
            try:
                self.yield_candidates(community, 1).next()
            except StopIteration:
                return False
            else:
                return True
        
        while True:
            yield 60.0
            for community in [community for community in self._communities.itervalues() if not has_candidates(community)]:
                community.unload_community()

    def _stats(self):
        while True:
            yield 10.0
            for community in self._communities.itervalues():
                candidates = list(sock_address for sock_address, _ in self.yield_all_candidates(community))
                print community.cid.encode("HEX"), len(candidates), "candidates[:10]", ", ".join("%s:%d" % sock_address for sock_address in candidates[:10])
        
class DispersySocket(object):
    def __init__(self, rawserver, dispersy, port, ip="0.0.0.0"):
        while True:
            try:
                self.socket = rawserver.create_udpsocket(port, ip)
                if __debug__: dprint("Dispersy listening at ", port, force=True)
            except socket.error:
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
        dispersy.define_auto_load(TrackerCommunity)

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=6421)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=60.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)

    # parse command-line arguments
    opt, _ = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start threads
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)
    callback = Callback()
    callback.start(name="Dispersy")
    callback.register(start)

    def rawserver_adrenaline():
        """
        The rawserver tends to wait for a long time between handling tasks.
        """
        rawserver.add_task(rawserver_adrenaline, 0.1)
    rawserver.add_task(rawserver_adrenaline, 0.1)

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
