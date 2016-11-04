import sys
import os
import subprocess
import time
import Queue

from async_file_reader import AsynchronousFileReader


class ShutdownTime():
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

        self._process_name = 'org.tribler.android'


    def run(self):
        # Append timings to output file
        with open(self._output_file, 'a') as data_file:

            # Start reading logcat
            cmd_logcat = self._adb + ' logcat -v time tag long'
            logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

            stdout_queue = Queue.Queue()
            stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
            stdout_reader.start()

            msg_start = 'Process ' + self._process_name + ' '
            msg_end = ' has died'
            msg_end_ = msg_end + '.'

            begin_time = None

            # Read until nothing more to read
            while not stdout_reader.eof():
                #time.sleep(0.1)
                while not stdout_queue.empty():
                    line = stdout_queue.get().strip()

                    if ': ' not in line: 
                        break

                    device_date, device_time, log = line.split(' ', 2)
                    tag, msg = log.split(': ', 1)

                    if tag.startswith('V/MainActivity') and 'onNewIntent: android.intent.action.ACTION_SHUTDOWN' in msg:
                        begin_time = time.time()
                        break

                    if tag.startswith('I/ActivityManager') and msg.startswith(msg_start) and (msg.endswith(msg_end) or msg.endswith(msg_end_)):
                        # Output
                        elapsed_time = time.time() - begin_time
                        str_time = str(elapsed_time) + "\n"

                        data_file.write(str_time)

                        logcat.kill()
                        exit()



if __name__ == '__main__':
    ShutdownTime(sys.argv, os.getenv('ADB', 'adb')).run()


