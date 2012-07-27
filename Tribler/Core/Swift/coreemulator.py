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
        #s.connect(('130.37.193.64',port))
        s.setblocking(0)
            
        if len(param) > 0:
            msg = cmd+' '+param+'\r\n'
        else:
            msg = cmd+'\r\n'
            
        time.sleep(1)
            
        print >>sys.stderr,"SENDING",msg
        s.send(msg)

        #msg2 = "SETMOREINFO 836e482197b3db76914a19fd4ae6debd725c3284 1\r\n";
        #s.send(msg2)

        #msg2 = "MAXSPEED 836e482197b3db76914a19fd4ae6debd725c3284 DOWNLOAD 512\r\n";
        #s.send(msg2)


        #s.close()
        count = 0
        flag = False
        while True:
            try:
                data = s.recv(1024)
            except:
                data = "#"
            
            print >>sys.stderr,"pe: Got BG ",data
            if len(data) == 0:
                print >>sys.stderr,"pe: BG closes IC"
                return

            lines = data.splitlines()
            for line in lines:
                if line.startswith("PLAY"):
                    words = line.split()
                    url = words[2]
                    p = urlparse.urlparse(url)
                    path  = p[2]
                    #self.retrieve_path(path,recurse=False)
                    break

            """
            count += 1
            if count == 10:
                msg2 = "START tswift://130.161.211.239:7758/836e482197b3db76914a19fd4ae6debd725c3281 dest1\r\n";
                s.send(msg2)
                msg2 = "START tswift://130.161.211.239:7758/836e482197b3db76914a19fd4ae6debd725d3284 dest2\r\n";
                s.send(msg2)
                msg2 = "START tswift://tracker3.p2p-next.org:20021/700c6102c087834fa75c1676c17610cad4276a6e dest3\r\n";
                s.send(msg2)
                msg2 = "START tswift://tracker3.p2p-next.org:20021/700c6102c087834fa75c1676c17610cad4276a6f dest4\r\n";
                s.send(msg2)
                msg2 = "START tswift://tracker2.p2p-next.org:20021/700c6102c087834fa75c1676c17610cad4272a6f dest5\r\n";
                s.send(msg2)
                
            if count == 20:
                msg2 = "START tswift://tracker2.p2p-next.org:20021/bbcc6102c087834fa75c1676c17610cad4272a60 dest6\r\n";
                s.send(msg2)
                
            time.sleep(.2)
                
            
            #s.send(msg)
            """
            time.sleep(.5)

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
        s2.connect(('127.0.0.1',8192))
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

#pe =  PluginEmulator(62062,"START",sys.argv[1])
#pe =  PluginEmulator(27758,"START","tswift://130.161.211.239:7758/836e482197b3db76914a19fd4ae6debd725c3284/go-open-vol-1/go-open-episode-01.mp4 destination")
#pe =  PluginEmulator(27758,"START","tswift://127.0.0.1:7758/836e482197b3db76914a19fd4ae6debd725c3284/go-open-vol-1/go-open-episode-01.mp4 destination")
pe =  PluginEmulator(37758,"START","tswift://127.0.0.1:7758/6d29cbb65b1f77d7a1860d6b1d375d152967ad7d C:\\Users\\arno\\Desktop\\TriblerDownloads")
#pe =  PluginEmulator(4567,"SHUTDOWN","")
