from time import strftime
import datetime
import select
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

    # Wait for response
    data = None
    addr = None
    try:
        data, addr = udpsock.recvfrom(1024)
    except socket.timeout, (strerror):
        if DEBUG:
            print >> sys.stderr, "NatTraversal: timeout with coordinator"
        return "ERR"

    if DEBUG:
        if addr == coordinator:
            print >> sys.stderr, "NatTraversal: received", data, "from coordinator"
        else:
            print >> sys.stderr, "NatTraversal: received", data, "from", addr
            
    # host, port = data.split(":")
    # peer = (host, int(port))
    # success = False
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

    host, port = data.split(":")
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

        if addr == peer: # data received, check address
            break

        
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)
    udpsock.sendto("hello",peer)

    # Close socket
    udpsock.close()
        
    if DEBUG:
        print >> sys.stderr, "NatTraversal: message from", addr, "is", data

    return "YES"

        
