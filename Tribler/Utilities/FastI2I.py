# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Simpler way of communicating with a separate process running swift via
# its CMDGW interface
#

import logging
from threading import Thread, Lock, currentThread, Event
import socket
from traceback import print_exc
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.dispersy.util import attach_profiler


class FastI2IConnection(Thread):

    def __init__(self, port, readlinecallback, closecallback):
        super(FastI2IConnection, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        name = "FastI2I" + self.getName()
        self.setName(name)
        self.setDaemon(True)

        self.port = port
        self.readlinecallback = readlinecallback
        self.closecallback = closecallback

        self.sock = None
        self.sock_connected = Event()
        # Socket only every read by self
        self.buffer = ''
        # write lock on socket
        self.lock = Lock()

        self.start()
        assert self.sock_connected.wait(60) or self.sock_connected.is_set(), 'Did not connect to socket within 60s.'

    @attach_profiler
    def run(self):

        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        data = None
        try:
            with self.lock:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(("127.0.0.1", self.port))
                self.sock_connected.set()
            while True:
                data = self.sock.recv(10240)
                if len(data) == 0:
                    break
                self.data_came_in(data)

        except:
            print_exc()

            import sys
            print >> sys.stderr, "Error while parsing, (%s)" % data or ''

        finally:
            self.close()

    def stop(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', self.port))
            s.send('')
            s.close()
        except:
            pass

    def data_came_in(self, data):
        self._logger.debug("fasti2i: data_came_in %s %s", repr(data[:40]), len(data))
        self.buffer = self.readlinecallback(self.buffer + data)
        assert self.buffer is not None, data

    def write(self, data):
        """ Called by any thread """
        self.lock.acquire()
        try:
            if self.sock is not None:
                self.sock.send(data)
        finally:
            self.lock.release()

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.closecallback(self.port)
            self.sock = None
            self.sock_connected.clear()
