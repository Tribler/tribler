# Written by Egbert Bouman
# Based on SimpleServer written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information
#
import socket
import logging
import mimetypes

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
from threading import Event, Thread
from traceback import print_exc
from binascii import unhexlify
from cherrypy.lib.httputil import get_ranges

from Tribler.Core.simpledefs import DLMODE_VOD


class VideoServer(ThreadingMixIn, HTTPServer):
    __single = None

    def __init__(self, port, session):
        if VideoServer.__single:
            raise RuntimeError("VideoServer is Singleton")
        VideoServer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.port = port
        self.session = session

        from Tribler.Core.Video.VideoPlayer import VideoPlayer
        self.videoplayer = VideoPlayer.getInstance()

        HTTPServer.__init__(self, ("127.0.0.1", self.port), VideoRequestHandler)

        self.server_thread = None

        self.daemon_threads = True
        self.allow_reuse_address = True

    def getInstance(*args, **kw):
        if VideoServer.__single is None:
            VideoServer(*args, **kw)
        return VideoServer.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        VideoServer.__single = None
    delInstance = staticmethod(delInstance)

    def start(self):
        self.server_thread = Thread(target=self.serve_forever, name="VideoHTTPServerThread-1")
        self.server_thread.setDaemon(True)
        self.server_thread.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
            self.close_request(request)
        except socket.error:
            pass
        except Exception:
            print_exc()


class VideoRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        self._logger = server._logger
        self.videoplayer = server.videoplayer
        self.event = None
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def log_message(self, f, *args):
        pass

    def do_GET(self):
        if self.request_version == 'HTTP/1.1':
            self.protocol_version = 'HTTP/1.1'

        self._logger.debug("VOD request %s %s", self.client_address, self.path)
        downloadhash, fileindex = self.path.strip('/').split('/')
        downloadhash = unhexlify(downloadhash)
        download = self.server.session.get_download(downloadhash)

        if not download or not fileindex.isdigit() or int(fileindex) > len(download.get_def().get_files()):
            self.send_error(404, "Not Found")
            return

        fileindex = int(fileindex)
        filename, length = download.get_def().get_files_as_unicode_with_length()[fileindex]

        requested_range = get_ranges(self.headers.getheader('range'), length)
        if requested_range is not None and len(requested_range) != 1:
            self.send_error(416, "Requested Range Not Satisfiable")
            return

        has_changed = self.videoplayer.get_vod_fileindex() != fileindex or\
            self.videoplayer.get_vod_download() != download
        if has_changed:
            # Notify the videoplayer (which will put the old VOD download back in normal mode).
            self.videoplayer.set_vod_fileindex(fileindex)
            self.videoplayer.set_vod_download(download)

            # Put download in sequential mode + trigger initial buffering.
            if download.get_def().is_multifile_torrent():
                download.set_selected_files([filename])
            download.set_mode(DLMODE_VOD)
            download.restart()

        piecelen = download.get_def().get_piece_length()
        blocksize = piecelen

        if requested_range is not None:
            firstbyte, lastbyte = requested_range[0]
            nbytes2send = lastbyte - firstbyte
            self.send_response(206)
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (firstbyte, lastbyte - 1, length))
        else:
            firstbyte = 0
            nbytes2send = length
            self.send_response(200)

        self._logger.debug("requested range %d - %d", firstbyte, firstbyte + nbytes2send)

        mimetype = mimetypes.guess_type(filename)[0]
        if mimetype:
            self.send_header('Content-Type', mimetype)
        self.send_header('Accept-Ranges', 'bytes')

        if length is not None:
            self.send_header('Content-Length', nbytes2send)
        else:
            self.send_header('Transfer-Encoding', 'chunked')

        if self.request_version == 'HTTP/1.1' and self.headers.get('Connection', '').lower() != 'close':
            self.send_header('Connection', 'Keep-Alive')
            self.send_header('Keep-Alive', 'timeout=300, max=1')

        self.end_headers()

        if has_changed:
            self.wait_for_buffer(download)

        stream, lock = self.videoplayer.get_vod_stream(downloadhash, wait=True)

        with lock:
            if stream.closed:
                return

            stream.seek(firstbyte)
            nbyteswritten = 0
            while True:
                data = stream.read(blocksize)

                if len(data) == 0:
                    break
                elif length is not None and nbyteswritten + len(data) > nbytes2send:
                    endlen = nbytes2send - nbyteswritten
                    if endlen != 0:
                        self.wfile.write(data[:endlen])
                        nbyteswritten += endlen
                    break
                else:
                    self.wfile.write(data)
                    nbyteswritten += len(data)

            if nbyteswritten != nbytes2send:
                self._logger.error("sent wrong amount, wanted %s got %s", nbytes2send, nbyteswritten)

            if not requested_range:
                stream.close()

    def wait_for_buffer(self, download):
        self.event = Event()

        def wait_for_buffer(ds):
            if download.vod_seekpos is None or download != self.videoplayer.get_vod_download()\
                    or ds.get_vod_prebuffering_progress() == 1.0:
                self.event.set()
                return 0, False
            return 1.0, False
        download.set_state_callback(wait_for_buffer)
        self.event.wait()
        self.event.clear()
