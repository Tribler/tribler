# Written by Arno Bakker, extracted
# from test_connect_overlay.py by Niels Zeilemaker

import socket
import thread
import BaseHTTPServer
from SocketServer import ThreadingMixIn

DEBUG = True


class MyTracker(ThreadingMixIn, BaseHTTPServer.HTTPServer):

    def __init__(self, trackport, myid, myip, myport):
        self.myid = myid
        self.myip = myip
        self.myport = myport
        BaseHTTPServer.HTTPServer.__init__(self, ("", trackport), SimpleServer)
        self.daemon_threads = True

    def background_serve(self):
        thread.start_new_thread(self.serve_forever, ())

    def shutdown(self):
        self.socket.close()


class SimpleServer(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):

        print("test: tracker: Got GET request", self.path, file=sys.stderr)

        p = []
        p1 = {'peer id': self.server.myid, 'ip': self.server.myip,'port':self.server.myport}
        p.append(p1)
        d = {}
        d['interval'] = 1800
        d['peers'] = p
        bd = bencode(d)
        size = len(bd)

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", size)
        self.end_headers()

        try:
            self.wfile.write(bd)
        except Exception as e:
            print_exc()
