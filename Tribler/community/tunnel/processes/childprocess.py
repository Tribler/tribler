import logging
import sys
from os import environ, kill
from os.path import isfile, join

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ProcessProtocol

from Tribler.community.tunnel.processes import CHILDFDS_ENABLED
from Tribler.community.tunnel.processes.iprocess import IProcess
from Tribler.community.tunnel.processes.line_util import pack_data, unpack_complex

CUSTOM_FDS = {0: 0,  # std in
              1: 1,  # std out
              2: 2,  # std err
              3: "w",  # ctrl in
              4: "r",  # ctrl out
              5: "w",  # data in
              6: "r",  # data out
              7: "w",  # exit in
              8: "r"}  # exit out


class ChildProcess(ProcessProtocol, IProcess):

    """
    Wrapper for a child process

    Used for creating child processes and communicating
    with them. To be overwritten for advanced
    functionality.
    """

    def __init__(self):
        """
        Initialize a ChildProcess and spawn it

        This spawns a process in the only multiplatform
        portable way. Using whatever executable and
        whatever environment we are already using.
        Only adding the --tunnel_subprocess arg.

        :returns: None
        """
        self.pid = None

        super(ChildProcess, self).__init__()

        # Raw input buffers
        self.databuffers = {1: "", 2: "", 4: "", 6: "", 8: ""}
        # Input callbacks
        self.input_callbacks = {1: self.on_generic,
                                2: self.on_stderr,
                                4: self.on_ctrl,
                                6: self.on_data,
                                8: self.on_exit}

        # Process is responsive
        self.started = Deferred()
        # One or more of the file descriptors closed unexpectedly
        self.broken = False

        # sys.path may include more than the executable path
        fixed_path = None
        for d in sys.path:
            if isfile(join(d, sys.argv[0])):
                fixed_path = d
                break

        # twistd can't deal with multiple instances
        # supplying unused pid and logfiles to facilitate this
        params = sys.argv
        if sys.argv[0].endswith("twistd"):
            params = [params[0]] + ["--pidfile", ".pidfile", "--logfile", ".logfile"] + params[1:]

        # Spawn the actual process
        self._spawn_process(sys.executable, params, fixed_path, CUSTOM_FDS if CHILDFDS_ENABLED else None)

    def _spawn_process(self, executable, params, path, fds):
        """
        Spawn a process

        :param executable: the executable to spawn
        :type executable: str
        :param params: the command line parameters to use
        :type params: [str]
        :param path: the PATH to use for execution
        :type path: str
        :param fds: the file descriptors to use
        :type fds: {int: str or int} or None
        :returns: None
        """
        sub_environ = {'TUNNEL_SUBPROCESS': '1'}
        sub_environ.update(environ)
        if fds:
            reactor.spawnProcess(self,
                                 executable,
                                 [executable]
                                 + params,
                                 env=sub_environ,
                                 path=path,
                                 childFDs=fds)
        else:
            reactor.spawnProcess(self,
                                 executable,
                                 [executable]
                                 + params,
                                 env=sub_environ,
                                 path=path)

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
        stream = int(msg[0])
        self.input_callbacks[stream](data)

    def on_stderr(self, msg):
        """
        Callback for when the child process writes to stderr

        :param msg: the message to write
        :type msg: str
        :returns: None
        """
        def print_later(m):
            print >> sys.stderr, "[CHILDPROCESS]", m
        reactor.callFromThread(print_later, msg)

    def write_ctrl(self, msg):
        """
        Write a control message to the process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 3, msg)

    def write_data(self, msg):
        """
        Write raw data to the process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 5, msg)

    def write_exit(self, msg):
        """
        Write an exit message to the process

        :param msg: the message to send
        :type msg: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 7, msg)

    def raw_write(self, fd, data):
        """
        Write data to a child's file descriptor

        :param fd: the file descriptor to write to
        :type fd: int
        :param data: the data to write
        :type data: str
        :returns: None
        """
        prefix = "" if CHILDFDS_ENABLED else str(fd)
        self.transport.writeToChild(fd if CHILDFDS_ENABLED else 0, pack_data(prefix + data))

    def connectionMade(self):
        """
        Notify users that this process is ready to go

        :returns: None
        """
        self.pid = self.transport.pid
        # Allow some time for the process to capture its streams
        reactor.callLater(1.0, self.started.callback, self)

    def childDataReceived(self, childFD, data):
        """
        Fired when the process sends us something

        :param childFD: the file descriptor which was used
        :type childFD: int
        :param data: the data which was sent
        :type data: str
        :returns: None
        """
        if childFD == 2:
            self.input_callbacks[childFD](data[:-1])
            return
        partitions = data.split('\n')
        for partition in partitions[:-1]:
            concat_data = self.databuffers.get(childFD, "") + partition + '\n'
            cc_data, out = unpack_complex(concat_data)
            self.databuffers[childFD] = cc_data
            if out is not None:
                self.input_callbacks[childFD](out)
                self.databuffers[childFD] = ""
        self.databuffers[childFD] += partitions[-1]

    def childConnectionLost(self, childFD):
        """
        Fired when a childFD is closed

        This is probably the result of a process shutdown

        :param childFD: the file descriptor which closed
        :type childFD: int
        :returns: None
        """
        self.broken = True
        logging.info("[" + str(self.pid)
                     + "] Connection lost with child FD "
                     + str(childFD))
        # We are not allowed to close the std streams
        if childFD > 2:
            self.transport.closeChildFD(childFD)

    def processEnded(self, status):
        """
        Fired when the process ends

        :param status: the exit status
        :type status: twisted.python.failure.Failure
        :returns: None
        """
        if CHILDFDS_ENABLED:
            # We are not allowed to close the std streams
            for i in xrange(3, 9):
                self.transport.closeChildFD(i)

    def terminate(self):
        """
        Terminate this process forcefully

        :returns: None
        """
        try:
            kill(self.pid, 9)
        except OSError:
            logging.error("Tried to kill already-dead process %d",
                          self.pid)
