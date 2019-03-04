"""
Video server.

Author(s): Jan David Mol, Arno Bakker, Egbert Bouman
"""
from __future__ import absolute_import

import logging
import mimetypes
import os
import socket
import time
from binascii import unhexlify
from collections import defaultdict
from threading import Event, RLock, Thread
from traceback import print_exc

from cherrypy.lib.httputil import get_ranges

from six.moves import xrange
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from six.moves.socketserver import ThreadingMixIn

from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import VODFile
from Tribler.Core.simpledefs import DLMODE_NORMAL, DLMODE_VOD


class VideoServer(ThreadingMixIn, HTTPServer):

    def __init__(self, port, session):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.port = port
        self.session = session
        self.vod_fileindex = None
        self.vod_download = None
        self.vod_info = defaultdict(dict)  # A dictionary containing info about the requested VOD streams.

        for _ in xrange(10000):
            try:
                HTTPServer.__init__(self, ("127.0.0.1", self.port), VideoRequestHandler)
                self._logger.debug("Listening at %d", self.port)
                break
            except socket.error:
                self._logger.debug("Listening failed at %d", self.port)
                self.port += 1
                continue

        self.server_thread = None

        self.daemon_threads = True
        self.allow_reuse_address = True

    def get_vod_download(self):
        """
        Return the current Video-On-Demand download that is being requested.
        """
        return self.vod_download

    def set_vod_download(self, new_download):
        """
        Set a new Video-On-Demand download. Set the mode of old download to normal and close the file stream of
        the old download.
        """
        if self.vod_download:
            self.vod_download.set_mode(DLMODE_NORMAL)
            vi_dict = self.vod_info.pop(self.vod_download.get_def().get_infohash(), None)
            if vi_dict and 'stream' in vi_dict:
                vi_dict['stream'][0].close()

        self.vod_download = new_download

    def get_vod_stream(self, dl_hash, wait=False):
        if 'stream' not in self.vod_info[dl_hash] and self.session.get_download(dl_hash):
            download = self.session.get_download(dl_hash)
            vod_filename = self.get_vod_destination(download)
            while wait and not os.path.exists(vod_filename):
                time.sleep(1)
            self.vod_info[dl_hash]['stream'] = (VODFile(open(vod_filename, 'rb'), download), RLock())

        if self.vod_info[dl_hash].has_key('stream'):
            return self.vod_info[dl_hash]['stream']
        return None, None

    @staticmethod
    def get_vod_destination(download):
        """
        Get the destination directory of the VOD download.
        """
        if download.get_def().is_multifile_torrent():
            return os.path.join(download.get_content_dest(), download.get_selected_files()[0])
        else:
            return download.get_content_dest()

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

    def shutdown_server(self):
        """
        Shutdown the video HTTP server.
        """
        self.shutdown()
        self.server_close()
        self.set_vod_download(None)


class VideoRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, video_server):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.event = None
        self.video_server = video_server
        BaseHTTPRequestHandler.__init__(self, request, client_address, video_server)

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
        filename, length = download.get_def().get_files_with_length()[fileindex]

        requested_range = get_ranges(self.headers.getheader('range'), length)
        if requested_range is not None and len(requested_range) != 1:
            self.send_error(416, "Requested Range Not Satisfiable")
            return

        has_changed = self.video_server.vod_fileindex != fileindex or\
            self.video_server.get_vod_download() != download
        if has_changed:
            self.video_server.vod_fileindex = fileindex
            self.video_server.set_vod_download(download)

            # Put download in sequential mode + trigger initial buffering.
            self.wait_for_handle(download)
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

        stream, lock = self.video_server.get_vod_stream(downloadhash, wait=True)

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

    def wait_for_handle(self, download):
        # TODO(Martijn): Ugly time.sleep required, should be refactored when we Twistify the video server
        while not (download.handle and download.handle.is_valid()):
            time.sleep(1)

    def wait_for_buffer(self, download):
        self.event = Event()

        def wait_for_buffer(ds):
            if download.vod_seekpos is None or download != self.video_server.get_vod_download()\
                    or ds.get_vod_prebuffering_progress() == 1.0:
                self.event.set()
                return 0
            return 1.0
        download.set_state_callback(wait_for_buffer)
        self.event.wait()
        self.event.clear()
