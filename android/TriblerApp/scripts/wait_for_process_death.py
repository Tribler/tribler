import sys
import os
import subprocess
import time
import Queue

from async_file_reader import AsynchronousFileReader


class WaitForProcessDeath():
    '''
    Helper class to wait for a process to die.
    '''

    def __init__(self, argv, adb):
        self._adb = adb
        nr_args = len(argv)

        if nr_args > 1:
            self._process_name = argv[1]
            print 'Service name:', self._process_name
        else:
            print 'Error: No process name specified!'
            exit()


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
        msg_end_ += '.'

        # Read until nothing more to read
        while not stdout_reader.eof():
            time.sleep(1)
            while not stdout_queue.empty():
                line = stdout_queue.get().strip()

                if line.startswith('-'):
                    break

                device_date, device_time, log = line.split(' ', 2)
                tag, msg = log.split(': ', 1)

                if tag.startswith('I/ActivityManager') and msg.startswith(msg_start) and (msg.endswith(msg_end) or msg.endswith(msg_end_)):
                    logcat.kill()
                    exit()



if __name__ == '__main__':
    WaitForProcessDeath(sys.argv, os.getenv('ADB', 'adb')).run()


