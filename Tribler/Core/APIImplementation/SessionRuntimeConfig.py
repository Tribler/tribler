# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information

from __future__ import with_statement
import sys
from traceback import print_exc

from Tribler.Core.exceptions import *
from Tribler.Core.SessionConfig import SessionConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# SessionRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Session which is a subclass of SessionRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101

class SessionRuntimeConfig(SessionConfigInterface):
    """
    Implements the Tribler.Core.API.SessionConfigInterface

    Use these to change the session config at runtime.
    """
    def set_state_dir(self, statedir):
        raise OperationNotPossibleAtRuntimeException()

    def get_state_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_state_dir(self)
        finally:
            self.sesslock.release()

    def set_install_dir(self, statedir):
        raise OperationNotPossibleAtRuntimeException()

    def get_install_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_install_dir(self)
        finally:
            self.sesslock.release()

    def set_permid_keypair_filename(self, keypair):
        raise OperationNotPossibleAtRuntimeException()

    def get_permid_keypair_filename(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_permid_keypair_filename(self)
        finally:
            self.sesslock.release()

    def set_listen_port(self, port):
        raise OperationNotPossibleAtRuntimeException()

    def get_listen_port(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_listen_port(self)
        finally:
            self.sesslock.release()

    def get_video_analyser_path(self):
        # To protect self.sessconfig
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_video_analyser_path(self)
        finally:
            self.sesslock.release()

    def set_megacache(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_megacache(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_megacache(self)
        finally:
            self.sesslock.release()

    def set_torrent_collecting(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_collecting(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting(self)
        finally:
            self.sesslock.release()

    def set_torrent_collecting_dir(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_collecting_dir(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting_dir(self)
        finally:
            self.sesslock.release()

    def set_torrent_collecting_max_torrents(self, value):
        self.sesslock.acquire()
        try:
            SessionConfigInterface.set_torrent_collecting_max_torrents(self, value)

            from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
            rth = RemoteTorrentHandler.getInstance()
            rth.set_max_num_torrents(value)
        finally:
            self.sesslock.release()

    def get_torrent_collecting_max_torrents(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_collecting_max_torrents(self)
        finally:
            self.sesslock.release()

    def set_torrent_checking(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_checking(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_checking(self)
        finally:
            self.sesslock.release()

    def set_torrent_checking_period(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_torrent_checking_period(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_torrent_checking_period(self)
        finally:
            self.sesslock.release()

    def set_mainline_dht(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_mainline_dht(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_mainline_dht(self)
        finally:
            self.sesslock.release()

    def set_nickname(self, value):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.set_nickname(self, value)
        finally:
            self.sesslock.release()

    def get_nickname(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_nickname(self)
        finally:
            self.sesslock.release()

    def set_mugshot(self, value, mime='image/jpeg'):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.set_mugshot(self, value, mime)
        finally:
            self.sesslock.release()

    def get_mugshot(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_mugshot(self)
        finally:
            self.sesslock.release()

    def set_peer_icon_path(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_peer_icon_path(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_peer_icon_path(self)
        finally:
            self.sesslock.release()


    #
    # Local Peer Discovery using IP Multicast
    #
    def set_multicast_local_peer_discovery(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_multicast_local_peer_discovery(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_multicast_local_peer_discovery(self)
        finally:
            self.sesslock.release()

    #
    # SWIFTPROC
    #
    def set_swift_proc(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_proc(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_proc(self)
        finally:
            self.sesslock.release()


    def set_swift_path(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_path(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_path(self)
        finally:
            self.sesslock.release()


    def set_swift_cmd_listen_port(self, port):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_cmd_listen_port(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_cmd_listen_port(self)
        finally:
            self.sesslock.release()

    def set_swift_downloads_per_process(self, value):
        raise OperationNotPossibleAtRuntimeException()

    def get_swift_downloads_per_process(self):
        self.sesslock.acquire()
        try:
            return SessionConfigInterface.get_swift_downloads_per_process(self)
        finally:
            self.sesslock.release()
