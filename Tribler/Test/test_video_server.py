# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest

import os
import sys
import time
import socket
from traceback import print_exc

from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Test.test_as_server import BASE_DIR
import random

DEBUG = False

class TestVideoHTTPServer(unittest.TestCase):
    """ 
    Class for testing HTTP-based video server.
    
    Mainly HTTP range queries.
    """

    def setUp(self):
        """ unittest test setup code """
        self.port = random.randint(10000, 60000)
        self.serv = VideoHTTPServer.getInstance(self.port)
        self.serv.background_serve()
        self.serv.register(self.videoservthread_error_callback, self.videoservthread_set_status_callback)

        self.sourcefn = os.path.join(BASE_DIR, "API", "file.wmv")  # 82KB or 82948 bytes
        self.sourcesize = os.path.getsize(self.sourcefn)
        
        #wait 5s to allow server to start
        time.sleep(5)

    def tearDown(self):
        """ unittest test tear down code """
        self.serv.shutdown()
        VideoHTTPServer.delInstance()

        time.sleep(2)

    def videoservthread_error_callback(self, e, url):
        """ Called by HTTP serving thread """
        if DEBUG:
            print >> sys.stderr, "test: ERROR", e, url
        self.assert_(False)

    def videoservthread_set_status_callback(self, status):
        """ Called by HTTP serving thread """
        if DEBUG:
            print >> sys.stderr, "test: STATUS", status

    #
    # Tests
    #
    def test_specific_range(self):
        self.range_check(115, 214, self.sourcesize)

    def test_last_100(self):        
        self.range_check(self.sourcesize - 100, None, self.sourcesize)
    
    def test_first_100(self):
        self.range_check(None, 100, self.sourcesize)
    
    def test_combined(self):
        self.range_check(115, 214, self.sourcesize, setset=True)

    #
    # Internal
    #
    def register_file_stream(self):
        stream = open(self.sourcefn, "rb")

        streaminfo = { 'mimetype': 'video/x-ms-wmv', 'stream': stream, 'length': self.sourcesize }

        self.serv.set_inputstream(streaminfo, "/stream")

    def get_std_header(self):
        msg = "GET /stream HTTP/1.1\r\n"
        msg += "Host: 127.0.0.1:" + str(self.port) + "\r\n"
        return msg

    def create_range_str(self, firstbyte, lastbyte):
        head = ""
        if firstbyte is not None:
            head += str(firstbyte)
        head += "-"
        if lastbyte is not None:
            head += str(lastbyte)

        return head

    def range_check(self, firstbyte, lastbyte, sourcesize, setset=False):
        if DEBUG:
            print >> sys.stderr, "test: range_test:", firstbyte, lastbyte, sourcesize, "setset", setset
        self.register_file_stream()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for i in range(5): #attempt to connect 5 times, sleep for 5 seconds in between tries
            try:
                s.connect(('127.0.0.1', self.port))
                break
            except:
                if i < 4:
                    time.sleep(5)
                else:
                    raise

        head = self.get_std_header()

        head += "Range: bytes="
        head += self.create_range_str(firstbyte, lastbyte)
        if setset:
            # Make into set of byte ranges, VideoHTTPServer should refuse.
            head += ",0-99"
        head += "\r\n"

        head += "Connection: close\r\n"

        head += "\r\n"

        if firstbyte is not None and lastbyte is None:
            # 100-
            expfirstbyte = firstbyte
            explastbyte = self.sourcesize - 1
        elif firstbyte is None and lastbyte is not None:
            # -100
            expfirstbyte = self.sourcesize - lastbyte
            explastbyte = self.sourcesize - 1
        else:
            expfirstbyte = firstbyte
            explastbyte = lastbyte

        # the amount of bytes actually requested. (Content-length)
        expsize = explastbyte - expfirstbyte + 1

        if DEBUG:
            print >> sys.stderr, "test: Expecting first", expfirstbyte, "last", explastbyte, "size", sourcesize
        s.send(head)

        # Parse header
        s.settimeout(10.0)
        while True:
            line = self.readline(s)
            if DEBUG:
                print >> sys.stderr, "test: Got line", `line`

            if len(line) == 0:
                if DEBUG:
                    print >> sys.stderr, "test: server closed conn"
                self.assert_(False)
                return

            if line.startswith("HTTP"):
                if not setset:
                    # Python returns "HTTP/1.0 206 Partial Content\r\n" HTTP 1.0???
                    self.assert_(line.startswith("HTTP/1."))
                    self.assert_(line.find("206") != -1)  # Partial content
                else:
                    self.assert_(line.startswith("HTTP/1."))
                    self.assert_(line.find("416") != -1)  # Requested Range Not Satisfiable
                    return

            elif line.startswith("Content-Range:"):
                expline = "Content-Range: bytes " + self.create_range_str(expfirstbyte, explastbyte) + "/" + str(sourcesize) + "\r\n"
                self.assertEqual(expline, line)

            elif line.startswith("Content-Type:"):
                self.assertEqual(line, "Content-Type: video/x-ms-wmv\r\n")

            elif line.startswith("Content-Length:"):
                self.assertEqual(line, "Content-Length: " + str(expsize) + "\r\n")

            elif line.endswith("\r\n") and len(line) == 2:
                # End of header
                break

        data = s.recv(expsize)
        if len(data) == 0:
            if DEBUG:
                print >> sys.stderr, "test: server closed conn2"
            self.assert_(False)
            return
        else:
            f = open(self.sourcefn, "rb")
            if firstbyte is not None:
                f.seek(firstbyte)
            else:
                f.seek(lastbyte, os.SEEK_END)

            expdata = f.read(expsize)
            f.close()
            self.assert_(data, expdata)

            try:
                # Read body, reading more should EOF (we disabled persist conn)
                data = s.recv(10240)
                self.assert_(len(data) == 0)

            except socket.timeout:
                if DEBUG:
                    print >> sys.stderr, "test: Timeout, video server didn't respond with requested bytes, possibly bug in Python impl of HTTP"
                    print_exc()

    def readline(self, s):
        line = ''
        while True:
            data = s.recv(1)
            if len(data) == 0:
                return line
            else:
                line = line + data
            if data == '\n' and len(line) >= 2 and line[-2:] == '\r\n':
                return line