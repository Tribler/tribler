# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information
#
import os
import socket
import string
import logging
import BaseHTTPServer
from SocketServer import ThreadingMixIn
from threading import RLock, Thread, currentThread
from traceback import print_exc

# NOTE: DEBUG is set dynamically depending from DEBUGWEBUI and DEBUGCONTENT
DEBUG = True
DEBUGCONTENT = False
DEBUGWEBUI = False
DEBUGLOCK = False
DEBUGBASESERV = False


def bytestr2int(b):
    if b == "":
        return None
    else:
        return int(b)

class VideoHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer):
# class VideoHTTPServer(BaseHTTPServer.HTTPServer):

    """
    Arno: not using ThreadingMixIn makes it a single-threaded server.

    2009-09-08: Previously single or multi didn't matter because there would
    always just be one request for one HTTP path. Now we started supporting HTTP
    range queries and that results in parallel requests on the same path
    (and thus our stream object). The reason there are parallel requests
    is due to the funky way VLC uses HTTP range queries: It does not request
    begin1-end1, begin2-end2, begin2-end2, but begin1- & begin2- &
    begin3-. That is, it requests almost the whole file everytime, and in
    parallel too, aborting the earlier connections as it proceeds.

    2009-12-05: I now made it Multi-threaded to also handle the NSSA search
    API requests. The concurrency issue on the p2p streams is handled by
    adding a lock per stream.
    """
    __single = None

    def __init__(self, port):
        if VideoHTTPServer.__single:
            raise RuntimeError("HTTPServer is Singleton")
        VideoHTTPServer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.port = port
        BaseHTTPServer.HTTPServer.__init__(self, ("127.0.0.1", self.port), SimpleServer)
        self.daemon_threads = True
        self.allow_reuse_address = True
        # self.request_queue_size = 10

        self.lock = RLock()

        self.urlpath2streaminfo = {}  # Maps URL to streaminfo
        self.mappers = []  # List of PathMappers

        self.errorcallback = None
        self.statuscallback = None
        self.is_shutdown = False

    def getInstance(*args, **kw):
        if VideoHTTPServer.__single is None:
            VideoHTTPServer(*args, **kw)
        return VideoHTTPServer.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        VideoHTTPServer.__single = None
    delInstance = staticmethod(delInstance)

    def background_serve(self):
        name = "VideoHTTPServerThread-1"
        self.thread2 = Thread(target=self.serve_forever, name=name)
        self.thread2.setDaemon(True)
        self.thread2.start()
        # thread.start_new_thread( self.serve_forever, () )

    def register(self, errorcallback, statuscallback):
        self.errorcallback = errorcallback
        self.statuscallback = statuscallback

    def shutdown(self):
        BaseHTTPServer.HTTPServer.shutdown(self)
        self.is_shutdown = True

    def set_inputstream(self, streaminfo, urlpath):
        if DEBUGLOCK:
            self._logger.debug("vs: set_input: lock %s %s", urlpath, currentThread().getName())
        self.lock.acquire()
        streaminfo['lock'] = RLock()
        self.urlpath2streaminfo[urlpath] = streaminfo
        if DEBUGLOCK:
            self._logger.debug("vs: set_input: unlock %s %s", urlpath, currentThread().getName())
        self.lock.release()

    def acquire_inputstream(self, urlpath):

        streaminfo = None
        # First check mappers, without locking, assuming video stream URL paths won't match mappers
        for mapper in self.mappers:
            streaminfo = mapper.get(urlpath)
            # print >>sys.stderr,"videoserv: get_inputstream: Got streaminfo",`streaminfo`,"from",`mapper`
            if streaminfo is not None and (streaminfo['statuscode'] == 200 or streaminfo['statuscode'] == 301):
                return streaminfo

        if DEBUGLOCK:
            self._logger.debug("vs: acq_input: lock %s %s", urlpath, currentThread().getName())
        self.lock.acquire()
        try:
            streaminfo = self.urlpath2streaminfo.get(urlpath, None)
        finally:
            if DEBUGLOCK:
                self._logger.debug("vs: acq_input: unlock %s %s", urlpath, currentThread().getName())
            self.lock.release()

        # Grab lock of video stream, such that other threads cannot read from it. Do outside self.lock
        if streaminfo is not None and 'lock' in streaminfo:
            if DEBUGLOCK:
                self._logger.debug("vs: acq_input: stream: lock %s %s", urlpath, currentThread().getName())
            streaminfo['lock'].acquire()
        return streaminfo

    def release_inputstream(self, urlpath):
        if DEBUGLOCK:
            self._logger.debug("vs: rel_input: lock %s %s", urlpath, currentThread().getName())
        self.lock.acquire()
        try:
            streaminfo = self.urlpath2streaminfo.get(urlpath, None)
        finally:
            if DEBUGLOCK:
                self._logger.debug("vs: rel_input: unlock %s %s", urlpath, currentThread().getName())
            self.lock.release()

        if streaminfo is not None and 'lock' in streaminfo:
            if DEBUGLOCK:
                self._logger.debug("vs: rel_input: stream: unlock %s %s", urlpath, currentThread().getName())
            streaminfo['lock'].release()

    def del_inputstream(self, urlpath):
        if DEBUGLOCK:
            self._logger.debug("vs: del_input: enter %s", urlpath)
        streaminfo = self.acquire_inputstream(urlpath)

        if DEBUGLOCK:
            self._logger.debug("vs: del_input: lock %s %s", urlpath, currentThread().getName())
        self.lock.acquire()
        try:
            del self.urlpath2streaminfo[urlpath]
        finally:
            if DEBUGLOCK:
                self._logger.debug("vs: del_input: unlock %s %s", urlpath, currentThread().getName())
            self.lock.release()

        if streaminfo is not None and 'lock' in streaminfo:
            if DEBUGLOCK:
                self._logger.debug("vs: del_input: stream: unlock %s %s", urlpath, currentThread().getName())
            streaminfo['lock'].release()

    def get_port(self):
        return self.port

    def add_path_mapper(self, mapper):
        """ WARNING: mappers cannot be added dynamically, must be registered before background_serve()
        """
        self.mappers.append(mapper)

    def handle_error(self, request, client_address):
        """ Error inside the BaseHTTPServer that reports errors like:
          File "c:\Python265\lib\socket.py", line 406, in readline
            data = self._sock.recv(self._rbufsize)
          error: [Errno 10053] An established connection was aborted by the software in your host machine

          As this fill the log when VLC uses HTTP range requests in its brutal
          way (send offset, close conn, send offset+10K-, close conn),
          only print when really wanted.
        """
        if DEBUGBASESERV:
            self._logger.debug("VideoHTTPServer: handle_error %s %s", request, client_address)
            print_exc()


