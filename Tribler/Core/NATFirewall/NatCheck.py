# Written by Lucia D'Acunto
# see LICENSE.txt for license information

from socket import timeout
import sys

DEBUG = False

def Test1(udpsock, serveraddr):
    """
    The client sends a request to a server asking it to send the
    response back to the address and port the request came from
    """
    retVal = {"Resp":False, "ExternalIP":None, "ExternalPort":None}
    BUFSIZ = 1024
    request = "ping1"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except timeout, (strerror):
        return retVal

    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
    except error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)

    publicIP, publicPort = reply.split(":")

    retVal["Resp"] = True
    retVal["ExternalIP"] = publicIP
    retVal["ExternalPort"] = publicPort

    return retVal

def Test2(udpsock, serveraddr):
    """
    The client sends a request asking to receive an echo from a
    different address and a different port on the address and port the
    request came from
    """
    retVal = {"Resp":False}
    BUFSIZ = 1024
    request = "ping2"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except timeout, (strerror):
        return retVal
    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
    except error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)

    retVal["Resp"] = True

    return retVal

def Test3(udpsock, serveraddr):
    """
    The client sends a request asking to receive an echo from the same
    address but from a different port on the address and port the
    request came from
    """
    retVal = {"Resp":False, "ExternalIP":None, "ExternalPort":None}
    BUFSIZ = 1024
    request = "ping3"

    udpsock.sendto(request, serveraddr)

    try:
        reply, rcvaddr = udpsock.recvfrom(BUFSIZ)
    except timeout, (strerror):
        return retVal
    except ValueError, (strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)
    except error, (errno, strerror):
        if DEBUG: print >> sys.stderr, "NATCheck:", "Could not receive data: %s" % (strerror)

    publicIP, publicPort = reply.split(":")

    retVal["Resp"] = True
    retVal["ExternalIP"] = publicIP
    retVal["ExternalPort"] = publicPort

    return retVal

# Returns information about the NAT the client is behind
def GetNATType(udpsock, clientIP, clientPort, serveraddr1, serveraddr2):

    BUFSIZ = 1024
    NatType, exIP, exPort = [-1, "Unknown"], "0.0.0.0", "0"

    # Do Test I
    ret = Test1(udpsock, serveraddr1)

    if DEBUG: print >> sys.stderr, "NATCheck:", "Test I reported: " + str(ret)

    if ret["Resp"] == False:
        NatType[1] = "Blocked"

    else:
        exIP = ret["ExternalIP"]
        exPort = ret["ExternalPort"]

        if ret["ExternalIP"] == clientIP: # No NAT: check for firewall

            if DEBUG: print >> sys.stderr, "NATCheck:", "No NAT"

            # Do Test II
            ret = Test2(udpsock, serveraddr1)
            if DEBUG: print >> sys.stderr, "NATCheck:", "Test II reported: " + str(ret)

            if ret["Resp"] == True:
                NatType[0] = 0
                NatType[1] = "Open Internet"
            else:
                if DEBUG: print >> sys.stderr, "NATCheck:", "There is a Firewall"

                # Do Test III
                ret = Test3(udpsock, serveraddr1)
                if DEBUG: print >> sys.stderr, "NATCheck:", "Test III reported: " + str(ret)

                if ret["Resp"] == True:
                    NatType[0] = 2
                    NatType[1] = "Restricted Cone Firewall"
                else:
                    NatType[0] = 3
                    NatType[1] = "Port Restricted Cone Firewall"

        else: # There is a NAT
            if DEBUG: print >> sys.stderr, "NATCheck:", "There is a NAT"

            # Do Test II
            ret = Test2(udpsock, serveraddr1)
            if DEBUG: print >> sys.stderr, "NATCheck:", "Test II reported: " + str(ret)
            if ret["Resp"] == True:
                NatType[0] = 1
                NatType[1] = "Full Cone NAT"
            else:
                #Do Test I using a different echo server
                ret = Test1(udpsock, serveraddr2)
                if DEBUG: print >> sys.stderr, "NATCheck:", "Test I reported: " + str(ret)

                if exIP == ret["ExternalIP"] and exPort == ret["ExternalPort"]: # Public address is constant: consistent translation

                    # Do Test III
                    ret = Test3(udpsock, serveraddr1)
                    if DEBUG: print >> sys.stderr, "NATCheck:", "Test III reported: " + str(ret)

                    if ret["Resp"] == True:
                        NatType[0] = 2
                        NatType[1] = "Restricted Cone NAT"
                    else:
                        NatType[0] = 3
                        NatType[1] = "Port Restricted Cone NAT"

                else:
                    NatType[0] = -1
                    NatType[1] = "Symmetric NAT"

    return (NatType, exIP, exPort)
