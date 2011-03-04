#!/usr/bin/python

"""
Run Dispersy in standalone mode.  Tribler will not be started.
"""

import errno
import socket
import sys
import time
import traceback
import threading
import optparse

# from Tribler.Community.Discovery.Community import DiscoveryCommunity
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.dispersy import Dispersy

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

def main():
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

        def data_came_in(self, address, data):
            self.dispersy.on_incoming_packets([(address, data)])

        def send(self, address, data):
            try:
                self.socket.sendto(data, address)
            except socket.error, error:
                if error[0] == SOCKET_BLOCK_ERRORCODE:
                    self.sendqueue.append((data, address))
                    self.rawserver.add_task(self.process_sendqueue, 0.1)

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
    command_line_parser.add_option("--script", action="store", type="string", help="Runs the Script python file with <SCRIPT> as an argument")
    command_line_parser.add_option("--script-args", action="store", type="string", help="Executes --script with these arguments.  Example 'startingtimestamp=1292333014,endingtimestamp=12923340000'")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start RawServer
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)

    # start Dispersy
    dispersy = Dispersy.get_instance(rawserver, opt.statedir)
    dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

    # # load the Discovery community
    # discovery, = DiscoveryCommunity.load_communities()
    # assert discovery == DiscoveryCommunity.get_instance()

    # load the script parser
    if opt.script:
        from Tribler.Core.dispersy.script import Script, DispersyTimelineScript, DispersyRoutingScript, DispersyDestroyCommunityScript, DispersySyncScript, DispersySubjectiveSetScript, DispersySignatureScript, DispersyMemberTagScript
        from Tribler.Community.allchannel.script import AllChannelScript
        from Tribler.Community.barter.script import BarterScript, BarterScenarioScript
        from Tribler.Community.discovery.script import DiscoveryUserScript, DiscoveryCommunityScript, DiscoverySyncScript

        args = {}
        if opt.script_args:
            for arg in opt.script_args.split(','):
                key, value = arg.split('=')
                args[key] = value

        script = Script.get_instance(rawserver)
        script.add("allchannel", AllChannelScript, include_with_all=False)
        script.add("dispersy-timeline", DispersyTimelineScript)
        script.add("dispersy-routing", DispersyRoutingScript)
        script.add("dispersy-destroy-community", DispersyDestroyCommunityScript)
        script.add("dispersy-sync", DispersySyncScript)
        # script.add("dispersy-similarity", DispersySimilarityScript)
        script.add("dispersy-signature", DispersySignatureScript)
        script.add("dispersy-member-tag", DispersyMemberTagScript)
        script.add("dispersy-subjective-set", DispersySubjectiveSetScript)
        script.add("discovery-user", DiscoveryUserScript)
        script.add("discovery-community", DiscoveryCommunityScript)
        script.add("discovery-sync", DiscoverySyncScript)
        script.add("barter", BarterScript)
        script.add("barter-scenario", BarterScenarioScript, args, include_with_all=False)
        script.load(opt.script)

    rawserver.listen_forever(None)
    session_done_flag.set()
    time.sleep(1)

if __name__ == "__main__":
    main()
