from __future__ import absolute_import

import os
from multiprocessing import Process, Value
from time import sleep

from Tribler.Core.Modules.process_checker import LOCK_FILE_NAME, ProcessChecker
from Tribler.Test.test_as_server import AbstractServer


def process_dummy_function(stop_flag):
    while stop_flag.value == 0:
        sleep(0.01)
        pass


class TestProcessChecker(AbstractServer):
    """A test class for the ProcessChecker which checks if the Tribler Core is already running."""
    def tearDown(self):
        super(TestProcessChecker, self).tearDown()
        if self.process:
            self.stop_flag.value = 1
            self.process.join()

    def setUp(self):
        super(TestProcessChecker, self).setUp()
        self.process = None
        self.stop_flag = Value('b', 0)
        self.state_dir = self.getStateDir()

    def create_lock_file_with_pid(self, pid):
        with open(os.path.join(self.state_dir, LOCK_FILE_NAME), 'w') as lock_file:
            lock_file.write(str(pid))

    def test_create_lock_file(self):
        """
        Testing if lock file is created
        """
        process_checker = ProcessChecker(state_directory=self.state_dir)
        process_checker.create_lock_file()
        self.assertTrue(os.path.exists(os.path.join(self.state_dir, LOCK_FILE_NAME)))

    def test_remove_lock_file(self):
        """
        Testing if lock file is removed on calling remove_lock_file()
        """
        process_checker = ProcessChecker(state_directory=self.state_dir)
        process_checker.create_lock_file()
        process_checker.remove_lock_file()
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, LOCK_FILE_NAME)))

    def test_no_lock_file(self):
        """
        Testing whether the process checker returns false when there is no lock file
        """
        process_checker = ProcessChecker(state_directory=self.state_dir)
        # Process checker does not create a lock file itself now, Core manager will call to create it.
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, LOCK_FILE_NAME)))
        self.assertFalse(process_checker.already_running)

    def test_invalid_pid_in_lock_file(self):
        """
        Testing pid should be -1 if the lock file is invalid
        """
        with open(os.path.join(self.state_dir, LOCK_FILE_NAME), 'wb') as lock_file:
            lock_file.write(b"Hello world")

        process_checker = ProcessChecker(state_directory=self.state_dir)
        self.assertEqual(process_checker.get_pid_from_lock_file(), -1)

    def test_own_pid_in_lock_file(self):
        """
        Testing whether the process checker returns True when it finds its own pid in the lock file
        """
        self.create_lock_file_with_pid(os.getpid())
        process_checker = ProcessChecker(state_directory=self.state_dir)
        self.assertTrue(process_checker.already_running)

    def test_other_instance_running(self):
        """Testing whether the process checker returns true when another process is running."""
        self.process = Process(target=process_dummy_function, args=(self.stop_flag,))
        self.process.start()

        self.create_lock_file_with_pid(self.process.pid)
        process_checker = ProcessChecker(state_directory=self.state_dir)
        self.assertTrue(process_checker.is_pid_running(self.process.pid))
        self.assertTrue(process_checker.already_running)

    def test_dead_pid_in_lock_file(self):
        """Testing whether the process checker returns false when there is a dead pid in the lock file."""
        dead_pid = 134824733
        self.create_lock_file_with_pid(dead_pid)
        process_checker = ProcessChecker(state_directory=self.state_dir)
        self.assertFalse(process_checker.is_pid_running(dead_pid))
        self.assertFalse(process_checker.already_running)
