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
                url = data[len("PLAY "):]
                p = urlparse.urlparse(url)
                path  = p.path
                readbufsize = 100
                break

        #self.retrieve_path(path,recurse=False)
        
        #s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #s2.connect(('127.0.0.1',6878))
        #s2.send("GET "+path+"HTTP/1.1\r\nHost: localhost:6878\r\n\r\n")
        #data = s2.recv(100)
        #print >>sys.stderr,"pe: Got HTTP command",data
        time.sleep(10000)


    def retrieve_path(self,path,recurse=False):
        readbufsize = 100000
        
        links = []
        print >>sys.stderr,"pe: GET",path
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.connect(('127.0.0.1',6878))
        s2.send("GET "+path+" HTTP/1.1\r\nHost: localhost:6878\r\n\r\n")
        while True:
            data = s2.recv(readbufsize)
            if len(data) == 0:
                break
            print >>sys.stderr,"pe: Got HTTP data",`data`
            
            eidx = 0
            while True:
                sidx = data.find("/hits",eidx)
                if sidx != -1:
                    eidx = data.find('"',sidx)
                    if eidx != -1:
                        hitpath = data[sidx:eidx]
                        #print >>sys.stderr,"pe: Found link",hitpath
                        links.append(hitpath)
                else:
                    break
                        
        if recurse:
            for hitpath in links:
                #hitpath = links[2][:-len("/thumbnail")]
                #print >>sys.stderr,"pe: Retrieving link",hitpath,"EOT"
                recurse = hitpath.endswith(".xml")
                
                # My dumb parser hack
                idx = hitpath.find("</MediaUri>")
                if idx != -1:
                    hitpath = hitpath[0:idx]
                print >>sys.stderr,"pe: FINAL link",hitpath,"EOT"
                self.retrieve_path(hitpath,recurse=recurse)
            
            
#pe = PluginEmulator(62062,"START","http://www.cs.vu.nl/~arno/vod/route2.tstream")
#pe = PluginEmulator(62062,"START","http://www.vuze.com/download/XUGIN6PEJJCQ5777C3WUMMBRFI6HYIHJ.torrent?referal=torrentfilelinkcdp&title=Gopher")

if len(sys.argv) < 2:
    print "Missing URL to play"
    raise SystemExit(1)

pe =  PluginEmulator(62062,"START",sys.argv[1])
