from time import strftime
from traceback import print_exc
import socket
import sys

DEBUG = False

def coordinateHolePunching(peer1, peer2, holePunchingAddr):

    if DEBUG:
        print >> sys.stderr, "NatTraversal: coordinateHolePunching at", holePunchingAddr

    # Set up the sockets
    try :
        udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udpsock.bind(holePunchingAddr)
        udpsock.settimeout(60)

    except socket.error, (errno, strerror) :

        if udpsock :
            udpsock.close()

        if DEBUG:
            print >> sys.stderr, "NatTraversal: Could not open socket: %s" % (strerror)

        return

    if DEBUG:
        print >> sys.stderr, "NatTraversal: waiting for connection..."

    # Receive messages
    peeraddr2 = None
    while True:

        try:
            data, peeraddr1 = udpsock.recvfrom(1024)
            if not data:
                continue
            else:
                if DEBUG:
                    print >> sys.stderr, "NatTraversal:", strftime("%Y/%m/%d %H:%M:%S"), "...connected from: ", peeraddr1
                if peeraddr2 == None:
                    peeraddr2 = peeraddr1
                elif peeraddr2 != peeraddr1:        
                    udpsock.sendto(peeraddr1[0] + ":" + str(peeraddr1[1]), peeraddr2)
                    udpsock.sendto(peeraddr1[0] + ":" + str(peeraddr1[1]), peeraddr2)
                    udpsock.sendto(peeraddr1[0] + ":" + str(peeraddr1[1]), peeraddr2)
                    udpsock.sendto(peeraddr2[0] + ":" + str(peeraddr2[1]), peeraddr1)
                    udpsock.sendto(peeraddr2[0] + ":" + str(peeraddr2[1]), peeraddr1)
                    udpsock.sendto(peeraddr2[0] + ":" + str(peeraddr2[1]), peeraddr1)
                    break

        except socket.timeout, error:
            if DEBUG:
                print >> sys.stderr, "NatTraversal: timeout with peers", error
            udpsock.close()
            break

    # Close socket
    udpsock.close()

def tryConnect(coordinator):
    
    # Set up the socket
    udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpsock.settimeout(5)

    # Send messages
    udpsock.sendto("ping",coordinator)
    udpsock.sendto("ping",coordinator)
    udpsock.sendto("ping",coordinator)
    if DEBUG:
        print >> sys.stderr, "NatTraversal: sending ping to ", coordinator

    # Wait for response from the coordinator

    while True:
        data = None
        addr = None
        try:
            data, addr = udpsock.recvfrom(1024)
        except socket.timeout, (strerror):
            if DEBUG:
                print >> sys.stderr, "NatTraversal: timeout with coordinator"
            return "ERR"

        if addr == coordinator:
            if DEBUG:
                print >> sys.stderr, "NatTraversal: received", data, "from coordinator"
            break

        if DEBUG:
            print >> sys.stderr, "NatTraversal: received", data, "from", addr
            
    #success = False
    #try:
    #    host, port = data.split(":")
    #except:
    #    print_exc()
    #    print >> sys.stderr, "NatCheckMsgHandler: error in received data:", data
    #    return success
    # peer = (host, int(port))
    # for i in range(3):
    #     udpsock.sendto("hello",peer)
    #     udpsock.sendto("hello",peer)
    #     udpsock.sendto("hello",peer)

    #     try:
    #         data, addr = udpsock.recvfrom(1024)

    #     except socket.timeout, (strerror):
    #         if DEBUG:
    #             print >> sys.stderr, "NatTraversal: first timeout", strerror
    #             print >> sys.stderr, "NatTraversal: resend"

    #     else:
    #         success = True
    #         break

    try:
        host, port = data.split(":")
    except:
        print_exc()
        print >> sys.stderr, "NatCheckMsgHandler: error in received data:", data
        return "ERR"

    peer = (host, int(port))
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)

    # Wait for response
    data = None
    addr = None

    while True:
        try:
            data, addr = udpsock.recvfrom(1024)
        except socket.timeout, (strerror):
            if DEBUG:
                print >> sys.stderr, "NatTraversal: first timeout", strerror
                print >> sys.stderr, "NatTraversal: resend"

            udpsock.sendto("hello", peer)
            udpsock.sendto("hello", peer)
            udpsock.sendto("hello", peer)

            try:
                data, addr = udpsock.recvfrom(1024)
            except socket.timeout, (strerror):
                if DEBUG:
                    print >> sys.stderr, "NatTraversal: second timeout", strerror

                return "NO"

        # data received, check address
        if addr == peer: # peer is not symmetric NAT
            break

        if addr[0] == peer[0]: # peer has a symmetric NAT
            peer = addr
            break

        
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)

    # Close socket
    udpsock.close()
        
    if DEBUG:
        print >> sys.stderr, "NatTraversal: message from", addr, "is", data

    return "YES"

        
