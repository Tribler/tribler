
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
        
        time.sleep(1)
        s.close()
        return
        
        while True:
            data = s.recv(1024)
            print >>sys.stderr,"pe: Got BG command",data
            if len(data) == 0:
                print >>sys.stderr,"pe: BG closes IC"
                return
            elif data.startswith("PLAY"):
                break

        #url = data[len("PLAY "):-2]
        url = data[len("PLAY "):]
        p = urlparse.urlparse(url)
        path  = p.path
        
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.connect(('127.0.0.1',6878))
        cmd = "GET "+path+" HTTP/1.1\r\nHost: localhost:6878\r\n\r\n"
        print >>sys.stderr,"SENDING CMD",cmd
        s2.send(cmd)
        data = s2.recv(256)
        print >>sys.stderr,"pe: Got HTTP command",data
            
            
#pe = PluginEmulator(62062,"START","http://www.cs.vu.nl/~arno/vod/route2.tstream")
pe = PluginEmulator(62062,"START","http://www.vuze.com/download/XUGIN6PEJJCQ5777C3WUMMBRFI6HYIHJ.torrent?referal=torrentfilelinkcdp&title=Gopher")
     
        