import sys
import os
import subprocess
import time
import Queue

from async_file_reader import AsynchronousFileReader


class AdbPull():
    '''
    Helper class to pull a file from the private files dir of Tribler on Android.
    '''

    def __init__(self, argv, adb):
        self._adb = adb
        nr_args = len(argv)

        if nr_args > 1:
            self._input_file = argv[1]
            print ' Input file:', self._input_file
        else:
            print 'Error: No input file specified!'
            exit()

        if self._input_file.endswith('/'):
            print 'Error: Cannot copy directories!'
            exit()

        file_name = os.path.basename(self._input_file)

        if nr_args > 2:
            self._output_file = os.path.realpath(argv[2])

            if os.path.isdir(self._output_file):
                self._output_file = os.path.join(self._output_file, file_name)
        else:
            self._output_file = file_name

        print 'Output file:', self._output_file

        if os.path.exists(self._output_file):
            print 'Warning: Overwriting output file!'


    def run(self):
        # Start reading logcat
        cmd_logcat = self._adb + ' logcat -v time tag long'
        logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

        stdout_queue = Queue.Queue()
        stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
        stdout_reader.start()

        # Start copy file
        cmd_copy = self._adb + ' shell am start -n org.tribler.android/.CopyFilesActivity --es "' + self._input_file + '" ""'
        print cmd_copy
        copy = subprocess.Popen(cmd_copy.split())

        temp_name = None
        started = False

        # Read until nothing more to read
        while not stdout_reader.eof():
            time.sleep(1)
            while not stdout_queue.empty():
                line = stdout_queue.get().strip()

                if ': ' not in line: 
                    break

                device_date, device_time, log = line.split(' ', 2)
                tag, path = log.split(': ', 1)

                if tag.startswith('E/CopyFile'):
                    print log
                    break

                if tag.startswith('I/CopyFileStartIn'):
                    if path.endswith(self._input_file):
                        started = True
                        print log

                    break

                if tag.startswith('I/CopyFileStartOut'):
                    if started:
                        temp_name = path
                        print log

                    break

                if tag.startswith('I/CopyFileDoneIn'):
                    if started:
                        print log

                    break

                if tag.startswith('I/CopyFileDoneOut'):
                    if not started or path != temp_name:
                        break

                    print log

                    # Pull file
                    cmd_pull = self._adb + ' pull ' + path + ' ' + self._output_file
                    print cmd_pull
                    pull = subprocess.Popen(cmd_pull.split())
                    pull.wait()

                    # Cleanup
                    cmd_remove = self._adb + ' shell rm "' + path + '"'
                    print cmd_remove
                    remove = subprocess.Popen(cmd_remove.split())
                    remove.wait()

                    print 'Finished!'
                    logcat.kill()
                    exit()



if __name__ == '__main__':
    AdbPull(sys.argv, os.getenv('ADB', 'adb')).run()


