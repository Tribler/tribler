# Written by Jan David Mol, Arno Bakker
# see LICENSE.txt for license information


import os,sys,string,time
from traceback import print_exc

if sys.version.startswith("2.4"):
    os.SEEK_SET = 0
    os.SEEK_CUR = 1
    os.SEEK_END = 2

DEBUG = False

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

 
class MovieTransportStreamWrapper:
    """ Provide a file-like interface """
    def __init__(self,mt):
        self.mt = mt
        self.started = False

    def read(self,numbytes=None):
        if not self.started:
            self.mt.start(0)
            self.started = True
        if self.mt.done():
            return ''
        data = self.mt.read(numbytes)
        if data is None:
            print >>sys.stderr,"MovieTransportStreamWrapper: mt read returns None"
            data = ''
        return data

    def seek(self,pos,whence=os.SEEK_SET):
        # TODO: shift play_pos in PiecePicking + interpret whence
        print >>sys.stderr,"MovieTransportStreamWrapper: seek() CALLED",pos,"whence",whence
        self.mt.seek(pos,whence=whence)
    
    def close(self):
        self.mt.stop()
        