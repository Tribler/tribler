# Written by Njaal Borch
# see LICENSE.txt for license information

import os.path

import sys
import socket  # For IPv6 override
import select
import threading

import BaseHTTPServer

import random  # Do not allow all nodes access


from Tribler.Core.ClosedSwarm import ClosedSwarm, Tools
from Tribler.Core.Statistics.Status import *

# Add SocketServer.ThreadingMixIn to get multithreaded


class MyWebServer(BaseHTTPServer.HTTPServer):

    """
    Non-blocking, multi-threaded IPv6 enabled web server
    """

    if socket.has_ipv6:
        address_family = socket.AF_INET6

    # Override in case python has IPv6 but system does not
    def __init__(self, server_address, RequestHandlerClass):
        try:
            BaseHTTPServer.HTTPServer.__init__(self,
                                               server_address,
                                               RequestHandlerClass)
        except:
            print >>sys.stderr, "Failed to use IPv6, using IPv4 instead"
            self.address_family = socket.AF_INET
            BaseHTTPServer.HTTPServer.__init__(self,
                                               server_address,
                                               RequestHandlerClass)
    # Override that blasted blocking thing!

    def get_request(self):
        """Get the request and client address from the socket.
        Override to allow non-blocking requests.

        WARNING: This will make "serve_forever" and "handle_request"
        throw exceptions and stuff! Serve_forever thus does not work!
        """

        # Use select for non-blocking IO
        if select.select([self.socket], [], [], 1)[0]:
            return self.socket.accept()
        else:
            return (None, None)


class WebHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    """
    Handle requests
    """

    server_version = "CS_Trial/2009_09"

    def log_message(self, format, *args):
        """
        Override message logging - don't want reverse DNS lookups
        or output to stderr

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client host and current date/time are prefixed to
        every message.

        """

        print format % args

    def failed(self, code, message=None):
        """
        Request failed, return error
        """

        try:
            if message:
                print "Sending %d (%s)" % (code, message)
                self.send_error(code, message)
            else:
                print "Sending %d " % code
                self.send_error(code)

            try:  # Should this be here?
                self.end_headers()
            except Exception as e:
                print >>sys.stderr, "Error sending end_headers - I guess I shouldn't do  it then"

            # self.wfile.close()
        except Exception as e:

            # Error sending error...  Log and ingnore
            print >>sys.stderr, "Error sending error %s, ignoring (%s)" % (code, e)

            # TODO: Remove this error thingy
            raise Exception("Could not send error")

        return False

    def prepareSend(self, type, size=None, response=200):

        # We're ready!
        try:
            self.send_response(response)
        except Exception as e:
            print >>sys.stderr, "Error sending response: %s" % e
            return

        # self.send_header("date", makeRFC1123time(time.time()))
        self.send_header("server", self.server_version)
        self.send_header("Content-Type", type)
        if size:
            self.send_header("Content-Length", size)
        self.end_headers()

    def do_POST(self):
        """
        Handle a POST request for a POA for the trial
        """

        # Don't block forever here
        self.rfile._sock.settimeout(5.0)

        import cgi
        env = {}
        env['REQUEST_METHOD'] = self.command
        if self.headers.typeheader is None:
            env['CONTENT_TYPE'] = self.headers.type
        else:
            env['CONTENT_TYPE'] = self.headers.typeheader
        length = self.headers.getheader('content-length')
        if length:
            env['CONTENT_LENGTH'] = length

        form = cgi.FieldStorage(environ=env, fp=self.rfile)

        try:
            swarm_id = form['swarm_id'].value
            perm_id = form['perm_id'].value
        except:
            return self.failed(400)

        try:
            poa = self.generate_poa(swarm_id, perm_id)
        except Exception as e:
            print >>sys.stderr, "Missing key for swarm '%s'" % swarm_id, e
            return self.failed(404)

        self.prepareSend("application/octet-stream", len(poa))
        self.wfile.write(poa)
        self.wfile.close()

    def generate_poa(self, swarm_id, perm_id):
        """
        Generate a POA if the swarm-id private key is available
        """

        status = Status.get_status_holder("LivingLab")

        # Randomly allow 80% to be authorized...
        if random.randint(0, 100) > 80:
            status.create_and_add_event("denied", [swarm_id, perm_id])
            status.get_status_element("poas_failed").inc()
            raise Exception("Randomly denied...")

        key_file = os.path.join(KEY_PATH, swarm_id + ".tkey")
        if not os.path.exists(key_file):
            raise Exception("Missing key file")

        # Load keys
        try:
            torrent_keypair = ClosedSwarm.read_cs_keypair(key_file)
        except Exception as e:
            raise Exception("Bad torrent key file")

        # TODO? Sanity - check that this key matches the torrent

        poa = ClosedSwarm.create_poa(swarm_id, torrent_keypair, perm_id)

        status.create_and_add_event("allowed", [swarm_id, perm_id])
        status.get_status_element("poas_generated").inc()

        return poa.serialize()


class WebServer(threading.Thread):

    def __init__(self, port):
        threading.Thread.__init__(self)
        print "Starting WebServer on port %s" % port
        self.server = MyWebServer(('', int(port)), WebHandler)
        self.port = port
        self.running = False

    def run(self):

        self.running = True

        print "WebServer Running on port %s" % self.port

        while self.running:
            try:
                print "Waiting..."
                self.server.handle_request()
            except Exception as e:
                if e.args[0] != "unpack non-sequence":
                    print >>sys.stderr, "Error handling request", e

                # Ignore these, Just means that there was no request
                # waiting for us
                pass

        print "Web server Stopped"

    def stop(self):
        self.running = False

        self.server.socket.shutdown(socket.SHUT_RDWR)

        self.server.socket.close()


if __name__ == "__main__":

    KEY_PATH = "./"

    status = Status.get_status_holder("LivingLab")
    id = "poa_generator"
    reporter = LivingLabReporter.LivingLabPeriodicReporter("Living lab CS reporter", 300, id)  # Report every 5 minutes
    status.add_reporter(reporter)

    status.create_status_element("poas_generated", 0)
    status.create_status_element("poas_failed", 0)

    ws = WebServer(8080)
    ws.start()

    raw_input("WebServer running, press ENTER to stop it")

    print "Stopping server"
    reporter.stop()
    ws.stop()
