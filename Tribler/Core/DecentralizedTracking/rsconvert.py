# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Converts betweem BiTorrent/BitTornado 3.x/0.3 RawServer and BitTorrent 5.0 
# rawserver for Khashmir
#
import sys

DEBUG = False

class RawServerConverter:
    
    def __init__(self,rawserver):
        self.rs = rawserver
        
    def create_udpsocket(self,port,host):
        return self.rs.create_udpsocket(port,host)
        
    def start_listening_udp(self,serversocket,handler,context=None):
        return self.rs.start_listening_udp(serversocket,handler)
    
    def stop_listening_udp(self,serversocket):
        return self.rs.stop_listening_udp(serversocket)
        
    def add_task(self,t,func,*args,**kwargs):
        if DEBUG:
            print >>sys.stderr,"rsconvert: add_task:",func
        newf = lambda:func(*args,**kwargs)
        return self.rs._add_task(newf,t)
        
    def external_add_task(self,t,func,*args,**kwargs):
        if DEBUG:
            print >>sys.stderr,"rsconvert: external_add_task:",func
        newf = lambda:func(*args,**kwargs)
        return self.rs.add_task(newf,t)

    def listen_forever(self):
        return self.rs.listen_forever()

    def stop(self):
        self.rs.doneflag.set()
        