# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information


import os,sys,string,time
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
        self.mt.start(bytepos)
        
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


class MovieTransportStreamWrapper:
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
            print >>sys.stderr,"MovieTransportStreamWrapper: mt read returns None"
            data = ''
        self.done = self.mt.done()
        return data

    def seek(self,pos,whence=None):
        # TODO: shift play_pos in PiecePicking + interpret whence
        pass
    
    def close(self):
        self.mt.stop()
        