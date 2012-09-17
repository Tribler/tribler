# Written by Arno Bakker, Diego Rabaioli
# see LICENSE.txt for license information
""" Communication layer between other instance or Web plugin e.g. for starting Downloads. """

# Protocol V1: Tribler 4.5.0:
# - [4 byte length of cmd][cmd]
# Protocol V2: SwarmPlugin
# - [cmd]\r\n
#
#
import sys
import socket
from traceback import print_exc
from threading import Thread, Event, currentThread
from Tribler.Core.BitTornado.RawServer import RawServer
try:
    prctlimported = True
    import prctl
except ImportError,e:
    prctlimported = False

DEBUG = False

class Instance2InstanceServer(Thread):
    
    def __init__(self,i2iport,connhandler,timeout=300.0):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName('Instance2Instance'+self.getName())
        self.i2iport = i2iport
        self.connhandler = connhandler
        

        self.i2idoneflag = Event()
        
        self.rawserver = RawServer(self.i2idoneflag,
                                   timeout/5.0, 
                                   timeout,
                                   ipv6_enable = False,
                                   failfunc = self.rawserver_fatalerrorfunc,
                                   errorfunc = self.rawserver_nonfatalerrorfunc)
        self.rawserver.add_task(self.rawserver_keepalive,1)
        # Only accept local connections
        self.rawserver.bind(self.i2iport,bind=['127.0.0.1'],reuse=True) 
        
    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time 
        
        Called by Instance2Instance thread """
        self.rawserver.add_task(self.rawserver_keepalive,1)
        
        
    def shutdown(self):
        self.connhandler.shutdown()
        self.i2idoneflag.set()

    #
    # Following methods are called by Instance2Instance thread
    #
    def rawserver_fatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"i2is: RawServer fatal error func called",e
        print_exc()

    def rawserver_nonfatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"i2is: RawServer non fatal error func called",e
            print_exc()
        # Could log this somewhere, or phase it out

    def run(self):
        
        if prctlimported:
            prctl.set_name("Tribler"+currentThread().getName())
        
        try:
            try:
                if DEBUG:
                    print >>sys.stderr,"i2is: Ready to receive remote commands on",self.i2iport
                self.rawserver.listen_forever(self)
            except:
                print_exc()    
        finally:
            self.rawserver.shutdown()

    def external_connection_made(self,s):
        try:
            if DEBUG:
                print >>sys.stderr,"i2is: external_connection_made" 
            self.connhandler.external_connection_made(s)
        except:
            print_exc()
            s.close()

    def connection_flushed(self,s):
        self.connhandler.connection_flushed(s)
    
    def connection_lost(self,s):
        if DEBUG:
            print >>sys.stderr,"i2is: connection_lost ------------------------------------------------"
        self.connhandler.connection_lost(s)
        
    def data_came_in(self, s, data):
        try:
            self.connhandler.data_came_in(s,data)
        except:
            print_exc()
            s.close()

    def add_task(self,func,t):
        self.rawserver.add_task(func,t)

    def start_connection(self,dns):
        return self.rawserver.start_connection_raw(dns,handler=self.connhandler)



class InstanceConnectionHandler:
    def __init__(self,readlinecallback=None):
        self.readlinecallback = readlinecallback
        self.singsock2ic = {} # Maps Tribler/Core/BitTornado/SocketHandler.py:SingleSocket to InstanceConnection
    
    def set_readlinecallback(self,readlinecallback):
        self.readlinecallback = readlinecallback
    
    def external_connection_made(self,s):
        # Extra check in case bind() no work
        if DEBUG:
            print >>sys.stderr,"i2is: ich: ext_conn_made"
        peername = s.get_ip()
        if peername != "127.0.0.1":
            print >>sys.stderr,"i2is: ich: ext_conn_made: Refusing non-local connection from",peername
            s.close()

        ic = InstanceConnection(s,self,self.readlinecallback)
        self.singsock2ic[s] = ic

    def connection_flushed(self,s):
        pass
    
    def connection_lost(self,s):
        """ Called when peer closes connection and when we close the connection """
        if DEBUG:
            print >>sys.stderr,"i2is: ich: connection_lost ------------------------------------------------"
        
        # Extra check in case bind() no work
        peername = s.get_ip()
        if peername != "127.0.0.1":
            print >>sys.stderr,"i2is: ich: connection_lost: Refusing non-local connection from",peername
            return

        del self.singsock2ic[s]
        
    def data_came_in(self,s, data):
        if DEBUG:
            print >>sys.stderr,"i2is: ich: data_came_in"

        ic = self.singsock2ic[s]
        try:
            ic.data_came_in(data)
        except:
            print_exc()

    def shutdown(self):
        for ic in self.singsock2ic.values():
            ic.shutdown()

    def set_server(self,i2is):
        self.i2is = i2is

    def start_connection(self,dns,ic):
        s = self.i2is.start_connection(dns)
        self.singsock2ic[s] = ic
        return s


class InstanceConnection:
    def __init__( self, singsock, connhandler, readlinecallback):
        self.singsock = singsock
        self.connhandler = connhandler
        self.readlinecallback = readlinecallback
        self.buffer = ''

    
    def data_came_in(self,data):
        """ Read \r\n ended lines from data and call readlinecallback(self,line) """
        # data may come in in parts, not lines! Or multiple lines at same time
        
        if DEBUG:
            print >>sys.stderr,"i2is: ic: data_came_in",`data`,len(data)

        if len(self.buffer) == 0:
            self.buffer = data
        else:
            self.buffer = self.buffer + data
        self.read_lines()
        
    def read_lines(self):
        while True:
            cmd, separator, self.buffer = self.buffer.partition("\r\n")
            if separator:
                if self.readlinecallback(self, cmd):
                    # 01/05/12 Boudewijn: when a positive value is returned we immediately return to
                    # allow more bytes to be pushed into the buffer
                    self.buffer = "".join((cmd, separator, self.buffer))

            else:
                self.buffer = cmd
                break
    
    def write(self,data):
        if self.singsock is not None:
            self.singsock.write(data)            
    
    def close(self):
        if self.singsock is not None:
            self.singsock.close()
            self.connhandler.connection_lost(self.singsock)
            self.singsock = None
        

class Instance2InstanceClient:
    
    def __init__(self,port,cmd,param):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1',port))
        msg = cmd+' '+param+'\r\n'
        s.send(msg)
        s.close()
        
        
