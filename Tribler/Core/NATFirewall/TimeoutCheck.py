# Written by Lucia D'Acunto
# see LICENSE.txt for license information

from socket import *
import sys
import thread
import threading


DEBUG = True


to = -1 # timeout default value
lck = threading.Lock()
evnt = threading.Event()


# Sending pings to the pingback server and waiting for a reply
def pingback(ping, pingbacksrvr):

    global to, lck, evnt

    # Set up the socket
    udpsock = socket(AF_INET, SOCK_DGRAM)
    udpsock.connect(pingbacksrvr)
    udpsock.settimeout(ping+10)
    
    if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "-> ping"

    # Send the ping to the server specifying the delay of the reply
    pingMsg = (str("ping:"+str(ping)))
    udpsock.send(pingMsg)
    udpsock.send(pingMsg)
    udpsock.send(pingMsg)

    # Wait for reply from the server
    while True:

        rcvaddr = None

        try:
            reply = udpsock.recv(1024)

        except timeout: # No reply from the server: timeout passed

            if udpsock:
                udpsock.close()

            if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "UDP connection to the pingback server has timed out for ping", ping

            lck.acquire()
            evnt.set()
            evnt.clear()
            lck.release()
            break

        if DEBUG: print >> sys.stderr, pingbacksrvr
        if DEBUG: print >> sys.stderr, rcvaddr

        if reply:
            data = reply.split(':')
            if DEBUG: print >> sys.stderr, data, "received from the pingback server"

            if data[0] == "pong":
                if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "<-", data[0], "after", data[1], "seconds"
                to = ping
                if int(data[1])==145:
                    lck.acquire()
                    evnt.set()
                    evnt.clear()
                    lck.release()
                return

        return


# Main method of the library: launches nat-timeout discovery algorithm
def GetTimeout(pingbacksrvr):
    """
    Returns the NAT timeout for UDP traffic
    """
    
    pings = [25, 35, 55, 85, 115, 145]

    # Send pings and wait for replies
    for ping in pings:
        thread.start_new_thread(pingback, (ping, pingbacksrvr))

    global evnt
    evnt.wait()

    if DEBUG: print >> sys.stderr, "TIMEOUTCHECK: timeout is", to
    return to