class SimpleServer(BaseHTTPServer.BaseHTTPRequestHandler):

    RANGE_REQUESTS_ENABLED = True

    def __init__(self, request, client_address, server):
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request, client_address, server)

        self._logger = logging.getLogger(self.__class__.__name__)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        """
        Handle HTTP GET request. See remark about VLC's use of HTTP GET RANGE
        requests above.

        Called by a separate thread for each request.
        """
        if self.server.is_shutdown:
            self.send_error(410)
            self.finish()
            return

        global DEBUG
        try:
            if self.path.startswith("/webUI"):
                DEBUG = DEBUGWEBUI
            else:
                DEBUG = DEBUGCONTENT

            if DEBUG:
                self._logger.debug("videoserv: do_GET: Got request %s %s %s", self.path, self.headers.getheader('range'), currentThread().getName())
                # print >>sys.stderr,"videoserv: do_GET: Range",self.headers.getrawheader('Range'),currentThread().getName()

            # 1. Get streaminfo for the data we should return in response
            nbytes2send = None
            nbyteswritten = 0
            try:
                streaminfo = self.server.acquire_inputstream(self.path)
            except:
                streaminfo = None

            if DEBUG:
                self._logger.debug("videoserv: do_GET: Got streaminfo %s %s %s", self.path, self.headers.getheader('range'), currentThread().getName())

            # Ric: modified to create a persistent connection in case it's requested (HTML5)
            if self.request_version == 'HTTP/1.1':
                self.protocol_version = 'HTTP/1.1'

            data = ""
            try:
                if streaminfo is None or ('statuscode' in streaminfo and streaminfo['statuscode'] != 200):
                    # 2. Send error response
                    if streaminfo is None:
                        streaminfo = {'statuscode': 500, 'statusmsg': "Internal Server Error, couldn't find resource"}
                    if DEBUG:
                        self._logger.debug("videoserv: do_GET: Cannot serve request %s %s", streaminfo['statuscode'], currentThread().getName())

                    self.send_response(streaminfo['statuscode'])
                    if streaminfo['statuscode'] == 301:
                        self.send_header("Location", streaminfo['statusmsg'])
                        self.end_headers()
                    else:
                        self.send_header("Content-Type", "text/plain")
                        self.send_header("Content-Length", len(streaminfo['statusmsg']))
                        self.end_headers()
                        self.wfile.write(streaminfo['statusmsg'])
                    return
                else:
                    # 2. Prepare to send stream
                    mimetype = streaminfo['mimetype']
                    stream = streaminfo['stream']
                    length = streaminfo['length']
                    if 'blocksize' in streaminfo:
                        blocksize = streaminfo['blocksize']
                    else:
                        blocksize = 65536

                # mimetype = 'application/x-mms-framed'
                # mimetype = 'video/H264'
                if DEBUG:
                    self._logger.debug("videoserv: do_GET: MIME type is %s length %s blocksize %s %s", mimetype, length, blocksize, currentThread().getName())

                # 3. Support for HTTP range queries:
                # http://tools.ietf.org/html/rfc2616#section-14.35
                firstbyte = 0
                if length is not None:
                    lastbyte = length - 1
                else:
                    lastbyte = None  # to avoid print error below

                range = self.headers.getheader('range')
                if self.RANGE_REQUESTS_ENABLED and length and range:
                    # Handle RANGE query
                    bad = False
                    type, seek = string.split(range, '=')
                    if seek.find(",") != -1:
                        # - Range header contains set, not supported at the moment
                        bad = True
                    else:
                        firstbytestr, lastbytestr = string.split(seek, '-')
                        firstbyte = bytestr2int(firstbytestr)
                        lastbyte = bytestr2int(lastbytestr)

                        if length is None:
                            # - No length (live)
                            bad = True
                        elif firstbyte is None and lastbyte is None:
                            # - Invalid input
                            bad = True
                        elif firstbyte >= length:
                            bad = True
                        elif lastbyte >= length:
                            if firstbyte is None:
                                """ If the entity is shorter than the specified
                                suffix-length, the entire entity-body is used.
                                """
                                lastbyte = length - 1
                            else:
                                bad = True

                    if bad:
                        # Send 416 - Requested Range not satisfiable and exit
                        self.send_response(416)
                        if length is None:
                            crheader = "bytes */*"
                        else:
                            crheader = "bytes */" + str(length)
                        self.send_header("Content-Range", crheader)
                        self.end_headers()

                        return

                    if firstbyte is not None and lastbyte is None:
                        # "100-" : byte 100 and further
                        nbytes2send = length - firstbyte
                        lastbyte = length - 1
                    elif firstbyte is None and lastbyte is not None:
                        # "-100" = last 100 bytes
                        nbytes2send = lastbyte
                        firstbyte = length - lastbyte
                        lastbyte = length - 1

                    else:
                        nbytes2send = lastbyte + 1 - firstbyte

                    # Arno, 2010-01-08: Fixed bug, now return /length
                    crheader = "bytes " + str(firstbyte) + "-" + str(lastbyte) + "/" + str(length)

                    self.send_response(206)
                    self.send_header("Content-Range", crheader)
                else:
                    # Normal GET request
                    nbytes2send = length
                    self.send_response(200)


                if DEBUG:
                    self._logger.debug("videoserv: do_GET: final range %s %s %s %s", firstbyte, lastbyte, nbytes2send, currentThread().getName())


                # 4. Seek in stream to desired offset
                try:
                    stream.seek(firstbyte)
                except:
                    # Arno, 2010-10-17: Live will throw harmless exception,
                    # Ogg live needs it to reset to "send header" first state.
                    # Better solution is to have OggMagicStream with
                    # ControlledStream in BackgroundProcess.py
                    print_exc()

                # For persistent connections keep the socket alive!
                if self.request_version == 'HTTP/1.1':
                    self.send_header("Connection", "Keep-Alive")
                    # test.. to be adjusted depending on the request
                    self.send_header("Keep-Alive", "timeout=300, max=1")

                # 5. Send headers
                self.send_header("Content-Type", mimetype)
                self.send_header("Accept-Ranges", "bytes")

                # Ric: bitrate needs to be detected even if the file is already completed
                if 'bitrate' in streaminfo and length is not None:
                    bitrate = streaminfo['bitrate']
                    estduration = float(length) / float(bitrate)
                    self.send_header("X-Content-Duration", estduration)

                if length is not None:
                    self.send_header("Content-Length", nbytes2send)
                else:
                    self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()

                # 6. Send body (completely, a Range: or an infinite stream in chunked encoding
                done = False
                while True:
                    data = stream.read(blocksize)
                    if len(data) == 0:
                        done = True

                    if DEBUG:
                        self._logger.debug("videoserv: HTTP: read %s bytes %s", len(data), currentThread().getName())

                    if length is None:
                        # If length unknown, use chunked encoding
                        # http://www.ietf.org/rfc/rfc2616.txt, $3.6.1
                        self.wfile.write("%x\r\n" % (len(data)))
                    if len(data) > 0:
                        # Limit output to what was asked on range queries:
                        if length is not None and nbyteswritten + len(data) > nbytes2send:
                            endlen = nbytes2send - nbyteswritten
                            if endlen != 0:
                                self.wfile.write(data[:endlen])
                            done = True
                            nbyteswritten += endlen
                        else:
                            self.wfile.write(data)
                            nbyteswritten += len(data)

                        # print >>sys.stderr,"videoserv: HTTP: wrote total",nbyteswritten

                    if length is None:
                        # If length unknown, use chunked encoding
                        self.wfile.write("\r\n")

                    if done:
                        if DEBUG:
                            self._logger.debug("videoserv: do_GET: stream reached EOF or range query's send limit %s", currentThread().getName())
                        break

                if nbyteswritten != nbytes2send:
                    self._logger.info("videoserv: do_GET: Sent wrong amount, wanted %s got %s %s", nbytes2send, nbyteswritten, currentThread().getName())

                # Arno, 2010-01-08: No close on Range queries
                if not range:
                    stream.close()
                    if self.server.statuscallback is not None:
                        self.server.statuscallback("Done")

            finally:
                self.server.release_inputstream(self.path)

        except socket.error, e2:
            pass
            # print_exc()

        except Exception, e:
            if DEBUG:
                self._logger.debug("videoserv: Error occured while serving %s", currentThread().getName())
            print_exc()
            self.error(e, self.path)

    def error(self, e, url):
        if self.server.errorcallback is not None:
            self.server.errorcallback(e, url)
        else:
            print_exc()
        if self.server.statuscallback is not None:
            self.server.statuscallback("Error playing video:" + str(e))


