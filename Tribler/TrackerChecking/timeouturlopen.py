import httplib
import socket
import urllib2
from urllib import addinfourl

def urlOpenTimeout(url,timeout=30,*data):
    class TimeoutHTTPConnection(httplib.HTTPConnection):
        def connect(self):
            """Connect to the host and port specified in __init__."""
            msg = "getaddrinfo returns an empty list"
            for res in socket.getaddrinfo(self.host, self.port, 0,
                                          socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    self.sock = socket.socket(af,socktype, proto)
                    self.sock.settimeout(timeout)
                    if self.debuglevel > 0:
                        print "connect: (%s, %s)" % (self.host, self.port)
                    self.sock.connect(sa)
                except socket.error, msg:
                    if self.debuglevel > 0:
                        print 'connect fail:', (self.host, self.port)
                    if self.sock:
                        self.sock.close()
                    self.sock = None
                    continue
                break
            if not self.sock:
                raise socket.error, msg

    class TimeoutHTTPHandler(urllib2.HTTPHandler):
        def http_open(self, req):
            return self.do_open(TimeoutHTTPConnection, req)

    opener = urllib2.build_opener(TimeoutHTTPHandler,
                                  urllib2.HTTPDefaultErrorHandler,
                                  urllib2.HTTPRedirectHandler)
    return opener.open(url,*data)

s = urlOpenTimeout("http://www.google.com",timeout=30)
