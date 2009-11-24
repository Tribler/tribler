# BAD CLIENT: SENDS 
# GET /path\r\n
# HTTP/1.1\r\n
# Host: localhost:6878\r\n
# \r\n
#
# Then Python HTTP server doesn't correctly send headers.

import sys
import socket
import urlparse
import time

class PluginEmulator:
    
    def __init__(self,port,cmd,param):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1',port))
        msg = cmd+' '+param+'\r\n'
        s.send(msg)
        #s.close()
        while True:
            data = s.recv(1024)
            print >>sys.stderr,"pe: Got BG command",data
            if len(data) == 0:
                print >>sys.stderr,"pe: BG closes IC"
                return
            elif data.startswith("PLAY"):
                break

        url = data[len("PLAY "):]
        p = urlparse.urlparse(url)
        path  = p.path
        
        #s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #s2.connect(('127.0.0.1',6878))
        #s2.send("GET "+path+"HTTP/1.1\r\nHost: localhost:6878\r\n\r\n")
        #data = s2.recv(100)
        #print >>sys.stderr,"pe: Got HTTP command",data
        time.sleep(10000)
            
            
#pe = PluginEmulator(62062,"START","http://www.cs.vu.nl/~arno/vod/route2.tstream")
#pe = PluginEmulator(62062,"START","http://www.legaltorrents.com/get/140-big-buck-bunny-480p.torrent")     
pe = PluginEmulator(62062,"START","http://trial.p2p-next.org/torrents/TEDx720p2.avi.tstream")        