# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""This module implements a HTTP Server for the UPnP Server."""

import re
import types
import socket
import urlparse
import Tribler.UPnP.common.upnpsoap as upnpsoap
import Tribler.UPnP.common.asynchHTTPserver as httpserver

#
# REQUEST HANDLER
#


class _RequestHandler(httpserver.AsynchHTTPRequestHandler):

    """Request Handler for UPnP Server HTTP Server."""

    def do_GET(self):
        """Respond to a GET request"""
        # In case of full url, parse to get to path
        url = urlparse.urlparse(self.path)

        # Expect Paths
        # /devices/devicename/presentation.html
        # /devices/devicename/description.xml
        # /services/serviceID/presentation.html
        # /services/serviceID/description.xml
        #
        # or special paths
        # /description.xml
        # /presentation.html

        path = url.path.strip('/')
        body = None
        tokens = path.split('/')

        # Special Root Device Description Path
        if path == self.server.service_manager.get_description_path():
            root_device = self.server.service_manager.get_root_device()
            body = root_device.get_xml_description()
            content_type = "text/xml"
        # Special Root Device Presentation Path
        elif path == self.server.service_manager.get_presentation_path():
            root_device = self.server.service_manager.get_root_device()
            body = root_device.get_html_description()
            content_type = "text/html"
        # Other Requests.
        elif len(tokens) == 3:
            type_, name = tokens[:2]

            if type_ == 'devices':
                object_ = self.server.service_manager.get_device(name)
            elif type_ == 'services':
                object_ = self.server.service_manager.get_service(name)

            if object:
                if path == object_.description_path:
                    body = object_.get_xml_description()
                    content_type = 'text/xml'
                elif path == object_.presentation_path:
                    body = object_.get_html_description()
                    content_type = 'text/html'

        try:
            if body:
                # Log
                msg = "GET %s [%s]" % (path, self.client_address[0])
                self.server.log(msg)

                self.send_response(200)
                self.send_header('content-length', str(len(body)))
                self.send_header('content-type', content_type)
                if 'accept-language' in self.headers:
                    self.send_header('content-language',
                                     self.headers['accept-language'])
                else:
                    self.send_header('content-language', 'xml:lang="en"')
                self.send_header('date', self.date_time_string())
                self.end_headers()
                self.wfile.write(body)
                self.request.close()
            else:
                self.send_error(404)
        except socket.error as error:
            self.server.log("SocketError %s" % error)

    def do_POST(self):
        """Responds to POST request."""
        # In case of full url, parse to get to path
        url = urlparse.urlparse(self.path)
        # Expect Path
        # /services/serviceID/control
        path = url.path.strip('/')
        tokens = path.split('/')
        if len(tokens) == 3:
            service_id = tokens[1]

            # Parse Header
            body_bytes = int(self.headers['content-length'])
            soapaction = self.headers['soapaction'].strip('"')
            [name_space, action_name] = soapaction.split("#")
            service = name_space.split(":")[2]

            # Body (SoapXML)
            body = self.rfile.read(body_bytes)
            res = upnpsoap.parse_action_request(body)
            if res:
                action = res[0]
                args = res[2]

                # Log
                msg = "POST %s %s [%s]" % (path, action,
                                           self.client_address[0])
                self.server.log(msg)

                service = self.server.service_manager.get_service(service_id)
                if service:
                    result_list = service.invoke_action(action_name, args)

                if isinstance(result_list, list):
                    # Reply
                    result_body = upnpsoap.create_action_response(name_space,
                                                                  action_name, result_list)
                    self.send_response(200)
                else:
                    # Error
                    result_body = upnpsoap.create_error_response("501",
                    "Operation Not supported")
                    self.send_response(500)

                self.send_header('Content-Length', str(len(result_body)))
                self.send_header('Content-Type', 'text/xml; charset="utf-8"')
                self.send_header('DATE', self.date_time_string())
                self.send_header('EXT', '')
                self.send_header('SERVER', self.server.get_server_header())
                self.end_headers()
                self.wfile.write(result_body)
                self.request.close()
                return

        self.server.log("ERROR Post %s %s" % (path,
                       self.client_address[0]))
        self.send_response(500)
        self.end_headers()
        self.request.close()

    def do_SUBSCRIBE(self):
        """Responds to SUBSCRIBE request."""
        # In case of full url, parse to get to path
        url = urlparse.urlparse(self.path)
        # Expect path
        # /services/service_id/events
        # or full URL
        # http://host:port/services/service_id/events
        path = url.path.strip('/')
        tokens = path.split('/')[-2:]

        error = 500

        if len(tokens) == 2:
            service_id = tokens[0]
            path = "/%s/%s" % tuple(tokens)

            # Service
            service = self.server.service_manager.get_service(service_id)

            # Requested Duration of Subscription
            if 'timeout' in self.headers:
                duration = self.headers['timeout'].split('-')[-1]
                if duration == 'infinite':
                    duration = 0
                else:
                    duration = int(duration)
            else:
                duration = 0

            # Subscribe
            if 'nt' in self.headers:
                # Callback URLs
                callback_urls = re.findall('<.*?>', self.headers['callback'])
                callback_urls = [url.strip('<>') for url in callback_urls]
                # Subscribe
                sid, duration = service.subscribe(callback_urls, duration)
                # Log
                msg = "SUBSCRIBE %s [%s]" % (path, self.client_address[0])
                self.server.log(msg)

            # Renew
            elif 'sid' in self.headers:
                sid = self.headers['sid'].split(':')[-1]
                # Renew
                duration = service.renew(sid, duration)
                # Log
                msg = "RENEW %s %s" % (path, self.client_address[0])
                self.server.log(msg)

            if sid and duration:
                # Respond
                self.send_response(200)
                self.send_header('server', self.server.get_server_header())
                self.send_header('sid', 'uuid:%s' % sid)
                self.send_header('timeout', 'Second-%s' % duration)
                self.send_header('content-length', 0)
                self.end_headers()
                self.wfile.flush()
                self.request.close()
                return
            else:
                error = 412  # Precondition failed

        msg = "ERROR [%d] Subscribe %s %s" % (error, path,
                                         self.client_address[0])
        self.server.log(msg)
        self.send_response(error)
        self.end_headers()

    def do_UNSUBSCRIBE(self):
        """Responds to UNSUBSCRIBE request."""
        # In case of full url, parse to get to path
        url = urlparse.urlparse(self.path)
        # Expect path
        # /services/service_id/events
        # or full URL
        # http://host:port/services/service_id/events
        path = url.path.strip('/')
        tokens = path.split('/')[-2:]
        if len(tokens) == 2:
            service_id = tokens[0]
            path = "/%s/%s" % tuple(tokens)
            # SID
            sid = self.headers['sid'].split(':')[-1]
            # UnSubscribe
            service = self.server.service_manager.get_service(service_id)
            service.unsubscribe(sid)
            # Log
            msg = "UNSUBSCRIBE %s [%s]" % (path, self.client_address[0])
            self.server.log(msg)
            # Protect against Control Point closing connection early.
            try:
                self.send_response(200)
                self.end_headers()
                self.request.close()
            except socket.error:
                pass
        else:
            msg = "ERROR Unsubscribe %s %s" % (path,
            self.client_address[0])
            self.server.log(msg)
            self.send_response(500)
            self.end_headers()
            self.request.close()

    def do_NOTIFY(self):
        """Responds to NOTIFY request. Just for testing."""
        msg = "NOTIFY [%s] %s" % (self.client_address[0], self.path)
        self.server.log(msg)
        data = "test"
        try:
            self.send_response(200)
            self.send_header('content-length', len(data))
            self.end_headers()
            self.wfile.write(data)
            self.request.close()
        except socket.error:
            pass

#
# HTTP SERVER
#

_HTTP_PORT = 44444


class HTTPServer(httpserver.AsynchHTTPServer):

    """HTTP Server for the UPnP Server."""

    def __init__(self, task_runner, logger=None):

        httpserver.AsynchHTTPServer.__init__(self, task_runner, _HTTP_PORT,
                                             _RequestHandler, logger)

        # Service Manager
        self.service_manager = None

    def set_service_manager(self, service_manager):
        """Initialise with reference to service manager."""
        self.service_manager = service_manager

    def get_server_header(self):
        """Get SERVER header for UPnP Server."""
        # Server Header
        server_fmt = '%s UPnP/1.0 %s'
        return server_fmt % (self.service_manager.get_os_version(),
                             self.service_manager.get_product_version())

    def startup(self):
        """Extend startup of superclass."""
        httpserver.AsynchHTTPServer.startup(self)
        self.log("URL %s" % self.service_manager.get_presentation_url())
