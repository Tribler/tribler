# Written by Lucia D'Acunto
# see LICENSE.txt for license information

import socket
import sys

DEBUG = False

def Test1(udpsock, serveraddr):
    """
    The client sends a request to a server asking it to send the
    response back to the address and port the request came from
    """

    retVal = {"resp":False, "ex_ip":None, "ex_port":None}
    BUFSIZ = 1024
    reply = ""
    request = "ping1"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except socket.timeout:
        #if DEBUG: print >> sys.stderr, "NATCheck:", "Connection attempt to %s timed out" % (serveraddr,)
        return retVal

    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal
    except socket.error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal

    ex_ip, ex_port = reply.split(":")

    retVal["resp"] = True
    retVal["ex_ip"] = ex_ip
    retVal["ex_port"] = ex_port

    return retVal

def Test2(udpsock, serveraddr):
    """
    The client sends a request asking to receive an echo from a
    different address and a different port on the address and port the
    request came from
    """

    retVal = {"resp":False}
    BUFSIZ = 1024
    request = "ping2"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except socket.timeout:        
        #if DEBUG: print >> sys.stderr, "NATCheck:", "Connection attempt to %s timed out" % (serveraddr,)
        return retVal
    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal
    except socket.error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal

    retVal["resp"] = True

    return retVal

def Test3(udpsock, serveraddr):
    """
    The client sends a request asking to receive an echo from the same
    address but from a different port on the address and port the
    request came from
    """

    retVal = {"resp":False, "ex_ip":None, "ex_port":None}
    BUFSIZ = 1024
    reply = ""
    request = "ping3"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except socket.timeout:
        #if DEBUG: print >> sys.stderr, "NATCheck:", "Connection attempt to %s timed out" % (serveraddr,)
        return retVal
    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal
    except socket.error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
        return retVal

    ex_ip, ex_port = reply.split(":")

    retVal["resp"] = True
    retVal["ex_ip"] = ex_ip
    retVal["ex_port"] = ex_port

    return retVal

# Returns information about the NAT the client is behind
def GetNATType(in_port, serveraddr1, serveraddr2):
    """
    Returns the NAT type according to the STUN algorithm, as well as the external
    address (ip, port) and the internal address of the host
    """

    serveraddr1 = ('stun1.tribler.org',6701)
    serveraddr2 = ('stun2.tribler.org',6702)
    
    nat_type, ex_ip, ex_port, in_ip = [-1, "Unknown"], "0.0.0.0", "0", "0.0.0.0"

    # Set up the socket
    udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udpsock.settimeout(5)
    try:
        udpsock.bind(('',in_port))
    except socket.error, err:
        print >> sys.stderr, "Couldn't bind a udp socket on port %d : %s" % (in_port, err)
        return (nat_type, ex_ip, ex_port, in_ip)
    try:
        # Get the internal IP address
        connectaddr = ('tribler.org',80)
        s = socket.socket()
        s.connect(connectaddr)
        in_ip = s.getsockname()[0]
        del s
        if DEBUG: print >> sys.stderr, "NATCheck: getting the internal ip address by connecting to tribler.org:80", in_ip
    except socket.error, err:
        print >> sys.stderr, "Couldn't connect to %s:%i" % (connectaddr[0], connectaddr[1])
        return (nat_type, ex_ip, ex_port, in_ip)

    """
        EXECUTE THE STUN ALGORITHM
    """

    # Do Test I
    ret = Test1(udpsock, serveraddr1)

    if DEBUG: print >> sys.stderr, "NATCheck:", "Test I reported: " + str(ret)

    if ret["resp"] == False:
        nat_type[1] = "Blocked"

    else:
        ex_ip = ret["ex_ip"]
        ex_port = ret["ex_port"]

        if ret["ex_ip"] == in_ip: # No NAT: check for firewall

            if DEBUG: print >> sys.stderr, "NATCheck:", "No NAT"

            # Do Test II
            ret = Test2(udpsock, serveraddr1)
            if DEBUG: print >> sys.stderr, "NATCheck:", "Test II reported: " + str(ret)

            if ret["resp"] == True:
                nat_type[0] = 0
                nat_type[1] = "Open Internet"
            else:
                if DEBUG: print >> sys.stderr, "NATCheck:", "There is a Firewall"

                # Do Test III
                ret = Test3(udpsock, serveraddr1)
                if DEBUG: print >> sys.stderr, "NATCheck:", "Test III reported: " + str(ret)

                if ret["resp"] == True:
                    nat_type[0] = 2
                    nat_type[1] = "Restricted Cone Firewall"
                else:
                    nat_type[0] = 3
                    nat_type[1] = "Port Restricted Cone Firewall"

        else: # There is a NAT
            if DEBUG: print >> sys.stderr, "NATCheck:", "There is a NAT"

            # Do Test II
            ret = Test2(udpsock, serveraddr1)
            if DEBUG: print >> sys.stderr, "NATCheck:", "Test II reported: " + str(ret)
            if ret["resp"] == True:
                nat_type[0] = 1
                nat_type[1] = "Full Cone NAT"
            else:
                #Do Test I using a different echo server
                ret = Test1(udpsock, serveraddr2)
                if DEBUG: print >> sys.stderr, "NATCheck:", "Test I reported: " + str(ret)

                if ex_ip == ret["ex_ip"] and ex_port == ret["ex_port"]: # Public address is constant: consistent translation

                    # Do Test III
                    ret = Test3(udpsock, serveraddr1)
                    if DEBUG: print >> sys.stderr, "NATCheck:", "Test III reported: " + str(ret)

                    if ret["resp"] == True:
                        nat_type[0] = 2
                        nat_type[1] = "Restricted Cone NAT"
                    else:
                        nat_type[0] = 3
                        nat_type[1] = "Port Restricted Cone NAT"

                else:
                    nat_type[0] = -1
                    nat_type[1] = "Symmetric NAT"

    udpsock.close()
    return (nat_type, ex_ip, ex_port, in_ip)
