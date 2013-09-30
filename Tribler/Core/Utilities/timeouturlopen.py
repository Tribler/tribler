# Written by Feek Zindel
# see LICENSE.txt for license information

from gzip import GzipFile
from StringIO import StringIO
import sys
import httplib
import socket
import urllib2

import urllib
import urlparse

DEBUG = False

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
                        print "connect: (%s, %s)" % (self.host, self.port)
                    self.sock.connect(sa)
                except socket.error as msg:
                    if self.debuglevel > 0:
                        print 'connect fail:', (self.host, self.port)
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


def find_proxy(url):
    """ Returns proxy host as "host:port" string """
    (scheme, netloc, path, pars, query, fragment) = urlparse.urlparse(url)
    proxies = urllib.getproxies()
    proxyhost = None
    if scheme in proxies:
        if '@' in netloc:
            sidx = netloc.find('@') + 1
        else:
            sidx = 0
        # IPVSIX TODO: what if host is IPv6 address
        eidx = netloc.find(':')
        if eidx == -1:
            eidx = len(netloc)
        host = netloc[sidx:eidx]
        if not (host == "127.0.0.1" or urllib.proxy_bypass(host)):
            proxyurl = proxies[scheme]
            proxyelems = urlparse.urlparse(proxyurl)
            proxyhost = proxyelems[1]

    if DEBUG:
        print >>sys.stderr, "find_proxy: Got proxies", proxies, "selected", proxyhost, "URL was", url
    return proxyhost


# s = urlOpenTimeout("http://torcache.com/torrent/F91DF2C0DC38FF530BB0B90E6FCD9BF0483F7936.torrent", timeout=10)
# print len(s.read())

# s = urlOpenTimeout("http://frayja.com", timeout=10)
# print len(s.read())
