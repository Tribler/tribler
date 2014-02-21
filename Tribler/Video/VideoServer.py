# Written by Jan David Mol, Arno Bakker
# Heavily modified by Egbert Bouman
# see LICENSE.txt for license information
#
import sys
import logging
import cherrypy
import mimetypes

from multiprocessing.synchronize import Event
from binascii import unhexlify
from cherrypy.lib import http

from Tribler.Core.simpledefs import DLMODE_VOD, DLMODE_NORMAL, NTFY_TORRENTS, NTFY_VIDEO_BUFFER


class VideoServer:
    __single = None

    def __init__(self, port, session):
        if VideoServer.__single:
            raise RuntimeError("VideoServer is singleton")
        VideoServer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.DEBUG)

        self.port = port
        self.session = session
        self.started = False

        from Tribler.Video.VideoPlayer import VideoPlayer
        self.videoplayer = VideoPlayer.getInstance()

        self.event = Event()
        self.session.add_observer(self.on_buffer, NTFY_TORRENTS, [NTFY_VIDEO_BUFFER])

    def getInstance(*args, **kw):
        if VideoServer.__single is None:
            VideoServer(*args, **kw)
        return VideoServer.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        VideoServer.__single = None
    delInstance = staticmethod(delInstance)

    def start(self):
        if not self.started:
            cherrypy.log.access_log.setLevel(logging.NOTSET)
            cherrypy.log.error_log.setLevel(logging.NOTSET)
            cherrypy.log.screen = False

            cherrypy.server.socket_port = self.port
            cherrypy.server.socket_timeout = 3600
            cherrypy.server.protocol_version = 'HTTP/1.1'

            app = cherrypy.tree.mount(self, config={'/':{}})
            app.log.access_log.setLevel(logging.NOTSET)
            app.log.error_log.setLevel(logging.NOTSET)

            cherrypy.engine.start()
            self.started = True

    def stop(self):
        if self.started:
            cherrypy.engine.exit()

    @cherrypy.expose
    def default(self, downloadhash, fileindex):
        print >> sys.stderr, "VideoServer: VOD request for", downloadhash, "/", fileindex
        downloadhash = unhexlify(downloadhash)
        download = self.session.get_download(downloadhash)

        if not download or not fileindex.isdigit() or int(fileindex) > len(download.get_def().get_files()):
            raise cherrypy.HTTPError(404, "Not Found")
            return

        filename, length = download.get_def().get_files_with_length()[int(fileindex)]

        requested_range = http.get_ranges(cherrypy.request.headers.get('Range'), length)
        if requested_range == []:
            raise cherrypy.HTTPError(416, "Requested Range Not Satisfiable")
            return

        # Put download in sequential mode + trigger initial buffering.
        if download.get_def().get_def_type() != "torrent" or download.get_def().is_multifile_torrent():
            download.set_selected_files([filename])
        self.event = Event()
        def wait_for_buffer(ds):
            if ds.get_vod_prebuffering_progress() == 1.0:
                self.event.set()
                return (0, False)
            return (1.0, False)
        download.set_state_callback(wait_for_buffer)
        download.set_mode(DLMODE_VOD)
        download.restart()

        # Put old VOD download back in normal mode.
#        if self.videoplayer.get_vod_download():
#            self.videoplayer.get_vod_download().set_mode(DLMODE_NORMAL)

        # Wait for buffering to complete.
        self.event.wait()

        mimetype = mimetypes.guess_type(filename)[0]
        piecelen = 2 ** 16 if download.get_def().get_def_type() == "swift" else download.get_def().get_piece_length()
        blocksize = piecelen

        if requested_range != None:
            firstbyte, lastbyte = requested_range[0]
            nbytes2send = lastbyte - firstbyte
            cherrypy.response.status = 206
            cherrypy.response.headers['Content-Range'] = 'bytes %d-%d/%d' % (firstbyte, lastbyte + 1, length)
        else:
            firstbyte = 0
            nbytes2send = length
            cherrypy.response.status = 200

        cherrypy.response.headers['Content-Type'] = mimetype
        cherrypy.response.headers['Accept-Ranges'] = 'bytes'

        if length is not None:
            cherrypy.response.headers['Content-Length'] = nbytes2send
        else:
            cherrypy.response.headers['Transfer-Encoding'] = 'chunked'

        if cherrypy.request.server_protocol == 'HTTP/1.1':
            cherrypy.response.headers['Connection'] = 'Keep-Alive'

        def write_data():
            stream, lock = self.videoplayer.get_vod_stream(downloadhash)
            with lock:
                stream.seek(firstbyte)
                nbyteswritten = 0
                while True:
                    data = stream.read(blocksize)
                    if len(data) == 0:
                        break
                    elif length is not None and nbyteswritten + len(data) > nbytes2send:
                        endlen = nbytes2send - nbyteswritten
                        if endlen != 0:
                            yield data[:endlen]
                            nbyteswritten += endlen
                        break
                    else:
                        yield data
                        nbyteswritten += len(data)

                    self.event.wait()

                if nbyteswritten != nbytes2send:
                    self._logger.error("VideoServer: sent wrong amount, wanted %s got %s", nbytes2send, nbyteswritten)

                if not requested_range:
                    stream.close()

        return write_data()

    default._cp_config = {'response.stream': True}

    def on_buffer(self, subject, changeType, download, fileindex, buffer_full):
        print >> sys.stderr, "VideoServer: on_buffer", buffer_full
        if buffer_full:
            self.event.set()
        else:
            self.event.clear()
