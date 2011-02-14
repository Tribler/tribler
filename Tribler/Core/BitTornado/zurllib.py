# Written by John Hoffman
# see LICENSE.txt for license information

import sys
from httplib import HTTPConnection, HTTPSConnection, HTTPException
from urlparse import urlparse
from bencode import bdecode
from gzip import GzipFile
from StringIO import StringIO
from __init__ import product_name, version_short
from traceback import print_exc,print_stack

from Tribler.Core.Utilities.timeouturlopen import find_proxy

VERSION = product_name+'/'+version_short
MAX_REDIRECTS = 10


class btHTTPcon(HTTPConnection): # attempt to add automatic connection timeout
    def connect(self):
        HTTPConnection.connect(self)
        try:
            self.sock.settimeout(30)
        except:
            pass

class btHTTPScon(HTTPSConnection): # attempt to add automatic connection timeout
    def connect(self):
        HTTPSConnection.connect(self)
        try:
            self.sock.settimeout(30)
        except:
            pass 

class urlopen:
    def __init__(self, url, silent = False):
        self.tries = 0
        self._open(url.strip(), silent)
        self.error_return = None

    def _open(self, url, silent = False):
        try:
            self.tries += 1
            if self.tries > MAX_REDIRECTS:
                raise IOError, ('http error', 500,
                                "Internal Server Error: Redirect Recursion")
            (scheme, netloc, path, pars, query, fragment) = urlparse(url)
            if scheme != 'http' and scheme != 'https':
                raise IOError, ('url error', 'unknown url type', scheme, url)
            wanturl = path
            if pars:
                wanturl += ';'+pars
            if query:
                wanturl += '?'+query
    #        if fragment:
    
            proxyhost = find_proxy(url)
            if proxyhost is None:
                desthost = netloc
                desturl = wanturl
            else:
                desthost = proxyhost
                desturl = scheme+'://'+netloc+wanturl
            try:
                self.response = None
                if scheme == 'http':
                    self.connection = btHTTPcon(desthost)
                else:
                    self.connection = btHTTPScon(desthost)
                self.connection.request('GET', desturl, None,
                                    { 'Host': netloc, 'User-Agent': VERSION,
                                      'Accept-Encoding': 'gzip' } )
                self.response = self.connection.getresponse()
            except HTTPException, e:
                raise IOError, ('http error', str(e))
            status = self.response.status
            if status in (301, 302):
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
        except Exception, e:
            if not silent:
                print_exc()
                print >>sys.stderr,"zurllib: URL was", url, e


    def read(self):
        if self.error_return:
            return self.error_return
        return self._read()

    def _read(self):
        data = self.response.read()
        if self.response.getheader('Content-Encoding', '').find('gzip') >= 0:
            try:
                compressed = StringIO(data)
                f = GzipFile(fileobj = compressed)
                data = f.read()
            except:
                raise IOError, ('http error', 'got corrupt response')
        return data

    def close(self):
        self.connection.close()

