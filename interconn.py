import wx
import sys
import socket

from Utility.helpers import getSocket


################################################################
#
# Class: ServerListener
#
# Single Instance opens local port for taking parameter from other instances
#
################################################################
class ServerListener:
    def __init__(self, utility):
        self.utility = utility
        self.s = None
        HOST = '127.0.0.1'       # Symbolic name meaning the local host

        PORT = 56766             # Arbitrary non-privileged port       
        self.s = getSocket(HOST, PORT, "server")
        if self.s is None:
            msg = 'Tribler-already-running check: Could not open socket '+str(PORT)+' on localhost'
            sys.stderr.write(msg) # No way
            ## Arno: we now have a popup for startup errors
            #sys.exit(1)
            raise socket.error(msg)
        
    def start(self):
        while 1:
            try:
                conn, addr = self.s.accept()
                data = conn.recv(1024)
                conn.close()
                # If the quitting flag has been set, or we've been asked to close
                if self.utility.abcquitting or data == "Close Connection":
                    self.s.close()
                    break
#                elif data == "KEEPALIVE":
#                    # just making sure the connection doesn't timeout...
#                    pass
                elif data == "Raise Window":
                    self.utility.frame.onTaskBarActivate()
                else:
                    self.utility.queue.addtorrents.AddTorrentFromFile(data)
            except wx.PyDeadObjectError:
                toosoontext = "\nTried to start ABC again too soon after exiting!\n" + \
                              "(Wait for ABC to finish shutting down, then try again)\n"
                sys.stderr.write(toosoontext)
                break
#        self.utility.abcdonequitting = True
#        sys.stderr.write("\nDone shutting down serverlistener")

    
################################################################
#
# Class: ClientPassParam
#
# Other instances except server pass parameter to a
# Single Instance process and close inmediately
#
################################################################
def ClientPassParam(params, ignoreError = False):
    HOST = '127.0.0.1'               # The remote host
    PORT = 56766                     # The same port as used by the server
    # Keep on trying...
    # (at least moreso than before)
    s = getSocket(HOST, PORT, 15)
    if s is None:
        if ignoreError:
            return
        print 'Tribler-already-running check: could not open socket'
#        sys.stderr.write("Could not open socket\n")
#        sys.stderr.write("--Trying to send params: (" + params + ")\n")
        sys.exit(1)        
            
    # if request is not close connection request
    # so it's torrent request copy .torrent
    # in backup torrent folder
    ##############################################
    if not params:
        s.send("Raise Window")
    else:
        s.send(params)
    s.close()
