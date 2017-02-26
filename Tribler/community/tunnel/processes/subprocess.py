"""
Each subprocess has 6 additional file descriptors
(next to the stdin, stdout and stderr). These are:

 - ctrl_in:  for receiving control messages
 - ctrl_out: for responding to control messages
 - data_in:  for receiving bulk data
 - data_out: for sending bulk data
 - exit_in:  for receiving exit signals
 - exit_out: for responding to exit signals
"""

import io
import logging
import os
import sys
import threading

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.community.tunnel.processes import CHILDFDS_ENABLED
from Tribler.community.tunnel.processes.iprocess import IProcess
from Tribler.community.tunnel.processes.line_util import pack_data, unpack_complex

FNO_CTRL_IN = 3
FNO_CTRL_OUT = 4
FNO_DATA_IN = 5
FNO_DATA_OUT = 6
FNO_EXIT_IN = 7
FNO_EXIT_OUT = 8

FILE_CTRL_IN = io.open(FNO_CTRL_IN, "rb", 0) if CHILDFDS_ENABLED else sys.__stdin__
FILE_CTRL_OUT = io.open(FNO_CTRL_OUT, "wb", 0) if CHILDFDS_ENABLED else sys.__stdout__
FILE_DATA_IN = io.open(FNO_DATA_IN, "rb", 0) if CHILDFDS_ENABLED else sys.__stdin__
FILE_DATA_OUT = io.open(FNO_DATA_OUT, "wb", 0) if CHILDFDS_ENABLED else sys.__stdout__
FILE_EXIT_IN = io.open(FNO_EXIT_IN, "rb", 0) if CHILDFDS_ENABLED else sys.__stdin__
FILE_EXIT_OUT = io.open(FNO_EXIT_OUT, "wb", 0) if CHILDFDS_ENABLED else sys.__stdout__

if not CHILDFDS_ENABLED:
    # The default stderr is way too slow flushing
    # its buffer. This causes congestion and slow down.
    class AutoFlushErrWriter(object):

        def write(self, s):
            sys.__stderr__.write(s)
            sys.__stderr__.flush()

        def __getattr__(self, item):
            return getattr(sys.__stderr__, item)

    sys.stderr = AutoFlushErrWriter()
    sys.stdout = sys.stderr

LOCK_GENERIC = None if CHILDFDS_ENABLED else threading.Lock()
LOCK_CTRL = threading.Lock() if CHILDFDS_ENABLED else LOCK_GENERIC
LOCK_DATA = threading.Lock() if CHILDFDS_ENABLED else LOCK_GENERIC
LOCK_EXIT = threading.Lock() if CHILDFDS_ENABLED else LOCK_GENERIC


class LineConsumer(threading.Thread):

    """
    Daemon thread to consume file data.
    """

    def __init__(self, file_obj, data_callback):
        """
        Initialize a LineConsumer

        :param file_obj: The file object to read
        :type file_obj: file
        :param data_callback: The callback for when data is read
        :type data_callback: func
        :returns: None
        """
        super(LineConsumer, self).__init__()

        self.file_obj = file_obj
        self.data_callback = data_callback
        self.daemon = True
        self.start()

    def run(self):
        """
        Keep consuming from the line until it is closed

        :returns: None
        """
        line = ""
        while not self.file_obj.closed:
            try:
                line += self.file_obj.readline()
            except IOError:
                break
            if line.endswith('\n') and len(line) > 8:
                line, data = unpack_complex(line)
                if data is not None:
                    reactor.callInThread(self.data_callback, data)


class Subprocess(IProcess):

    """
    The main entry-point handle: a subprocess object.
    Overwritten by the subprocess for more advanced
    functionality.
    """

    def __init__(self):
        """
        Initialize a new Subprocess

        :returns: None
        """
        super(Subprocess, self).__init__()

        self.closed = Deferred()

    def start(self):
        """
        Start consuming from the input file descriptors

        :returns: None
        """
        if CHILDFDS_ENABLED:
            LineConsumer(FILE_CTRL_IN, self.on_ctrl)
            LineConsumer(FILE_DATA_IN, self.on_data)
            LineConsumer(FILE_EXIT_IN, self.on_exit)
        else:
            LineConsumer(sys.__stdin__, self.on_generic)

    def on_generic(self, msg):
        """
        Callback for when a multiplexed message is sent over
        a stream. These have their intended stream identifier
        as the first character.

        :param msg: the received message
        :type msg: str
        :returns: None
        """
        data = msg[1:]
        try:
            stream = int(msg[0])
            if stream == FNO_CTRL_IN:
                self.on_ctrl(data)
            elif stream == FNO_DATA_IN:
                self.on_data(data)
            elif stream == FNO_EXIT_IN:
                self.on_exit(data)
            else:
                logging.error("Got data for unknown file descriptor " + msg[0])
        except ValueError:
            logging.error("Got data for unknown file descriptor " + msg[0])

    def write_ctrl(self, msg):
        """
        Write a control message to the parent process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        Subprocess.write(FILE_CTRL_OUT, FNO_CTRL_OUT, msg, LOCK_CTRL)

    def write_data(self, msg):
        """
        Write raw data to the parent process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        Subprocess.write(FILE_DATA_OUT, FNO_DATA_OUT, msg, LOCK_DATA)

    def write_exit(self, msg):
        """
        Write an exit message to the parent process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        Subprocess.write(FILE_EXIT_OUT, FNO_EXIT_OUT, msg, LOCK_EXIT)

    @staticmethod
    def close_all_streams():
        """
        Close all registered file descriptors

        :returns: None
        """
        # We use the fact that they are assigned
        # to the range [3, 8].
        if CHILDFDS_ENABLED:
            for fno in xrange(3, 9, 1):
                Subprocess.close(fno)

    @staticmethod
    def write(f, fno, data, lock):
        """
        Write to the parent process

        :param f: the file to write to
        :type f: file
        :param data: the data to write
        :type data: str
        :param lock: the Lock to acquire
        :type lock: threading.Lock
        :returns: None
        """
        prefix = "" if CHILDFDS_ENABLED else str(fno)
        packed = pack_data(prefix + data)
        lock.acquire(True)
        try:
            f.write(packed)
            f.flush()
        except IOError:
            pass
        finally:
            lock.release()

    @staticmethod
    def close(fno):
        """
        Close a file descriptor

        :param fno: the file descriptor number
        :type fno: int
        :returns: None
        """
        os.close(fno)

    def end(self):
        """
        End the Subprocess

        Close all streams and call the closed callback

        :returns: None
        """
        self.close_all_streams()
        self.closed.callback(True)
        reactor.callFromThread(reactor.stop)

    @inlineCallbacks
    def block_until_end(self):
        """
        Wait until the Subprocess is closed

        :returns: None
        """
        yield self.closed
