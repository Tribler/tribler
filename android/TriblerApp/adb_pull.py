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
            print 'No input file specified!'
            exit()

        file_name = os.path.basename(self._input_file)
        if not file_name:
            print 'Cannot copy directories!'
            exit()

        self._temp_file = str(time.time()) + file_name
        print '  Temp file:', self._temp_file

        if nr_args > 2:
            self._output_file = argv[2]
        else:
            self._output_file = file_name

        print 'Output file:', self._output_file
        if os.path.exists(self._output_file):
            print 'Output file already exists!'
            exit()

        self._adb = adb

        if nr_args > 3:
            device = argv[3]
            print 'Device:', device
            self_adb += ' -s ' + device


    def run(self):
        # Start reading logcat
        cmd_logcat = self._adb + ' logcat -v time tag long'
        logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

        stdout_queue = Queue.Queue()
        stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
        stdout_reader.start()

        # Start copy file
        cmd_copy = self._adb + ' shell am start -n org.tribler.android/.CopyFilesActivity -e "' + self._input_file + '" "' + self._temp_file + '"'
        print cmd_copy
        copy = subprocess.Popen(cmd_copy.split())

        # Read until nothing more to read
        while not stdout_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get().strip()
                date, time, log = line.split(' ', 2)

                if log.startswith('E/CopyFile'):
                    print log
                    break

                if log.startswith('I/CopyFileStart'):
                    tag, file = log.split(': ', 1)
                    print 'Start copying file:', file
                    break

                if log.startswith('I/CopyFileDone'):
                    tag, file = log.split(': ', 1)
                    print ' Done copying file:', file

                    if not file.endswith(self._temp_file):
                        print '  Skip copied file:', file
                        break

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


