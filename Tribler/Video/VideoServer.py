# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information
#
# TODO: Allow only 1 GET request

import os,sys,string,time
import socket
import SocketServer
import BaseHTTPServer
from SocketServer import ThreadingMixIn
import thread
from threading import RLock,Thread,currentThread
from traceback import print_exc

DEBUG = True
        

class VideoHTTPServer(ThreadingMixIn,BaseHTTPServer.HTTPServer):
#class VideoHTTPServer(BaseHTTPServer.HTTPServer):
    __single = None
    
    def __init__(self,port):
        if VideoHTTPServer.__single:
            raise RuntimeError, "HTTPServer is Singleton"
        VideoHTTPServer.__single = self 

        self.port = port
        BaseHTTPServer.HTTPServer.__init__( self, ("",self.port), SimpleServer )
        self.daemon_threads = True
        self.allow_reuse_address = True
        #self.request_queue_size = 10

        self.lock = RLock()        
        
        self.stream = None
        self.mimetype = None
        self.length = None
        
        self.errorcallback = None
        self.statuscallback = None
        
    def getInstance(*args, **kw):
        if VideoHTTPServer.__single is None:
            VideoHTTPServer(*args, **kw)
        return VideoHTTPServer.__single
    getInstance = staticmethod(getInstance)
    
    def background_serve( self ):
        name = "VideoHTTPServerThread-1"
        self.thread2 = Thread(target=self.serve_forever,name=name)
        self.thread2.setDaemon(True)
        self.thread2.start()
        #thread.start_new_thread( self.serve_forever, () )

    def register(self,errorcallback,statuscallback):
        self.errorcallback = errorcallback
        self.statuscallback = statuscallback

    def set_inputstream(self,mimetype,stream,length):
        self.lock.acquire()
        self.stream = stream
        self.mimetype = mimetype
        self.length = length
        self.lock.release()
        
    def get_inputstream(self):
        self.lock.acquire()
        ret = (self.mimetype,self.stream,self.length)
        self.lock.release()
        return ret

    def get_port(self):
        return self.port

    def shutdown(self):
        if DEBUG:
            print >>sys.stderr,"videoserv: Shutting down HTTP"
        # Stop by closing listening socket of HTTP server
        self.socket.close()


class SimpleServer(BaseHTTPServer.BaseHTTPRequestHandler):

    """
    def __init__(self,request, client_address, server):
        self.count = 0
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self,request,client_address,server)
    """

    def do_GET(self):
        try:
            if DEBUG:
                print >>sys.stderr,"videoserv: do_GET: Got request",self.path,self.headers.getheader('range')
                
            #if self.server.statuscallback is not None:
            #    self.server.statuscallback("Player ready - Attempting to load file...")
            (mimetype,stream,length) = self.server.get_inputstream()
            if stream is None:
                if DEBUG:
                    print >>sys.stderr,"videoserv: do_GET: No data to serve request"
                return
            print >>sys.stderr,"videoserv: MIME type is",mimetype,"length",length
    
            # h4x0r until we merge patches from player-release-0.0 branch
            if mimetype is None and length is None:
                mimetype = 'video/mp2t'
            elif mimetype is None:
                mimetype = 'video/mpeg'
                
            #mimetype = 'application/x-mms-framed'
            #mimetype = 'video/H264'
                
            print >>sys.stderr,"videoserv: final MIME type is",mimetype,"length",length
    
            firstbyte = 0
            if length is not None:
                lastbyte = length-1
    
            range = self.headers.getheader('range')
            if range:
                type, seek = string.split(range,'=')
                firstbyte, lastbyte = string.split(seek,'-')
        
            stream.seek( int(firstbyte) )
    
            self.send_response(200)
            self.send_header("Content-Type", mimetype)
            if length is not None:
                self.send_header("Content-Length", length)
            else:
                self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            count = 0
            while True:
                data = stream.read()
                if length is None:
                    # If length unknown, use chunked encoding
                    # http://www.ietf.org/rfc/rfc2616.txt, $3.6.1 
                    self.wfile.write("%x\r\n" % (len(data)))
                if len(data) > 0: 
                    self.wfile.write(data)
                if length is None:
                    # If length unknown, use chunked encoding
                    self.wfile.write("\r\n")

                if len(data) == 0:
                    if DEBUG:
                        print >>sys.stderr,"videoserv: stream.read no data" 
                    break
                    
                count += 1
                if count % 100 == 0:
                    print >>sys.stderr,"videoserv: writing data % 100"
                
            if DEBUG:
                print >>sys.stderr,"videoserv: do_GET: Done sending data"
    
            stream.close()
            if self.server.statuscallback is not None:
                self.server.statuscallback("Done")
            #f.close()
            
        except Exception,e:
            if DEBUG:
                print >>sys.stderr,"videoserv: Error occured while serving"
            print_exc()
            self.error(e,self.path)


    def error(self,e,url):
        if self.server.errorcallback is not None:
            self.server.errorcallback(e,url)
        else:
            print_exc()
        if self.server.statuscallback is not None:
            self.server.statuscallback("Error playing video:"+str(e))
