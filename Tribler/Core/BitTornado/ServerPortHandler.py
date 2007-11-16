# Written by John Hoffman
# see LICENSE.txt for license information

import sys
from cStringIO import StringIO
from binascii import b2a_hex, b2a_uu 
#from RawServer import RawServer
from sha import sha
try:
    True
except:
    True = 1
    False = 0

# 2fastbt_
from BT1.Encrypter import protocol_name
from traceback import print_exc,print_stack
# _2fastbt

def toint(s):
    return long(b2a_hex(s), 16)

default_task_id = []

DEBUG = True

def show(s):
    for i in xrange(len(s)): 
        print ord(s[i]),
    print

class SingleRawServer:
    def __init__(self, info_hash, multihandler, doneflag, protocol):
        self.info_hash = info_hash
        self.doneflag = doneflag
        self.protocol = protocol
        self.multihandler = multihandler
        self.rawserver = multihandler.rawserver
        self.finished = False
        self.running = False
        self.handler = None
        self.taskqueue = []

    def shutdown(self):
        if not self.finished:
            self.multihandler.shutdown_torrent(self.info_hash)

    def _shutdown(self):
        if not self.finished:
            self.finished = True
            self.running = False
            self.rawserver.kill_tasks(self.info_hash)
            if self.handler:
                self.handler.close_all()

    def _external_connection_made(self, c, options, msg_remainder):
        if DEBUG:
            print >> sys.stderr,"SingleRawServer: _external_conn_made, running?",self.running
        if self.running:
            c.set_handler(self.handler)
            self.handler.externally_handshaked_connection_made(
                c, options, msg_remainder)

    ### RawServer functions ###

    def add_task(self, func, delay=0, id = default_task_id):
        if id is default_task_id:
            id = self.info_hash
        if not self.finished:
            self.rawserver.add_task(func, delay, id)

#    def bind(self, port, bind = '', reuse = False):
#        pass    # not handled here
        
    def start_connection(self, dns, handler = None):
        if not handler:
            handler = self.handler
        c = self.rawserver.start_connection(dns, handler)
        return c

#    def listen_forever(self, handler):
#        pass    # don't call with this
    
    def start_listening(self, handler):
        self.handler = handler    # Encoder
        self.running = True
        return self.shutdown    # obviously, doesn't listen forever

    def is_finished(self):
        return self.finished

    def get_exception_flag(self):
        return self.rawserver.get_exception_flag()

class NewSocketHandler:     # hand a new socket off where it belongs
    def __init__(self, multihandler, connection):    # connection: SingleSocket
        self.multihandler = multihandler
        self.connection = connection
        connection.set_handler(self)
        self.closed = False
        self.buffer = StringIO()
        self.complete = False
        self.next_len, self.next_func = 1, self.read_header_len
        self.multihandler.rawserver.add_task(self._auto_close, 15)

    def _auto_close(self):
        if not self.complete:
            self.close()
        
    def close(self):
        if not self.closed:
            self.connection.close()
            self.closed = True

#   header format:
#        connection.write(chr(len(protocol_name)) + protocol_name + 
#            (chr(0) * 8) + self.encrypter.download_id + self.encrypter.my_id)

    # copied from Encrypter and modified
    
    def read_header_len(self, s):
        if s == 'G':
            self.protocol = 'HTTP'
            self.firstbyte = s
            if DEBUG:
                print >>sys.stderr,"NewSocketHandler: Got HTTP connection"
            return True
        else:
            l = ord(s)
            return l, self.read_header

    def read_header(self, s):
        self.protocol = s
        return 8, self.read_reserved

    def read_reserved(self, s):
        self.options = s
        return 20, self.read_download_id

    def read_download_id(self, s):
        if DEBUG:
            print >>sys.stderr,"NewSocketHandler: Swarm id is",`s`,self.connection.socket.getpeername()
        if self.multihandler.singlerawservers.has_key(s):
            if self.multihandler.singlerawservers[s].protocol == self.protocol:
                if DEBUG:
                    print >>sys.stderr,"NewSocketHandler: Found rawserver for swarm id"
                return True
        if DEBUG:
            print >>sys.stderr,"NewSocketHandler: No rawserver found for swarm id",`s`
        return None

    def read_dead(self, s):
        return None

    def data_came_in(self, garbage, s):
#        if DEBUG:
#            print "NewSocketHandler data came in", sha(s).hexdigest()
        while 1:
            if self.closed:
                return
            i = self.next_len - self.buffer.tell()
            if i > len(s):
                self.buffer.write(s)
                return
            self.buffer.write(s[:i])
            s = s[i:]
            m = self.buffer.getvalue()
            self.buffer.reset()
            self.buffer.truncate()
            try:
                x = self.next_func(m)
            except:
                self.next_len, self.next_func = 1, self.read_dead
                raise
            if x is None:
                if DEBUG:
                    print >> sys.stderr,"NewSocketHandler:",self.next_func,"returned None"
                self.close()
                return
            if x == True:       # ready to process
                if self.protocol == 'HTTP':
                    if DEBUG:
                        print >> sys.stderr,"NewSocketHandler: Reporting HTTP connection" 
                    self.multihandler.httphandler.external_connection_made(self.connection)
                    self.multihandler.httphandler.data_came_in(self.connection,self.firstbyte)
                    self.multihandler.httphandler.data_came_in(self.connection,s)
                else:
                    if DEBUG:
                        print >> sys.stderr,"NewSocketHandler: Reporting connection via",self.multihandler.singlerawservers[m]._external_connection_made
                    self.multihandler.singlerawservers[m]._external_connection_made(
                        self.connection, self.options, s)
                self.complete = True
                return
            self.next_len, self.next_func = x

    def connection_flushed(self, ss):
        pass

    def connection_lost(self, ss):
        self.closed = True

class MultiHandler:
    def __init__(self, rawserver, doneflag):
        self.rawserver = rawserver
        self.masterdoneflag = doneflag
        self.singlerawservers = {}
        self.connections = {}
        self.taskqueues = {}
        self.httphandler = None

    def newRawServer(self, info_hash, doneflag, protocol=protocol_name):
        new = SingleRawServer(info_hash, self, doneflag, protocol)
        self.singlerawservers[info_hash] = new
        return new

    def shutdown_torrent(self, info_hash):
        self.singlerawservers[info_hash]._shutdown()
        del self.singlerawservers[info_hash]

    def listen_forever(self):
        if DEBUG:
            print >>sys.stderr,"MultiHandler: listen_forever()"
        self.rawserver.listen_forever(self)
        for srs in self.singlerawservers.values():
            srs.finished = True
            srs.running = False
            srs.doneflag.set()

    def set_httphandler(self,httphandler):
        self.httphandler = httphandler
        
    ### RawServer handler functions ###
    # be wary of name collisions

    def external_connection_made(self, ss):
        # ss: SingleSocket
        NewSocketHandler(self, ss)
