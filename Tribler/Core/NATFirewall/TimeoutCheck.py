from socket import *
from types import StringType, ListType, TupleType, DictType, IntType
import random
import sys
import time

from Tribler.Core.BitTornado.bencode import bencode, bdecode

DEBUG = False

def pingback(udpsock, pingbacksrvr):

    udpsock.settimeout(200)

    while 1:

        reply = None
        rcvaddr = None

        try:
            reply, rcvaddr = udpsock.recvfrom(1024)

        except timeout:

            if udpsock:
                udpsock.close()

            if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "UDP connection to the pingback server has timed out"
            break

        if reply:
            data = bdecode(reply)

            if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "<-", data

            if data == "ping":
                if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "-> pong"
                udpsock.sendto(bencode("pong"), pingbacksrvr)


# Main method of the library: launches nat-timeout discovery algorithm
def timeout_check(pingbacksrvr):

    to = -1 # timeout

    # Setup sockets
    tcpsock = socket(AF_INET, SOCK_STREAM)
    tcpsock.settimeout(600)

    try:
        tcpsock.connect(pingbacksrvr)

    except timeout:
        if tcpsock:
            tcpsock.close()

        if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "TCP connection to the pingback server has timed out"
        return to

    except error, (errno, strerror):
        if tcpsock:
            tcpsock.close()

        if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "Could not connect socket: %s" % (strerror)
        return to

    udpsock = socket(AF_INET, SOCK_DGRAM)

    # Generate random ID
    myid = random.sample(xrange(10000000),1)[0]

    # Create and send message
    myidData = ("GET_MY_TIMEOUT", myid)
    myidMsg = bencode(myidData)
    tcpsock.send(myidMsg)
    time.sleep(1)
    udpsock.sendto(myidMsg, pingbacksrvr)
    pingback(udpsock, pingbacksrvr)

    # Wait for response
    try:
        rcvMsg = tcpsock.recv(1024)

    except timeout:
        if tcpsock:
            tcpsock.close()
        if udpsock:
            udpsock.close()

        if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "TCP connection to the pingback server has timed out"
        return to

    if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", rcvMsg

    try:
        data = bdecode(rcvMsg)
    except ValueError:
        if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "bad encoded data"
        udpsock.close()
        tcpsock.close()
        return to

    if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", data
    time.sleep(10)

    udpsock.close()
    tcpsock.close()

    if type(data) is TupleType or type(data) is ListType and len(data) is 2:
        if data[0] == "TIMEOUT":
            if DEBUG: print >> sys.stderr, "TIMEOUTCHECK:", "TIMEOUT response received"

            if type(data[1]) is IntType:
                to = data[1]

    return to
