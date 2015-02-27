# Written by Feek Zindel
# see LICENSE.txt for license information

from gzip import GzipFile
from StringIO import StringIO
import httplib
import socket
import urllib2
import logging

logger = logging.getLogger(__name__)


def urlOpenTimeout(url, timeout=30, referer='', *data):
    class TimeoutHTTPConnection(httplib.HTTPConnection):

        def connect(self):
            """Connect to the host and port specified in __init__."""
            msg = "getaddrinfo returns an empty list"
            for res in socket.getaddrinfo(self.host, self.port, 0,
                                          socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    self.sock = socket.socket(af, socktype, proto)
                    self.sock.settimeout(timeout)
                    if self.debuglevel > 0:
                        logger.debug("connect: (%s, %s)", self.host, self.port)
                    self.sock.connect(sa)
                except socket.error as msg:
                    if self.debuglevel > 0:
                        logger.debug('connect fail: %s, %s', self.host, self.port)
                    if self.sock:
                        self.sock.close()
                    self.sock = None
                    continue
                break
            if not self.sock:
                raise socket.error(msg)

    class TimeoutHTTPHandler(urllib2.HTTPHandler):

        def http_open(self, req):
            return self.do_open(TimeoutHTTPConnection, req)

    # Boudewijn, 09/09/10: Now accepting gzip compressed HTTP trafic.
    class GZipProcessor(urllib2.BaseHandler):

        def http_request(self, req):
            req.add_header("Accept-Encoding", "gzip")
            return req
        https_request = http_request

        def http_response(self, req, resp):
            if resp.headers.get("content-encoding") == "gzip":
                gzip = GzipFile(fileobj=StringIO(resp.read()), mode="r")
                prev_resp = resp
                resp = urllib2.addinfourl(gzip, prev_resp.headers, prev_resp.url)
                resp.code = prev_resp.code
                resp.msg = prev_resp.msg
            return resp
        https_response = http_response

    # Arno, 2010-03-09: ProxyHandler is implicit, so code already proxy aware.
    opener = urllib2.build_opener(GZipProcessor,
                                  TimeoutHTTPHandler,
                                  urllib2.HTTPDefaultErrorHandler,
                                  urllib2.HTTPRedirectHandler,)
    if referer:
        opener.addheaders = [('Referer', referer)]
    return opener.open(url, *data)


# s = urlOpenTimeout("http://torcache.com/torrent/F91DF2C0DC38FF530BB0B90E6FCD9BF0483F7936.torrent", timeout=10)
# print len(s.read())

# s = urlOpenTimeout("http://frayja.com", timeout=10)
# print len(s.read())
