# Written by John Hoffman
# see LICENSE.txt for license information

from httplib import HTTPConnection, HTTPException
from urlparse import urlparse
from bencode import bdecode
import socket
from gzip import GzipFile
from StringIO import StringIO
from urllib import quote, unquote
from __init__ import product_name, version_short

VERSION = product_name+'/'+version_short
MAX_REDIRECTS = 10


class btHTTPcon(HTTPConnection): # attempt to add automatic connection timeout
    def connect(self):
        HTTPConnection.connect(self)
        try:
            self.sock.settimeout(30)
        except:
            pass


class urlopen:
    def __init__(self, url):
        self.tries = 0
        self._open(url.strip())
        self.error_return = None

    def _open(self, url):
        self.tries += 1
        if self.tries > MAX_REDIRECTS:
            raise IOError, ('http error', 500,
                            "Internal Server Error: Redirect Recursion")
        (scheme, netloc, path, pars, query, fragment) = urlparse(url)
        if scheme != 'http':
            raise IOError, ('url error', 'unknown url type', scheme, url)
        url = path
        if pars:
            url += ';'+pars
        if query:
            url += '?'+query
#        if fragment:
        try:
            self.connection = btHTTPcon(netloc)
            self.connection.request('GET', url, None,
                                { 'User-Agent': VERSION,
                                  'Accept-Encoding': 'gzip' } )
            self.response = self.connection.getresponse()
        except HTTPException, e:
            raise IOError, ('http error', str(e))
        status = self.response.status
        if status in (301,302):
            try:
                self.connection.close()
            except:
                pass
            self._open(self.response.getheader('Location'))
            return
        if status != 200:
            try:
                data = self._read()
                d = bdecode(data)
                if d.has_key('failure reason'):
                    self.error_return = data
                    return
            except:
                pass
            raise IOError, ('http error', status, self.response.reason)

    def read(self):
        if self.error_return:
            return self.error_return
        return self._read()

    def _read(self):
        data = self.response.read()
        if self.response.getheader('Content-Encoding','').find('gzip') >= 0:
            try:
                compressed = StringIO(data)
                f = GzipFile(fileobj = compressed)
                data = f.read()
            except:
                raise IOError, ('http error', 'got corrupt response')
        return data

    def close(self):
        self.connection.close()
