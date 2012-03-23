#!/usr/bin/python

"""
Run Dispersy in standalone mode.  Tribler will not be started.
"""

import errno
import optparse
import socket
import sys
import threading
import time
import traceback

# from Tribler.Community.Discovery.Community import DiscoveryCommunity
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.callback import Callback
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
            self.sendqueue_lock = threading.Lock()
            self.sendqueue = []

        def get_address(self):
            return self.socket.getsockname()

        def data_came_in(self, packets):
            # called on the Tribler rawserver

            # the rawserver SUCKS.  every now and then exceptions are not shown and apparently we are
            # sometimes called without any packets...
            if packets:
                # for address, data in packets:
                #     meta = self.dispersy.convert_packet_to_meta_message(data, load=False)
                #     print "%.1f %30s <- %15s:%-5d %4d bytes" % (time.time(), meta.name, address[0], address[1], len(data))

                try:
                    self.dispersy.data_came_in(packets)
                except:
                    traceback.print_exc()
                    raise

        def send(self, address, data):
            # meta = self.dispersy.convert_packet_to_meta_message(data, load=False)
            # print "%.1f %30s -> %15s:%-5d %4d bytes" % (time.time(), meta.name, address[0], address[1], len(data))

            with self.sendqueue_lock:
                if self.sendqueue:
                    self.sendqueue.append((data, address))
                else:
                    try:
                        self.socket.sendto(data, address)

                    except socket.error, error:
                        if error[0] == SOCKET_BLOCK_ERRORCODE:
                            self.sendqueue.append((data, address))
                            print >> sys.stderr, time.time(), "sendqueue overflowing", len(self.sendqueue), "(first schedule)"
                            self.rawserver.add_task(self.process_sendqueue, 0.1)

        def process_sendqueue(self):
            print >> sys.stderr, time.time(), "sendqueue overflowing", len(self.sendqueue)

            with self.sendqueue_lock:
                while self.sendqueue:
                    data, address = self.sendqueue.pop(0)
                    try:
                        self.socket.sendto(data, address)

                    except socket.error, error:
                        if error[0] == SOCKET_BLOCK_ERRORCODE:
                            self.sendqueue.insert(0, (data, address))
                            self.rawserver.add_task(self.process_sendqueue, 0.1)
                            break

    def on_fatal_error(error):
        print >> sys.stderr, "Rawserver fatal error:", error
        global exit_exception
        exit_exception = error
        session_done_flag.set()

    def on_non_fatal_error(error):
        print >> sys.stderr, "Rawserver non fatal error:", error

    def start():
        # start Dispersy
        dispersy = Dispersy.get_instance(callback, unicode(opt.statedir))
        dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

        # load the script parser
        if opt.script:
            from Tribler.Core.dispersy.script import Script
            script = Script.get_instance(callback)

            script_kargs = {}
            if opt.script_args:
                for arg in opt.script_args.split(','):
                    key, value = arg.split('=')
                    script_kargs[key] = value

            if not opt.disable_dispersy_script:
                from Tribler.Core.dispersy.script import DispersyClassificationScript, DispersyTimelineScript, DispersyDestroyCommunityScript, DispersyBatchScript, DispersySyncScript, DispersyIdenticalPayloadScript, DispersySubjectiveSetScript, DispersySignatureScript, DispersyMemberTagScript, DispersyMissingMessageScript, DispersyUndoScript, DispersyCryptoScript, DispersyDynamicSettings, DispersyBootstrapServers
                script.add("dispersy-batch", DispersyBatchScript)
                script.add("dispersy-classification", DispersyClassificationScript)
                script.add("dispersy-crypto", DispersyCryptoScript)
                script.add("dispersy-destroy-community", DispersyDestroyCommunityScript)
                script.add("dispersy-dynamic-settings", DispersyDynamicSettings)
                script.add("dispersy-identical-payload", DispersyIdenticalPayloadScript)
                script.add("dispersy-member-tag", DispersyMemberTagScript)
                script.add("dispersy-missing-message", DispersyMissingMessageScript)
                script.add("dispersy-signature", DispersySignatureScript)
                script.add("dispersy-subjective-set", DispersySubjectiveSetScript)
                script.add("dispersy-sync", DispersySyncScript)
                script.add("dispersy-timeline", DispersyTimelineScript)
                script.add("dispersy-undo", DispersyUndoScript)
                script.add("dispersy-bootstrap-servers", DispersyBootstrapServers)

            if not opt.disable_allchannel_script:
                # from Tribler.Community.allchannel.script import AllChannelScript
                # script.add("allchannel", AllChannelScript, include_with_all=False)

                from Tribler.community.allchannel.script import AllChannelScenarioScript
                script.add("allchannel-scenario", AllChannelScenarioScript, script_kargs, include_with_all=False)

            if not opt.disable_walktest_script:
                from Tribler.community.walktest.script import ScenarioScript
                script.add("walktest-scenario", ScenarioScript, script_kargs, include_with_all=False)

            if not opt.disable_effort_script:
                from Tribler.community.effort.script import ScenarioScript
                script.add("effort-scenario", ScenarioScript, script_kargs, include_with_all=False)

            # if not opt.disable_barter_script:
            #     from Tribler.Community.barter.script import BarterScript, BarterScenarioScript
            #     script.add("barter", BarterScript)
            #     script.add("barter-scenario", BarterScenarioScript, script_kargs, include_with_all=False)

            # # bump the rawserver, or it will delay everything... since it sucks.
            # def bump():
            #     pass
            # rawserver.add_task(bump)

            script.load(opt.script)

    command_line_parser = optparse.OptionParser()
    command_line_parser.add_option("--statedir", action="store", type="string", help="Use an alternate statedir", default=u".")
    command_line_parser.add_option("--ip", action="store", type="string", default="0.0.0.0", help="Dispersy uses this ip")
    command_line_parser.add_option("--port", action="store", type="int", help="Dispersy uses this UDL port", default=12345)
    command_line_parser.add_option("--timeout-check-interval", action="store", type="float", default=1.0)
    command_line_parser.add_option("--timeout", action="store", type="float", default=300.0)
    command_line_parser.add_option("--disable-allchannel-script", action="store_true", help="Include allchannel scripts", default=False)
    command_line_parser.add_option("--disable-barter-script", action="store_true", help="Include barter scripts", default=False)
    command_line_parser.add_option("--disable-dispersy-script", action="store_true", help="Include dispersy scripts", default=False)
    command_line_parser.add_option("--disable-walktest-script", action="store_true", help="Include walktest scripts", default=False)
    command_line_parser.add_option("--disable-effort-script", action="store_true", help="Include effort scripts", default=False)
    command_line_parser.add_option("--script", action="store", type="string", help="Runs the Script python file with <SCRIPT> as an argument")
    command_line_parser.add_option("--script-args", action="store", type="string", help="Executes --script with these arguments.  Example 'startingtimestamp=1292333014,endingtimestamp=12923340000'")

    # parse command-line arguments
    opt, args = command_line_parser.parse_args()
    print "Press Ctrl-C to stop Dispersy"

    # start threads
    session_done_flag = threading.Event()
    rawserver = RawServer(session_done_flag, opt.timeout_check_interval, opt.timeout, False, failfunc=on_fatal_error, errorfunc=on_non_fatal_error)
    callback = Callback()
    callback.start(name="Dispersy")

    def rawserver_adrenaline():
        """
        The rawserver tends to wait for a long time between handling tasks.  Our tests will fail if
        they are delayed by the rawserver for too long.
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
    callback.register(start)
    rawserver.listen_forever(None)
    callback.stop()

    if callback.exception:
        global exit_exception
        exit_exception = callback.exception

if __name__ == "__main__":
    exit_exception = None
    main()
    if exit_exception:
        raise exit_exception
