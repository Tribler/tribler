# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import socket
from StringIO import StringIO
from traceback import print_exc
from threading import Thread

from Tribler.Core.BitTornado.BT1.convert import tobinary,toint

def readn(s,n,buffer):
    """ read n bytes from socket stream s, using buffer as aid """
    nwant = n
    while True:
        try:
            data = s.recv(nwant)
        except socket.error, e:
            if e[0] == 10035: # WSAEWOULDBLOCK on Windows
                continue
            else:
                raise e
        if len(data) == 0:
            return data
        nwant -= len(data)
        buffer.write(data)
        if nwant == 0:
            break
    buffer.seek(0)
    data = buffer.read(n)
    buffer.seek(0)
    return data


class Instance2InstanceServer(Thread):
    
    def __init__(self,port,callback):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName('Instance2Instance'+self.getName())
        self.port = port
        self.callback = callback
        
        self.ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ss.bind(('127.0.0.1', self.port))
        self.ss.listen(1)
        
    def run(self):
        while True:
            try:
                conn, addr = self.ss.accept()
                buffer = StringIO()
                sizedata = readn(conn,4,buffer)
                size = toint(sizedata)
                msg = readn(conn,size,buffer)
                
                if msg.startswith('START '):
                    url = msg[len('START '):]
                    self.callback('START',url)
                conn.close()
                
            except:
                print_exc()
        

class Instance2InstanceClient:
    
    def __init__(self,port,cmd,param):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1',port))
        msg = cmd+' '+param
        sizedata = tobinary(len(msg))
        s.send(sizedata)
        s.send(msg)
        s.close()
        
        