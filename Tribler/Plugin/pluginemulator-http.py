
import sys
import socket
import urlparse
import time


class PluginEmulator:

    def __init__(self, port, cmd, param):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', port))
        msg = cmd + ' ' +param+'\r\n'
        s.send(msg)

        while True:
            data = s.recv(1024)
            print >>sys.stderr, "pe: Got BG command", data
            if len(data) == 0:
                print >>sys.stderr, "pe: BG closes IC"
                return
            elif data.startswith("PLAY"):

                f = open("bla.bat", "wb")
                f.write("\"\\Program Files\\GnuWin32\\bin\\wget.exe\" -S " + data[4:])
                f.close()
                break

        time.sleep(1000)
        return

        # url = data[len("PLAY "):-2]
        url = data[len("PLAY "):]
        p = urlparse.urlparse(url)
        path = p[2]

        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.connect(('127.0.0.1', 6878))
        cmd = "GET " + path +" HTTP/1.1\r\nHost: localhost:6878\r\n\r\n\r\n"
        print >>sys.stderr, "SENDING CMD", cmd
        s2.send(cmd)
        for i in range(0, 2):
            data = s2.recv(256)
            print >>sys.stderr, "pe: Got HTTP command", repr(data)
            if len(data) == 0:
                break

        print >>sys.stderr, "pe: Sleeping"
        time.sleep(100)


# pe = PluginEmulator(62062,"START","http://www.cs.vu.nl/~arno/vod/route2.tstream")
pe = PluginEmulator(62062, "START", "file:/Build/trans-release-0.1/stroom.ogg.tstream")
