# Written by Bram Cohen
# see LICENSE.txt for license information

from cStringIO import StringIO
from sys import stdout
import time
from clock import clock
from gzip import GzipFile
try:
    True
except:
    True = 1
    False = 0

DEBUG = False

weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

months = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

class HTTPConnection:
    def __init__(self, handler, connection):
        self.handler = handler
        self.connection = connection
        self.buf = ''
        self.closed = False
        self.done = False
        self.donereading = False
        self.next_func = self.read_type

    def get_ip(self):
        return self.connection.get_ip()

    def data_came_in(self, data):
        if self.donereading or self.next_func is None:
            return True
        self.buf += data
        while True:
            try:
                i = self.buf.index('\n')
            except ValueError:
                return True
            val = self.buf[:i]
            self.buf = self.buf[i+1:]
            self.next_func = self.next_func(val)
            if self.donereading:
                return True
            if self.next_func is None or self.closed:
                return False

    def read_type(self, data):
        self.header = data.strip()
        words = data.split()
        if len(words) == 3:
            self.command, self.path, garbage = words
            self.pre1 = False
        elif len(words) == 2:
            self.command, self.path = words
            self.pre1 = True
            if self.command != 'GET':
                return None
        else:
            return None
        if self.command not in ('HEAD', 'GET'):
            return None
        self.headers = {}
        return self.read_header

    def read_header(self, data):
        data = data.strip()
        if data == '':
            self.donereading = True
            if self.headers.get('accept-encoding','').find('gzip') > -1:
                self.encoding = 'gzip'
            else:
                self.encoding = 'identity'
            r = self.handler.getfunc(self, self.path, self.headers)
            if r is not None:
                self.answer(r)
            return None
        try:
            i = data.index(':')
        except ValueError:
            return None
        self.headers[data[:i].strip().lower()] = data[i+1:].strip()
        if DEBUG:
            print data[:i].strip() + ": " + data[i+1:].strip()
        return self.read_header

    def answer(self, (responsecode, responsestring, headers, data)):
        if self.closed:
            return
        if self.encoding == 'gzip':
            compressed = StringIO()
            gz = GzipFile(fileobj = compressed, mode = 'wb', compresslevel = 9)
            gz.write(data)
            gz.close()
            cdata = compressed.getvalue()
            if len(cdata) >= len(data):
                self.encoding = 'identity'
            else:
                if DEBUG:
                   print "Compressed: %i  Uncompressed: %i\n" % (len(cdata),len(data))
                data = cdata
                headers['Content-Encoding'] = 'gzip'

        # i'm abusing the identd field here, but this should be ok
        if self.encoding == 'identity':
            ident = '-'
        else:
            ident = self.encoding
        self.handler.log( self.connection.get_ip(), ident, '-',
                          self.header, responsecode, len(data),
                          self.headers.get('referer','-'),
                          self.headers.get('user-agent','-') )
        self.done = True
        r = StringIO()
        r.write('HTTP/1.0 ' + str(responsecode) + ' ' + 
            responsestring + '\r\n')
        if not self.pre1:
            headers['Content-Length'] = len(data)
            for key, value in headers.items():
                r.write(key + ': ' + str(value) + '\r\n')
            r.write('\r\n')
        if self.command != 'HEAD':
            r.write(data)
        self.connection.write(r.getvalue())
        if self.connection.is_flushed():
            self.connection.shutdown(1)

class HTTPHandler:
    def __init__(self, getfunc, minflush):
        self.connections = {}
        self.getfunc = getfunc
        self.minflush = minflush
        self.lastflush = clock()

    def external_connection_made(self, connection):
        self.connections[connection] = HTTPConnection(self, connection)

    def connection_flushed(self, connection):
        if self.connections[connection].done:
            connection.shutdown(1)

    def connection_lost(self, connection):
        ec = self.connections[connection]
        ec.closed = True
        del ec.connection
        del ec.next_func
        del self.connections[connection]

    def data_came_in(self, connection, data):
        c = self.connections[connection]
        if not c.data_came_in(data) and not c.closed:
            c.connection.shutdown(1)

    def log(self, ip, ident, username, header,
            responsecode, length, referrer, useragent):
        year, month, day, hour, minute, second, a, b, c = time.localtime(time.time())
        print '%s %s %s [%02d/%3s/%04d:%02d:%02d:%02d] "%s" %i %i "%s" "%s"' % (
            ip, ident, username, day, months[month], year, hour,
            minute, second, header, responsecode, length, referrer, useragent)
        t = clock()
        if t - self.lastflush > self.minflush:
            self.lastflush = t
            stdout.flush()
