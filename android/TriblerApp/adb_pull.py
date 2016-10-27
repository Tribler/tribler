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



class AdbPull():
    '''
    Helper class to pull a file from the private files dir of Tribler on Android.
    '''

    def __init__(self, argv, adb):
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

        self._adb = adb

        if nr_args > 3:
            device = argv[3]
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

        # Start copy file
        cmd_copy = self._adb + ' shell am start -n org.tribler.android/.CopyFilesActivity -e "' + self._input_file + '" ""'
        print cmd_copy
        copy = subprocess.Popen(cmd_copy.split())

        temp_name = None
        started = False

        # Read until nothing more to read
        while not stdout_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get().strip()

                if line.startswith('-'):
                    break;

                date, time, log = line.split(' ', 2)
                tag, file = log.split(': ', 1)

                if tag.startswith('E/CopyFile'):
                    print log
                    break

                if tag.startswith('I/CopyFileStartIn'):
                    if file.endswith(self._input_file):
                        started = True
                        print log

                    break

                if tag.startswith('I/CopyFileStartOut'):
                    if started:
                        temp_name = file
                        print log

                    break

                if tag.startswith('I/CopyFileDoneIn'):
                    if started:
                        print log

                    break

                if tag.startswith('I/CopyFileDoneOut'):
                    if not started or file != temp_name:
                        break

                    print log

                    # Pull file
                    cmd_pull = self._adb + ' pull ' + file + ' ' + self._output_file
                    print cmd_pull
                    pull = subprocess.Popen(cmd_pull.split())
                    pull.wait()

                    # Cleanup
                    cmd_remove = self._adb + ' shell rm "' + file + '"'
                    print cmd_remove
                    remove = subprocess.Popen(cmd_remove.split())
                    remove.wait()

                    print 'Finished!'
                    logcat.kill()
                    exit()



if __name__ == '__main__':
    AdbPull(sys.argv, os.getenv('ADB', 'adb')).run()


