import sys

from twisted.python import usage
from twisted.internet import reactor


class SubprocessLauncher(usage.Options):

    """
    This class parses options and tries to start a Tunnel Subprocess
    """

    optFlags = [
        ["tunnel_subprocess", None, "Internal: run this process as a tunnel subprocess"]
    ]

    def parse_argv(self):
        """
        Parse sys.argv for arguments

        :returns: None
        """
        remaining = sys.argv[:]
        while len(remaining):
            try:
                self.parseOptions(remaining)
                break
            except usage.UsageError:
                remaining.pop(0)
            except SystemExit:
                break


    def attempt_subprocess_start(self):
        """
        Attempt to start a subprocess, if specified

        This checks if the subprocess flag is set in the arguments.
        If it is, it launches a subprocess. Be sure not to start
        anything else if this is successful.

        :return: whether a subprocess was launched
        :rtype: bool
        """
        if 'tunnel_subprocess' in self.keys() and self['tunnel_subprocess']:
            if reactor.running:
                self._start_with_reactor()
            else:
                self._start_without_reactor()
            return True
        return False

    def _start_without_reactor(self):
        """
        The reactor does not exist yet, we will have to run it ourselves

        :returns: None
        """
        self._start_with_reactor()
        reactor.run()

    def _start_with_reactor(self):
        """
        Someone else has provided us with a reactor, simply start

        :returns: None
        """
        from Tribler.community.tunnel.processes.tunnel_subprocess import TunnelSubprocess
        subprocess = TunnelSubprocess()
        subprocess.start()
