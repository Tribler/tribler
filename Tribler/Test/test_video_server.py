# Written by Arno Bakker
# see LICENSE.txt for license information
import os
import time
import socket
import binascii
from traceback import print_exc

from Tribler.Test.test_as_server import TESTS_DATA_DIR, TestAsServer
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig

DEBUG = True


class TestVideoHTTPServer(TestAsServer):

    """
    Class for testing HTTP-based video server.

    Mainly HTTP range queries.
    """

    def setUp(self):
        """ unittest test setup code """
        TestAsServer.setUp(self)
        self.port = self.session.get_videoplayer_port()
        self.sourcefn = os.path.join(TESTS_DATA_DIR, "video.avi")
        self.sourcesize = os.path.getsize(self.sourcefn)

        # wait 5s to allow server to start
        time.sleep(5)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_libtorrent(True)
        self.config.set_videoplayer(True)

    def tearDown(self):
        """ unittest test tear down code """
        TestAsServer.tearDown(self)
        time.sleep(2)

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
        self.tdef = TorrentDef()
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_tracker("http://127.0.0.1:12/announce")
        self.tdef.finalize()

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(os.path.dirname(self.sourcefn))

        download = self.session.start_download(self.tdef, dscfg)
        while not download.handle:
            time.sleep(1)

    def get_std_header(self):
        msg = "GET /%s/0 HTTP/1.1\r\n" % binascii.hexlify(self.tdef.get_infohash())
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
        self._logger.debug("range_test: %s %s %s setset %s", firstbyte, lastbyte, sourcesize, setset)
        self.register_file_stream()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', self.port))

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

        self._logger.debug("Expecting first %s last %s size %s ", expfirstbyte, explastbyte, sourcesize)
        s.send(head)

        # Parse header
        s.settimeout(10.0)
        while True:
            line = self.readline(s)
            if DEBUG:
                self._logger.debug("Got line: %s", repr(line))

            if len(line) == 0:
                if DEBUG:
                    self._logger.debug("server closed conn")
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
                expline = "Content-Range: bytes " + self.create_range_str(
                    expfirstbyte, explastbyte) + "/" + str(sourcesize) + "\r\n"
                self.assertEqual(expline, line)

            elif line.startswith("Content-Type:"):
                self.assertEqual(line, "Content-Type: video/x-msvideo\r\n")

            elif line.startswith("Content-Length:"):
                self.assertEqual(line, "Content-Length: " + str(expsize) + "\r\n")

            elif line.endswith("\r\n") and len(line) == 2:
                # End of header
                break

        data = s.recv(expsize)
        if len(data) == 0:
            if DEBUG:
                self._logger.debug("server closed conn2")
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
                    self._logger.debug(
                        "Timeout, video server didn't respond with requested bytes, possibly bug in Python impl of HTTP")
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
