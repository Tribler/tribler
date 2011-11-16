#!/usr/bin/python

"""
Run Dispersy in standalone channel booster.  It will join the AllChannelCommunity.  It will join any
ChannelCommunity that it hears about.  Tribler will not be started.
"""

import os
import errno
import socket
import sys
import traceback
import threading
import optparse

from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity

from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.dispersy.callback import Callback, Idle
from Tribler.Core.dispersy.crypto import ec_from_private_pem, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.member import Member

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK

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
        dispersy = Dispersy.get_instance(callback, unicode(opt.statedir))
        dispersy.socket = DispersySocket(rawserver, dispersy, opt.port, opt.ip)

        # load my member
        ec = ec_from_private_pem(open(os.path.join(opt.statedir, "ec.pem"), "r").read())
        my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # define auto loads
        dispersy.define_auto_load(AllChannelCommunity, (my_member,), {"integrate_with_tribler":False, "auto_join_channel":True})
        dispersy.define_auto_load(ChannelCommunity, {"integrate_with_tribler":False})

        # load communities
        schedule = []
        schedule.append((AllChannelCommunity, (my_member,), {"integrate_with_tribler":False, "auto_join_channel":True}))
        schedule.append((ChannelCommunity, (), {"integrate_with_tribler":False}))

        for cls, args, kargs in schedule:
            counter = 0
            for counter, master in enumerate(cls.get_master_members(), 1):
                if dispersy.has_community(master.mid):
                    continue

                cls.load_community(master, *args, **kargs)
                yield Idle()

            if __debug__: print >> sys.stderr, "restored", counter, cls.get_classification(), "communities"

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
