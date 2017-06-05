import os
from multiprocessing import Process

from Tribler.Core.Modules.process_checker import ProcessChecker, LOCK_FILE_NAME
from Tribler.Test.test_as_server import AbstractServer


def process_func():
    while True:
        pass


class TestProcessChecker(AbstractServer):

    def tearDown(self, annotate=True):
        super(TestProcessChecker, self).tearDown(annotate=annotate)
        if self.process:
            self.process.terminate()

    def setUp(self, annotate=True):
        super(TestProcessChecker, self).setUp(annotate=annotate)
        self.process = None
        self.state_dir = self.getStateDir()

    def create_lock_file_with_pid(self, pid):
        with open(os.path.join(self.state_dir, LOCK_FILE_NAME), 'wb') as lock_file:
            lock_file.write(str(pid))

    def test_no_lock_file(self):
        """
        Testing whether the process checker returns false when there is no lock file
        """
        process_checker = ProcessChecker()
        self.assertTrue(os.path.exists(os.path.join(self.state_dir, LOCK_FILE_NAME)))
        self.assertFalse(process_checker.already_running)

    def test_invalid_pid_in_lock_file(self):
        """
        Test whether a new lock file is created when an invalid pid is written inside the current lock file
        """
        with open(os.path.join(self.state_dir, LOCK_FILE_NAME), 'wb') as lock_file:
            lock_file.write("Hello world")

        process_checker = ProcessChecker()
        self.assertGreater(int(process_checker.get_pid_from_lock_file()), 0)

    def test_own_pid_in_lock_file(self):
        """
        Testing whether the process checker returns false when it finds its own pid in the lock file
        """
        self.create_lock_file_with_pid(os.getpid())
        process_checker = ProcessChecker()
        self.assertFalse(process_checker.already_running)

    def test_other_instance_running(self):
        """
        Testing whether the process checker returns true when another process is running
        """
        self.process = Process(target=process_func)
        self.process.start()

        self.create_lock_file_with_pid(self.process.pid)
        process_checker = ProcessChecker()
        self.assertTrue(process_checker.is_pid_running(self.process.pid))
        self.assertTrue(process_checker.already_running)

    def test_dead_pid_in_lock_file(self):
        """
        Testing whether the process checker returns false when there is a dead pid in the lock file
        """
        dead_pid = 134824733
        self.create_lock_file_with_pid(dead_pid)
        process_checker = ProcessChecker()
        self.assertFalse(process_checker.is_pid_running(dead_pid))
        self.assertFalse(process_checker.already_running)
