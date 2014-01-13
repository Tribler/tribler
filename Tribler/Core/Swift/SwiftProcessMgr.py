# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import urlparse
import binascii
import random
import time
from traceback import print_exc, print_stack
import threading

from Tribler.Core.Swift.SwiftProcess import *
from Tribler.Utilities.Instance2Instance import *


DEBUG = False


class SwiftProcessMgr:

    """ Class that manages a number of SwiftProcesses """

    def __init__(self, binpath, i2iport, dlsperproc, tunnellistenport, sesslock):
        self.binpath = binpath
        self.i2iport = i2iport
        # ARNOSMPTODO: Implement such that a new proc is created when needed
        self.dlsperproc = dlsperproc
        self.tunnellistenport = tunnellistenport
        self.sesslock = sesslock
        self.done = False

        self.sps = []

    def get_or_create_sp(self, workdir, zerostatedir, listenport, httpgwport, cmdgwport):
        """ Download needs a process """
        self.sesslock.acquire()
        if not self.done:
            # print >>sys.stderr,"spm: get_or_create_sp"
            try:
                self.clean_sps()

                sp = None
                if listenport is not None:
                    # Reuse the one with the same requested listen port
                    for sp2 in self.sps:
                        if sp2.listenport == listenport:
                            sp = sp2
                            # print >>sys.stderr,"spm: get_or_create_sp: Reusing",sp2.get_pid()

                elif self.dlsperproc > 1:
                    # Find one with room, distribute equally
                    random.shuffle(self.sps)
                    for sp2 in self.sps:
                        if len(sp2.get_downloads()) < self.dlsperproc:
                            sp = sp2
                            if DEBUG:
                                print("spm: get_or_create_sp: Reusing", sp.get_pid(), file=sys.stderr)
                            break

                if sp is None:
                    # Create new process
                    sp = SwiftProcess(self.binpath, workdir, zerostatedir, listenport, httpgwport, cmdgwport, self)
                    print("spm: get_or_create_sp: Creating new", sp.get_pid(), file=sys.stderr)
                    self.sps.append(sp)

                    # Arno, 2011-10-13: On Linux swift is slow to start and
                    # allocate the cmd listen socket?!
                    # 2012-05-23: connection_lost() will attempt another
                    # connect when the first fails, so not timing dependent,
                    # just ensures no send_()s get lost. Executed by NetworkThread.
                    if sys.platform == "linux2" or sys.platform == "darwin":
                        print("spm: Need to sleep 1 second for swift to start on Linux?! FIXME", file=sys.stderr)
                        time.sleep(1)

                    sp.start_cmd_connection()

                return sp
            finally:
                self.sesslock.release()

    def release_sp(self, sp):
        """ Download no longer needs process. Apply process-cleanup policy """
        # ARNOSMPTODO: MULTIPLE: Add policy param on whether to keep process around when no downloads.
        self.sesslock.acquire()
        try:
            # Arno, 2012-05-23: Don't kill tunneling swift process
            if sp.get_listen_port() == self.tunnellistenport:
                return

            # Niels, 2013-05-15: Don't kill at all we want a swift process as a background process
            if False and len(sp.get_downloads()) == 0:
                self.destroy_sp(sp)
        finally:
            self.sesslock.release()

    def destroy_sp(self, sp):
        print("spm: destroy_sp:", sp.get_pid(), file=sys.stderr)
        self.sesslock.acquire()
        try:
            self.sps.remove(sp)
            sp.early_shutdown()
            # Don't need gracetime, no downloads left.
            sp.network_shutdown()
        finally:
            self.sesslock.release()

    def clean_sps(self):
        # lock held
        deads = []
        for sp in self.sps:
            if not sp.is_alive():
                print("spm: clean_sps: Garbage collecting dead", sp.get_pid(), file=sys.stderr)
                deads.append(sp)
        for sp in deads:
            self.sps.remove(sp)

    def early_shutdown(self):
        """ First phase of two phase shutdown. network_shutdown is called after
        gracetime (see Session.shutdown()).
        """
        # Called by any thread, assume sessionlock is held
        print("spm: early_shutdown", file=sys.stderr)
        try:
            self.sesslock.acquire()
            self.done = True

            for sp in self.sps:
                try:
                    sp.early_shutdown()
                except:
                    print_exc()
        finally:
            self.sesslock.release()

    def network_shutdown(self):
        """ Gracetime expired, kill procs """
        # Called by network thread
        print("spm: network_shutdown", file=sys.stderr)
        for sp in self.sps:
            try:
                sp.network_shutdown()
            except:
                print_exc()

    def connection_lost(self, port):
        if self.done:
            return

        self.sesslock.acquire()
        try:
            for sp in self.sps:
                if sp.get_cmdport() == port:
                    print("spm: connection_lost: Restart", sp.get_pid(), file=sys.stderr)
                    sp.start_cmd_connection()
        finally:
            self.sesslock.release()
