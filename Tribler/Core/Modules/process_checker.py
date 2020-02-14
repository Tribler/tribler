from __future__ import absolute_import

import os

import psutil

from six import text_type

from Tribler.Core.Config.tribler_config import TriblerConfig


LOCK_FILE_NAME = 'triblerd.lock'


class ProcessChecker(object):
    """
    This class contains code to check whether a Tribler process is already running.
    """
    def __init__(self, state_directory=None):
        self.state_directory = state_directory or TriblerConfig().get_state_dir()
        self.lock_file_path = os.path.join(self.state_directory, LOCK_FILE_NAME)

        if os.path.exists(self.lock_file_path):
            # Check for stale lock file (created before the os was last restarted).
            # The stale file might contain the pid of another running process and
            # not the Tribler itself. To find out we can simply check if the lock file
            # was last modified before os reboot.
            # lock_file_modification_time < system boot time
            file_pid = self.get_pid_from_lock_file()
            if file_pid < 1 or os.path.getmtime(self.lock_file_path) < psutil.boot_time():
                self.remove_lock_file()

        self.already_running = self.is_process_running()

    def is_process_running(self):
        if os.path.exists(self.lock_file_path):
            file_pid = self.get_pid_from_lock_file()

            if file_pid == os.getpid() or ProcessChecker.is_pid_running(file_pid):
                return True
        return False

    @staticmethod
    def is_pid_running(pid):
        return psutil.pid_exists(pid)

    def create_lock_file(self):
        """
        Create the lock file and write the PID in it. We also create the directory structure since the ProcessChecker
        might be called before the .Tribler directory has been created.
        """
        if not os.path.exists(self.state_directory):
            os.makedirs(self.state_directory)

        # Remove the previous lock file
        self.remove_lock_file()

        with open(self.lock_file_path, 'wb') as lock_file:
            lock_file.write(text_type(os.getpid()).encode())

    def remove_lock_file(self):
        """
        Remove the lock file if it exists.
        """
        if os.path.exists(self.lock_file_path):
            os.unlink(self.lock_file_path)

    def get_pid_from_lock_file(self):
        """
        Returns the PID from the lock file.
        """
        if not os.path.exists(self.lock_file_path):
            return -1
        with open(self.lock_file_path, 'rb') as lock_file:
            try:
                return int(lock_file.read())
            except ValueError:
                return -1
