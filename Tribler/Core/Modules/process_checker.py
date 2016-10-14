import os
from Tribler.Core.Config.tribler_config import TriblerConfig


LOCK_FILE_NAME = 'triblerd.lock'


class ProcessChecker(object):
    """
    This class contains code to check whether a Tribler process is already running.
    """

    def __init__(self, statedir=None):
        """
        Check whether a lock file exists in the Tribler directory. If not, create the file. If it exists,
        check the PID that is written inside the lock file.
        """
        self.already_running = False

        if statedir:
            self.statedir = statedir
        else:
            self.statedir = TriblerConfig().get_state_dir()

        self.lock_file_path = os.path.join(self.statedir, LOCK_FILE_NAME)

        if os.path.exists(self.lock_file_path):
            file_pid = self.get_pid_from_lock_file()
            if file_pid == str(os.getpid()):
                # Ignore when we find our own PID inside the lock file
                self.already_running = False
            elif file_pid != os.getpid() and not ProcessChecker.is_pid_running(int(file_pid)):
                # The process ID written inside the lock file is old, just remove the lock file and create a new one.
                self.remove_lock_file()
                self.create_lock_file()
            else:
                self.already_running = True
        else:
            self.create_lock_file()

    @staticmethod
    def is_pid_running(pid):
        """
        Check whether a given process ID is currently running. We do this by sending signal 0 to the process
        which does not has any effect on the running process.
        Source: http://stackoverflow.com/questions/7647167/check-if-a-process-is-running-in-python-in-linux-unix
        """
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    def create_lock_file(self):
        """
        Create the lock file and write the PID in it. We also create the directory structure since the ProcessChecker
        might be called before the .Tribler directory has been created.
        """
        if not os.path.exists(self.statedir):
            os.makedirs(self.statedir)

        with open(self.lock_file_path, 'wb') as lock_file:
            lock_file.write(str(os.getpid()))

    def remove_lock_file(self):
        """
        Remove the lock file.
        """
        os.unlink(self.lock_file_path)

    def get_pid_from_lock_file(self):
        """
        Returns the PID from the lock file.
        """
        with open(self.lock_file_path, 'rb') as lock_file:
            return lock_file.read()
