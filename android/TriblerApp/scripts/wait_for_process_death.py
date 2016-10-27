import sys
import os
import Queue
import subprocess
import threading
import time


class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()



class WaitForProcessDeath():
    '''
    Helper class to wait for a process to die.
    '''

    def __init__(self, argv, adb):
        nr_args = len(argv)

        if nr_args > 1:
            self._process_name = argv[1]
            print 'Service name:', self._process_name
        else:
            print 'Error: No process name specified!'
            exit()

        self._adb = adb

        if nr_args > 2:
            device = argv[2]
            self._adb += ' -s ' + device


    def run(self):
        # Clear logcat
        cmd_clear = self._adb + ' logcat -c'
        print cmd_clear
        clear = subprocess.Popen(cmd_clear.split())
        clear.wait()

        # Start reading logcat
        cmd_logcat = self._adb + ' logcat -v time tag long'
        logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

        stdout_queue = Queue.Queue()
        stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
        stdout_reader.start()

        msg_start = 'Process ' + self._process_name + ' '
        msg_end = ' has died'

        # Read until nothing more to read
        while not stdout_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get().strip()

                if line.startswith('-'):
                    break;

                date, time, log = line.split(' ', 2)
                tag, msg = log.split(': ', 1)

                if tag.startswith('I/ActivityManager') and msg.startswith(msg_start) and msg.endswith(msg_end):
                    logcat.kill()
                    exit()



if __name__ == '__main__':
    WaitForProcessDeath(sys.argv, os.getenv('ADB', 'adb')).run()


