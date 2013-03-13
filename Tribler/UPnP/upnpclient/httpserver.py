# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""This module implements a HTTP Server for the UPnP Client
(UPnP Control Point)."""

import urlparse
import socket
import uuid
import Tribler.UPnP.common.upnpsoap as upnpsoap
import Tribler.UPnP.common.asynchHTTPserver as httpserver

##############################################
# REQUEST HANDLER
##############################################

class _RequestHandler(httpserver.AsynchHTTPRequestHandler):
    """HTTP Request Handler for UPnP Client."""

    def do_NOTIFY(self):
        """Respond to NOTIFY request."""
        url = urlparse.urlparse(self.path)
        path = url.path.strip('/')
        tokens = path.split('/')
        if len(tokens) == 2:

            # Parse Request
            device_uuid = uuid.UUID(tokens[0])
            service_id = tokens[1]

            # Sid
            sid = None
            if self.headers.has_key('sid'):
                tokens =  self.headers['sid'].split(':')
                if len(tokens) == 2:
                    sid = uuid.UUID(tokens[1])

            # Seq
            seq = int(self.headers.get('seq', '-1'))

            # Body
            body_bytes = int(self.headers.get('content-length', '0'))
            body = self.rfile.read(body_bytes)
            var_list = upnpsoap.parse_event_message(body)

            # Process Notification
            self.server.handle_notification(device_uuid, service_id,
                                            sid, seq, var_list)

            # Log
            msg = "NOTIFY %s [%s]" % (service_id, self.client_address[0])
            self.server.log(msg)

            # Send Response
            try:
                self.send_response(200)
                self.end_headers()
                self.request.close()
            except socket.error:
                pass

        else:
            try:
                self.send_response(500)
                self.end_headers()
                self.request.close()
            except socket.error:
                pass



##############################################
# HTTP SERVER
##############################################

_HTTP_PORT = 44445

class HTTPServer(httpserver.AsynchHTTPServer):
    """HTTP Server for the UPnP Client."""

    def __init__(self, upnp_client, task_runner, logger=None):

        httpserver.AsynchHTTPServer.__init__(self, task_runner,
                                             _HTTP_PORT,
                                             _RequestHandler, logger=logger)

        self._upnp_client = upnp_client
        self._base_event_url = "http://%s:%d/" % (self.get_host(),
                                                  self.get_port())


    def startup(self):
        """Extending Startup."""
        httpserver.AsynchHTTPServer.startup(self)
        self.log("URL %s" % self._base_event_url)

    def handle_notification(self, device_uuid, service_id, sid, seq, var_list):
        """Notification forwarded to UPnPClient."""
        self._upnp_client.handle_notification(device_uuid, service_id,
                                               sid, seq, var_list)

    def get_base_event_url(self):
        """Get base event URL."""
        return self._base_event_url