class VideoRawVLCServer:
    __single = None

    def __init__(self):
        if VideoRawVLCServer.__single:
            raise RuntimeError("VideoRawVLCServer is Singleton")
        VideoRawVLCServer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.lock = RLock()
        self.oldsid = None
        self.sid2streaminfo = {}

        # self.lastsid = None # workaround bug? in raw inf

    def getInstance(*args, **kw):
        if VideoRawVLCServer.__single is None:
            VideoRawVLCServer(*args, **kw)
        return VideoRawVLCServer.__single
    getInstance = staticmethod(getInstance)

    def set_inputstream(self, streaminfo, sid):
        """ Store a record for stream ID "sid" which may be
        retrieved by VLC anytime after this call
        """
        self.lock.acquire()
        try:
            self._logger.info("VLCRawServer: setting sid %s", sid)
            self.sid2streaminfo[sid] = streaminfo

            # workaround
            # self.lastsid = sid
        finally:
            self.lock.release()

    def get_inputstream(self, sid):
        """ Get the record for the given stream """
        # TODO: locking?
        self.lock.acquire()
        try:
            return self.sid2streaminfo[sid]
        finally:
            self.lock.release()

    def shutdown(self):
        pass

    def ReadDataCallback(self, bufc, buflen, sid):
        try:
            # print >>sys.stderr,"VideoRawVLCServer:ReadDataCallback: stream",sid,"wants", buflen,"thread",currentThread().getName()
            # workaround
            # sid = self.lastsid
            # print >>sys.stderr,"VideoRawVLCServer:ReadDataCallback: stream override sid",sid

            if self.oldsid is not None and self.oldsid != sid:
                # Switched streams, garbage collect old
                oldstream = self.sid2streaminfo[self.oldsid]['stream']
                del self.sid2streaminfo[self.oldsid]
                try:
                    oldstream.close()
                except:
                    print_exc()
            self.oldsid = sid

            streaminfo = self.get_inputstream(sid)
            # print >>sys.stderr,"rawread: sid",sid,"n",buflen
            data = streaminfo['stream'].read(buflen)
            size = len(data)
            # print >>sys.stderr,"rawread: sid",sid,"GOT",size
            if size == 0:
                return 0
            else:
                bufc[0:size] = data
            # print >>sys.stderr,"VideoRawVLCServer:ReadDataCallback: bufc size ", len(bufc)

            return size
        except:
            print_exc()
            return -1

    def SeekDataCallback(self, pos, sid):
        try:
            # WARNING: CURRENT 0.8.6h binaries have bug in vlcglue.c: pos is just a long int , not a long long int.

            # print >>sys.stderr,"VideoRawVLCServer: SeekDataCallback: stream",sid,"seeking to", pos,"oldsid",self.oldsid
            # Arno: TODO: add support for seeking
            if True:
                streaminfo = self.get_inputstream(sid)
                streaminfo['stream'].seek(pos, os.SEEK_SET)
                return 0

            return -1

        except:
            print_exc()
            return -1
