
import sys
import os
import time
from traceback import print_exc

from Tribler.Video.VideoServer import VideoHTTPServer


VIDEOHTTP_LISTENPORT = 8080


class HTTPSeeder:

    def __init__(self):
        self.videoHTTPServer = VideoHTTPServer(VIDEOHTTP_LISTENPORT)
        self.videoHTTPServer.register(self.videoservthread_error_callback, self.videoservthread_set_status_callback)
        self.videoHTTPServer.background_serve()

    #
    # VideoServer status/error reporting
    #
    def videoservthread_error_callback(self, e, url):
        print("httpseed: Video server reported error", url, str(e), file=sys.stderr)

    def videoservthread_set_status_callback(self, status):
        print("httpseed: Video server sets status callback", status, file=sys.stderr)


if __name__ == '__main__':

    print("httpseed: Starting", file=sys.stderr)

    httpseed = HTTPSeeder()

    paths = []
    paths.append("treeOfLife.ogv")
    paths.append("RDTV_ep2_5min.ogv")

    for path in paths:
        filename = os.path.basename(path)

        f = open(path, "rb")
        s = os.stat(path)
        fsize = s.st_size

        # streaminfo = { 'mimetype': 'application/ogg', 'stream': f, 'length': fsize, 'blocksize':2 ** 16, 'bitrate':69976.4 }
        streaminfo = {'mimetype': 'application/ogg', 'stream': f, 'length': fsize, 'blocksize': 2 ** 16}

        urlpath = "/" + filename
        print("httpseed: Hosting", urlpath, file=sys.stderr)
        httpseed.videoHTTPServer.set_inputstream(streaminfo, urlpath)

    print("httpseed: Waiting", file=sys.stderr)
    try:
        while True:
            time.sleep(sys.maxsize / 2048)
    except:
        print_exc()
