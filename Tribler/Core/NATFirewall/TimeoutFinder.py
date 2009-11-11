# Written by Gertjan Halkes
# see LICENSE.txt for license information


import struct
import time
import sys

DEBUG = False

class TimeoutFinder:
    PINGBACK_TIMES = [ 245, 235, 175, 115, 85, 55, 25, 10 ]
    PINGBACK_ADDRESS = ("mughal.tribler.org", 7396)

    def __init__(self, rawserver, initial_ping, reportback = None):
        self.sockets = []
        self.rawserver = rawserver
        self.timeout_found = -1
        self.initial_ping = initial_ping
        self.reportback = reportback
        self.timeout_index = 0

        # Stagger the pings by 1 second to unsure minimum impact on other traffic
        rawserver.add_task(self.ping, 1)
        rawserver.add_task(self.report_done, TimeoutFinder.PINGBACK_TIMES[0] + 5)


    def ping(self):
        sock = self.rawserver.create_udpsocket(0, "0.0.0.0")
        self.sockets.append(sock)
        self.rawserver.start_listening_udp(sock, self)
        if self.initial_ping:
            sock.sendto(struct.pack("!Id", 0, float(TimeoutFinder.PINGBACK_TIMES[self.timeout_index])),
                TimeoutFinder.PINGBACK_ADDRESS)
        else:
            sock.sendto(struct.pack("!Id", TimeoutFinder.PINGBACK_TIMES[self.timeout_index],
                time.time()), TimeoutFinder.PINGBACK_ADDRESS)
        self.timeout_index += 1
        if self.timeout_index < len(TimeoutFinder.PINGBACK_TIMES):
            self.rawserver.add_task(self.ping, 1)


    def data_came_in(self, address, data):
        if len(data) != 12:
            return
        #FIXME: the address should be checked, but that can only be done if
        # the address is in dotted-decimal notation
        #~ if address != TimeoutFinder.PINGBACK_ADDRESS:
            #~ return

        timeout = struct.unpack("!Id", data)
        if timeout[0] == 0:
            to_find = int(timeout[1])
            for i in range(0, len(TimeoutFinder.PINGBACK_TIMES)):
                if to_find == TimeoutFinder.PINGBACK_TIMES[i]:
                    self.sockets[i].sendto(struct.pack("!Id", to_find, time.time()), TimeoutFinder.PINGBACK_ADDRESS)
                    break
        else:
            if DEBUG:
                print >>sys.stderr, ("Received ping with %d delay" % (timeout[0]))
            self.timeout_found = timeout[0]
            #FIXME: log reception of packet

    def report_done(self):
        for i in self.sockets:
            self.rawserver.stop_listening_udp(i)
            i.close()

        if self.reportback:
            self.reportback(self.timeout_found, self.initial_ping)


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

    def report(timeout, initial_ping):
        if initial_ping:
            with_ = "with"
        else:
            with_ = "without"

        if DEBUG:
            print >>sys.stderr, ("Timeout %s initial ping: %d" % (with_, timeout))

    DEBUG = True

    log = open("log-timeout.txt", "w")

    rawserver_ = RawServer.RawServer(Event(),
                           60.0,
                           300.0,
                           False,
                           failfunc = fail,
                           errorfunc = error)
    thread.start_new_thread(rawserver_.listen_forever, (None,))
    time.sleep(0.5)
    TimeoutFinder(rawserver_, False, report)
    TimeoutFinder(rawserver_, True, report)

    print "TimeoutFinder started, press enter to quit"
    sys.stdin.readline()
