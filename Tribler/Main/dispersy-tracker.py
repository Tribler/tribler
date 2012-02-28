#!/usr/bin/python

"""
Run Dispersy in standalone tracker mode.  Tribler will not be started.
"""

from time import time
from random import random
import errno
import optparse
import socket
import sys
import threading
import traceback

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.Statistics.Logger import OverlayLogger
from Tribler.Core.dispersy.callback import Callback
from Tribler.Core.dispersy.candidate import WalkCandidate
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import BinaryConversion
from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.member import DummyMember, Member

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
    def __init__(self, *args, **kargs):
        super(TrackerCommunity, self).__init__(*args, **kargs)
        # communities are cleaned based on a 'strike' rule.  periodically, we will check is there
        # are active candidates, when there are 'strike' is set to zero, otherwise it is incremented
        # by one.  once 'strike' reaches a predefined value the community is cleaned
        self._strikes = 0

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

    def update_strikes(self, now):
        # does the community have any active candidates
        for candidate in self._dispersy.candidates:
            if candidate.is_active(self, now):
                self._strikes = 0
                break
        else:
            self._strikes += 1
        return self._strikes

    def initiate_meta_messages(self):
        return []

    def initiate_conversions(self):
        return [BinaryTrackerConversion(self, "\x00")]

    def dispersy_claim_sync_bloom_filter(self, identifier):
        # disable the sync mechanism
        return None

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

    def __init__(self, callback, statedir, port):
        assert isinstance(port, int)
        assert 0 <= port
        super(TrackerDispersy, self).__init__(callback, statedir)

        # non-autoload nodes
        self._non_autoload = set()
        self._non_autoload.update(host for host, _ in self._bootstrap_candidates.iterkeys())
        # leaseweb machines, some are running boosters, they never unload a community
        self._non_autoload.update(["95.211.105.65", "95.211.105.67", "95.211.105.69", "95.211.105.71", "95.211.105.73", "95.211.105.75", "95.211.105.77", "95.211.105.79", "95.211.105.81", "85.17.81.36"])

        # logger
        overlaylogpostfix = "dp" + str(port) + ".log"
        self._logger = OverlayLogger.getInstance(overlaylogpostfix, statedir)
        self._candidates_status = {}
        callback.register(self._candidate_logger, priority=-128)

        # generate a new my-member
        ec = ec_generate_key(u"very-low")
        self._my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))

        callback.register(self._unload_communities, priority=-128)

    def get_community(self, cid, load=False, auto_load=True):
        try:
            return super(TrackerDispersy, self).get_community(cid, True, True)
        except KeyError:
            self._communities[cid] = TrackerCommunity.join_community(DummyMember(cid), self._my_member)
            return self._communities[cid]

    def _convert_packets_into_batch(self, packets):
        """
        Ensure that communities are loaded when the packet is received from a non-bootstrap node,
        otherwise, load and auto-load are disabled.
        """
        def filter_non_bootstrap_nodes():
            for candidate, packet in packets:
                cid = packet[2:22]

                if not cid in self._communities and candidate.sock_addr[0] in self._non_autoload:
                    if __debug__:
                        dprint("drop a ", len(packet), " byte packet (received from non-autoload node) from ", candidate, level="warning", force=1)
                        self._statistics.drop("_convert_packets_into_batch:from bootstrap node for unloaded community", len(packet))
                    continue

                yield candidate, packet

        packets = list(filter_non_bootstrap_nodes())
        if packets:
            return super(TrackerDispersy, self)._convert_packets_into_batch(packets)

        else:
            return []

    def yield_random_candidates(self, community):
        # the regular yield_random_candidates includes a security mechanism where we first choose
        # the category (walk or stumble) and than a candidate.  this results in a problem with flash
        # crowds, we solve this by removing the security mechanism.  this mechanism is not useful
        # for trackers as they will always receive a steady supply of valid connections as well.
        now = time()
        candidates = self._candidates.values()
        for length in xrange(len(candidates), 0, -1):
            candidate = candidates.pop(int(random() * length))
            if candidate.in_community(community, now) and candidate.is_any_active(now):
                yield candidate
        # candidates = [candidate for candidate in self._candidates.itervalues() if candidate.in_community(community, now) and candidate.is_any_active(now)]
        # for length in xrange(len(candidates), 0, -1):
        #     yield candidates.pop(int(random() * length))

    def _unload_communities(self):
        def is_active(community, now):
            # check 1: does the community have any active candidates
            if community.update_strikes(now) < 3:
                return True

            # check 2: does the community have any cached messages waiting to be processed
            for meta in self._batch_cache.iterkeys():
                if meta.community == community:
                    return True

            # the community is inactive
            return False

        while True:
            yield 180.0
            now = time()
            inactive = [community for community in self._communities.itervalues() if not is_active(community, now)]
            dprint("cleaning ", len(inactive), "/", len(self._communities), " communities")
            for community in inactive:
                community.unload_community()

    def _candidate_logger(self):
        logger = self._logger
        candidate_status = self._candidates_status
        iter_candidates = self._candidates.iteritems
        cid_hex = "0" * 40

        while True:
            yield 30.0
            now = time()

            for key, candidate in iter_candidates():
                if isinstance(candidate, WalkCandidate):
                    current_status = candidate_status.get(key, "unknown")
                    if candidate.is_any_active(now):
                        new_status = "active"
                    elif candidate.is_all_obsolete(now):
                        new_status = "obsolete"
                    else:
                        new_status = "inactive"

                    if current_status == "unknown" and new_status == "obsolete":
                        # already logged CONN_DEL
                        pass

                    elif not current_status == new_status:
                        if new_status == "active":
                            logger("CONN_ADD", cid_hex, key[0], key[1])
                            candidate_status[key] = "active"

                        elif new_status == "inactive":
                            logger("CONN_DEL", cid_hex, key[0], key[1])
                            candidate_status[key] = "inactive"

                        elif new_status == "obsolete":
                            del candidate_status[key]

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
                    break

def main():
    def on_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    def on_non_fatal_error(error):
        print >> sys.stderr, error
        session_done_flag.set()

    def start():
        # start Dispersy
        dispersy = TrackerDispersy.get_instance(callback, unicode(opt.statedir), opt.port)
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
