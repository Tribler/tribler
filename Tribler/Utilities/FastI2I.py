# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Simpler way of communicating with a separate process running swift via
# its CMDGW interface
#

import sys
from threading import Thread, Lock, currentThread, Event
import socket
from traceback import print_exc
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False

from Tribler.dispersy.decorator import attach_profiler

DEBUG = False


class FastI2IConnection(Thread):

    def __init__(self, port, readlinecallback, closecallback):
        Thread.__init__(self)
        self.setName("FastI2I" + self.getName())
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
        assert self.sock_connected.wait(60), 'Did not connect to socket within 60s.'

    @attach_profiler
    def run(self):

        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        try:
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
        """ Read \r\n ended lines from data and call readlinecallback(self,line) """
        # data may come in in parts, not lines! Or multiple lines at same time

        if DEBUG:
            print >> sys.stderr, "fasti2i: data_came_in", repr(data), len(data)

        if len(self.buffer) == 0:
            self.buffer = data
        else:
            self.buffer = self.buffer + data
        self.read_lines()

    def read_lines(self):
        while True:
            cmd, separator, self.buffer = self.buffer.partition("\r\n")
            if separator:
                if self.readlinecallback(self, cmd):
                    # 01/05/12 Boudewijn: when a positive value is returned we immediately return to
                    # allow more bytes to be pushed into the buffer
                    self.buffer = "".join((cmd, separator, self.buffer))

                    # 06/05/13 Boudewijn: we must return to read the remainder of the data.  note
                    # that the remainder (all bytes behind the first separator) must be removed from
                    # self.buffer during the readlinecallback call
                    break

            else:
                self.buffer = cmd
                break

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
