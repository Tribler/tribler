# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Simpler way of communicating with a separate process running swift via
# its CMDGW interface
#

import sys
from threading import Thread,Lock
import socket
from traceback import print_exc

DEBUG = False

class FastI2IConnection(Thread):
    
    def __init__(self,port,readlinecallback,closecallback):
        Thread.__init__(self)
        self.setName("FastI2I"+self.getName())
        self.setDaemon(True)

        self.port = port
        self.readlinecallback = readlinecallback
        self.closecallback = closecallback
        
        self.sock = None
        # Socket only every read by self
        self.buffer = ''
        # write lock on socket
        self.lock = Lock() 

        self.start()
        
        
    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(("127.0.0.1",self.port))
            while True:
                data = self.sock.recv(10240)
                self.data_came_in(data)
        except:
            print_exc()
            self.close()

    
    def data_came_in(self,data):
        """ Read \r\n ended lines from data and call readlinecallback(self,line) """
        # data may come in in parts, not lines! Or multiple lines at same time
        
        if DEBUG:
            print >>sys.stderr,"fasti2i: data_came_in",`data`,len(data)

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
        """ Called by any thread """
        self.lock.acquire()
        try:
            if self.sock is not None:
                self.sock.send(data)
        finally:
            self.lock.release()            
    
    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.closecallback(self.port)
            self.sock = None
            