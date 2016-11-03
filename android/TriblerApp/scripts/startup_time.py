import sys
import os
import subprocess
import time
import Queue

from async_file_reader import AsynchronousFileReader


class StartupTime():
    '''
    Helper class for timing the startup.
    '''

    def __init__(self, argv, adb):
        self._adb = adb
        nr_args = len(argv)

        if nr_args > 1:
            self._output_file = argv[1]
            print 'Output file:', self._output_file
        else:
            print 'Error: No output file specified!'
            exit()


    def run(self):
        # Append timings to output file
        with open(self._output_file, 'a') as data_file:

            # Start reading logcat
            cmd_logcat = self._adb + ' logcat -v time tag long'
            logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

            stdout_queue = Queue.Queue()
            stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
            stdout_reader.start()

            begin_time = None

            # Read until nothing more to read
            while not stdout_reader.eof():
                #time.sleep(1)
                while not stdout_queue.empty():
                    line = stdout_queue.get().strip()

                    if ': ' not in line: 
                        break

                    device_date, device_time, log = line.split(' ', 2)
                    tag, msg = log.split(': ', 1)

                    if tag.startswith('I/ActivityManager') and 'org.tribler.android/.MainActivity' in msg:
                        begin_time = time.time()
                        break

                    if tag.startswith('V/onEvent') and 'TriblerStartedEvent;' in msg:
                        # Output
                        elapsed_time = time.time() - begin_time
                        str_time = str(elapsed_time) + "\n"

                        data_file.write(str_time)

                        logcat.kill()
                        exit()



if __name__ == '__main__':
    StartupTime(sys.argv, os.getenv('ADB', 'adb')).run()


