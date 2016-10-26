#!/usr/bin/python

import sys
import getopt
import os
import Queue
import subprocess
import threading


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
    Helper class to pull a file from the private app dir of tribler on Android.
    '''

    def __init__(self, argv):
        self.inputfile = ''
        self.outputfile = ''
        try:
            opts, args = getopt.getopt(argv, 'hi:o:', ['ifile=', 'ofile='])
        except getopt.GetoptError:
            print 'adb_pull.py -i <inputfile> -o <outputfile>'
            sys.exit(2)

        for opt, arg in opts:
            if opt == '-h':
                print 'adb_pull.py -i <inputfile> -o <outputfile>'
                sys.exit()
            elif opt in ('-i', '--ifile'):
                self.inputfile = arg
            elif opt in ('-o', '--ofile'):
                self.outputfile = arg

        print 'Input file is: ', self.inputfile
        print 'Output file is: ', self.outputfile


    def run(self, adb, tmp_dir):
        # Start copy file to temp dir
        cmd_mkdir= adb + ' shell mkdir "' + tmp_dir + '"'
        subprocess.Popen(cmd_mkdir.split())

        # Start reading logcat
        cmd_logcat = adb + ' logcat -v tag long'
        logcat = subprocess.Popen(cmd_logcat.split(), stdout=subprocess.PIPE)

        stdout_queue = Queue.Queue()
        stdout_reader = AsynchronousFileReader(logcat.stdout, stdout_queue)
        stdout_reader.start()

        # Start copy file to temp dir
        cmd_copy = adb + ' shell am start -n org.tribler.android/.CopyFilesActivity -e "' + self.inputfile + '" "' + tmp_dir + '"'
        subprocess.Popen(cmd_copy.split())

        tag = 'I/CopyFileDone'
        tag_error = 'E/CopyFile'

        # Read until nothing more to read
        while not stdout_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get()

                if (line.startswith(tag_error)):
                    print line.rstrip('\n')

                if line.startswith(tag):
                    # Pull file from temp_dir onCopyFileDone
                    file = line.split(tag, 1)
                    print file
                    pull = subprocess.Popen([adb, 'pull', file, self.outputfile])
                    pull.wait()
                    return


    def cleanup(self, adb, tmp_dir):
        # Delete temp dir
        cmd_rm_rf = adb + ' shell rm -rf "' + tmp_dir + '"'
        subprocess.Popen(cmd_rm_rf.split())



if __name__ == '__main__':
    adb_pull = AdbPull(sys.argv[1:])

    adb = os.getenv('ADB', 'adb')
    temp_dir = '/sdcard/.Tribler'

    adb_pull.cleanup(adb, temp_dir)
    adb_pull.run(adb, temp_dir)
    adb_pull.cleanup(adb, temp_dir)


