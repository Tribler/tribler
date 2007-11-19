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
from __init__ import read,BLOCKSIZE

DEBUG = True


class MovieTransport:
    
    def __init__(self):
        pass
        
    def start( self, bytepos = 0 ):
        pass
    
    def size(self ):
        pass

    def read(self):
        pass
        
    def stop(self):
        pass

    def done(self):
        pass
    
    def get_mimetype(self):
        pass
 
    def set_mimetype(self,mimetype):
        pass

 
class MovieFileTransport(MovieTransport):
    
    def __init__(self,videofilename,mimetype,enckey=None):
        self.videofilename = videofilename
        self.mimetype = mimetype
        self.enckey = enckey
        self.doneflag = False
        self.userpos = 0

    def start( self, bytepos = 0 ):
        """ Initialise to start playing at position `bytepos'. """
        self.userpos = bytepos
        self.file = open(self.videofilename,"rb")
        if self.userpos != 0:
            self.file.seek(self.userpos,0)
        
    def size(self ):
        statinfo = os.stat(self.videofilename)
        return statinfo.st_size

    def read(self):
        diff = self.userpos % BLOCKSIZE
        if diff != 0:
            self.file.seek(-diff,1)
        data = self.file.read(BLOCKSIZE)
        if len(data) != BLOCKSIZE:
            self.doneflag = True
            if len(data)==0:
                return None
        if self.enckey is not None:
            ret = read(data,self.enckey)
        else:
            ret = data
            
        self.userpos += len(data)-diff
        return ret[diff:]

    def stop(self):
        """ Playback is stopped. """
        self.file.close()

    def done(self):
        return self.doneflag
    
    def get_mimetype(self):
        return self.mimetype


class MovieTransportDecryptWrapper:
    """ Reads a MovieTransport from byte 0 to end and does decryption
        and the start-from-offset!=0 behaviour.
    """
    
    def __init__(self,mt,enckey):
        self.mt = mt
        self.enckey = enckey
        self.doneflag = False
        self.userpos = 0

    def start( self, bytepos = 0 ):
        """ Initialise to start playing at position `bytepos'. """
        self.userpos = bytepos
        self.mt.start(0)
        
    def size(self ):
        return self.mt.size()

    def read(self):
        diff = self.userpos % BLOCKSIZE
        data = self.mt.read(BLOCKSIZE)
        if len(data) != BLOCKSIZE:
            self.doneflag = True
            if len(data)==0:
                return None
        if self.enckey is not None:
            ret = read(data,self.enckey)
        else:
            ret = data
            
        self.userpos += len(data)-diff
        return ret[diff:]

    def stop(self):
        """ Playback is stopped. """
        self.mt.stop()

    def done(self):
        return self.mt.done()
    
    def get_mimetype(self):
        return self.mt.get_mimetype()



class MovieTransportFileLikeInterfaceWrapper:
    """ Provide a file-like interface """
    def __init__(self,mt):
        self.mt = mt
        self.started = False
        self.done = False

    def read(self,numbytes=None):
        if self.done:
            return ''
        if not self.started:
            self.mt.start(0)
        data = self.mt.read(numbytes)
        if data is None:
            print >>sys.stderr,"MovieTransportFileLikeInterfaceWrapper: mt read returns None"
            data = ''
        self.done = self.mt.done()
        return data
        
    def close(self):
        self.mt.stop()

        

class VideoHTTPServer(ThreadingMixIn,BaseHTTPServer.HTTPServer):
#class VideoHTTPServer(BaseHTTPServer.HTTPServer):
    __single = None
    
    def __init__(self):
        if VideoHTTPServer.__single:
            raise RuntimeError, "HTTPServer is Singleton"
        VideoHTTPServer.__single = self 

        self.port = 6880
        self.lock = RLock()        
        self.running = False
        self.movietransport = None
        BaseHTTPServer.HTTPServer.__init__( self, ("",self.port), SimpleServer )
        self.daemon_threads = True
        self.allow_reuse_address = True
        #self.request_queue_size = 10
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

    def set_movietransport(self,newmt):
        ret = False
        self.lock.acquire()
        if not self.running:
            self.running = True
            ret = True
        self.movietransport = newmt
        self.lock.release()
        return ret
        
    def get_movietransport(self):
        self.lock.acquire()
        ret = self.movietransport
        self.lock.release()
        return ret

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
            movie = self.server.get_movietransport()
            if movie is None:
                if DEBUG:
                    print >>sys.stderr,"videoserv: do_GET: No data to serve request"
                return
            
            #return
            
            size  = movie.size()
            mimetype = movie.get_mimetype()
            if DEBUG:
                print >>sys.stderr,"videoserv: MIME type is",mimetype
    
            firstbyte, lastbyte = 0, size-1
    
            range = self.headers.getheader('range')
            if range:
                type, seek = string.split(range,'=')
                firstbyte, lastbyte = string.split(seek,'-')
        
            movie.start( int(firstbyte) )
    
            self.send_response(200)
            self.send_header("Content-Type", mimetype)
            self.send_header("Content-Length", size)
            self.end_headers()
            
            
            #f = open("/tmp/video.data","wb")
            
            count = 0 
            
            first = True
            while not movie.done():
                data = movie.read()
                if not data:
                    if DEBUG:
                        print >>sys.stderr,"videoserv: movie.read no data" 
                    break
                try:
                    """
                    f = self.wfile.fileno()
                    print >>sys.stderr,"videoserv: fileno",f 
                    r, w, e = select([], [f], [])
                    print >>sys.stderr,"videoserv: select returned",r,w,e
                    """
                    
                    """
                    Arno: 2007-01-06: Testing packetloss: Result: good.
                    Even at 50% packet loss on the Finland 800 kbps AVI
                    VideoLan player keeps on playing.
                    
                    self.count += 1
                    if (self.count % 2) == 0:
                        print >>sys.stderr,"videoserv: NOT WRITING" 
                        continue
                    count += 1
                    if (count % 100) == 50:
                        time.sleep(10)
                    """
                    
                    ##print >>sys.stderr,"videoserv: writing",len(data) 
                    self.wfile.write(data)
                    
                    #f.write(data)
                    
                    #sleep(1)
                    """
                    if first:
                        if self.server.statuscallback is not None:
                            self.server.statuscallback("Player ready - Attempting to play file...")
                        first = False
                    """
                    
                except IOError, e:
                    if DEBUG:
                        print >>sys.stderr,"videoserv: client closed connection for ", self.path
                    print_exc(file=sys.stderr)
                    self.error(e,self.path)
                    break
                except socket.error,e:
                    print_exc(file=sys.stderr)
                    self.error(e,self.path)
                    break
                except Exception,e:
                    print_exc(file=sys.stderr)
                    self.error(e,self.path)
                    break

            if DEBUG:
                print >>sys.stderr,"videoserv: do_GET: Done sending data"
    
            movie.stop()
            if self.server.statuscallback is not None:
                self.server.statuscallback("Done")
            #f.close()
            
        except Exception,e:
            if DEBUG:
                print >>sys.stderr,"videoserv: Error occured while serving"
            ##f = open("/tmp/videoserv.log","w")
            print_exc()
            self.error(e,self.path)

            ##f.close()

    def error(self,e,url):
        if self.server.errorcallback is not None:
            self.server.errorcallback(e,url)
        else:
            print_exc()
        if self.server.statuscallback is not None:
            self.server.statuscallback("Error playing video")
