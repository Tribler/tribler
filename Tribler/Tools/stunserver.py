# Written by Lucia D'Acunto
# see LICENSE.txt for license information

# natserver.py

import os
from socket import *
from time import strftime
import select
import sys
import thread


DEBUG = True


# Print usage information
def usage() :

    print "Usage:"
    print "     python natserver.py <serverport> <bounceip> <bounceport>"


# Serve client connections (if server 1 or 2)
def servemain(bounceaddr, serveraddr) :

    # Set up the sockets
    try :
        udpsock = socket(AF_INET, SOCK_DGRAM)
        udpsock.setsockopt(SOL_SOCKET,SO_REUSEADDR,1)
        udpsock.bind(serveraddr)

    except error, (errno, strerror) :

        if udpsock :
            udpsock.close()

        if DEBUG:
            print >> sys.stderr, "Could not open socket: %s" % (strerror)
        sys.stdout.flush()

        sys.exit(1)

    try :
        udpsock.setblocking(0)
    except error :
        pass


    # Loop forever receiving messages and sending pings
    while 1 :

        if DEBUG:
            print >> sys.stderr, serveraddr, "Waiting for connection..."

        try :
            ready_to_read, ready_to_write, errors = select.select([udpsock],[],[])

        except (KeyboardInterrupt, SystemExit):

            if udpsock :
                udpsock.close()

            if DEBUG:
                print >> sys.stderr, "Exiting ..."

            sys.exit(1)

        except select.error, (errno, strerror) :

            if udpsock :
                udpsock.close()

            if DEBUG:
                print >> sys.stderr, "I/O error: %s" % (strerror)

            sys.exit(1)

        for i in ready_to_read :

            if DEBUG:
                print >> sys.stderr, "Incoming connection..."

            # Serve udp connections
            if i == udpsock :

                BUFSIZ = 1024
                try:
                    data, clientaddr = udpsock.recvfrom(BUFSIZ)
                    print >> sys.stderr, strftime("%Y/%m/%d %H:%M:%S"), "...connected from:", clientaddr

                except error, (errno, strerr) :
                    if DEBUG:
                        print >> sys.stderr, strerr
                    break

                if data == "ping1" : # The client is running Test I

                    if DEBUG:
                        print >> sys.stderr, "received ping1"

                    reply = "%s:%s" % (clientaddr[0], clientaddr[1])
                    try:
                        udpsock.sendto(reply, clientaddr)
                    except:
                        break

                if data == "ping2": # The client is running Test II

                    if DEBUG:
                        print >> sys.stderr, "received ping2"

                    reply = "%s:%s" % (clientaddr[0], clientaddr[1])
                    try:
                        udpsock.sendto(reply, bounceaddr)
                    except:
                        break
                    if DEBUG:
                        print >> sys.stderr, "bounce request is", reply
                        print >> sys.stderr, "bounce request sent to ", (bounceaddr)

                if data == "ping3" :  # The client is running Test III

                    if DEBUG:
                        print >> sys.stderr, "received ping3"

                    # Create a new socket and bind it to a different port
                    try :

                        #serveraddr2 = (gethostbyname(gethostname()), int(sys.argv[1]) + 5)
                        serveraddr2 = (serveraddr[0], serveraddr[1] + 5)
                        udpsock2 = socket(AF_INET, SOCK_DGRAM)
                        udpsock2.bind(serveraddr2)
                        if DEBUG:
                            print >> sys.stderr, "new socket bind at ", serveraddr2

                    except error, (errno, strerror) :

                        if udpsock2 :
                            udpsock2.close()

                        if DEBUG:
                            print >> sys.stderr, "Could not open socket: %s" % (strerror)

                        break

                    # Send an echo back to the client using the new socket
                    reply =  "%s:%s " % (clientaddr[0], clientaddr[1])
                    print >> sys.stderr, "send an echo back to the client using the new socket... reply=", reply, "clientaddr=", clientaddr
                    udpsock2.sendto(reply, clientaddr)

                    udpsock2.close()

                else:
                    if DEBUG:
                        print >> sys.stderr, "data is: ", data

                    try :
                        host, port = data.split(":")

                    except (ValueError) :
                        break

                    try :
                        bouncedest = (host, int(port))

                    except ValueError :
                        break

                    try:
                        udpsock.sendto(data, bouncedest)
                    except:
                        break
                    if DEBUG:
                        print >> sys.stderr, "Bounceping sent to", bouncedest


    udpsock.close()



# Serve bounce connections
def bouncemain(serveraddr) :

    # Set up the sockets
    try :
        udpsock = socket(AF_INET, SOCK_DGRAM)
        udpsock.setsockopt(SOL_SOCKET,SO_REUSEADDR,1)
        udpsock.bind(serveraddr)

    except error, (errno, strerror) :

        if udpsock :
            udpsock.close()

        if DEBUG:
            print >> sys.stderr, "Could not open socket: %s" % (strerror)

        sys.exit(1)

    try :
        udpsock.setblocking(0)
    except error :
        pass


    # Loop forever receiving messages and sending pings
    while 1 :

        if DEBUG:
            print >> sys.stderr, serveraddr,  "Waiting for connection..."

        try :
            ready_to_read, ready_to_write, errors = select.select([udpsock],[],[])

        except (KeyboardInterrupt, SystemExit):

            if udpsock :
                udpsock.close()

            if DEBUG:
                print >> sys.stderr, "Exiting ..."

            sys.exit(1)

        except select.error, (errno, strerror) :

            if udpsock :
                udpsock.close()

            if DEBUG:
                print >> sys.stderr, "I/O error: %s" % (strerror)

            sys.exit(1)

        for i in ready_to_read :

            if DEBUG:
                print >> sys.stderr, "Incoming connection..."


            # Serve udp connections
            if i == udpsock :

                BUFSIZ = 1024
                data, clientaddr = udpsock.recvfrom(BUFSIZ)
                print >> sys.stderr, strftime("%Y/%m/%d %H:%M:%S"), "...connected from: ", clientaddr
                if DEBUG:
                    print >> sys.stderr, "data is: ", data

                try :
                    host, port = data.split(":")

                except (ValueError) :
                    break

                try :
                    bouncedest = (host, int(port))

                except ValueError :
                    break

                try:
                    udpsock.sendto(data, bouncedest)
                except:
                    break
                if DEBUG:
                    print >> sys.stderr, "Bounceping sent to", bouncedest

    udpsock.close()



if __name__=="__main__" :

    # Server initialization

    if len(sys.argv) != (4) :
        usage()
        sys.exit(1)

    bounceaddr = None
    serveraddr = None

    try :
        bounceaddr = (sys.argv[2], int(sys.argv[3]))

    except ValueError, strerror :
        if DEBUG:
            print >> sys.stderr, "ValueError: ", strerror
        usage()
        sys.exit(1)

    try :
        #serveraddr = (gethostbyname(gethostname()), int(sys.argv[1]))
        serveraddr = ("0.0.0.0", int(sys.argv[1]))

    except ValueError, strerror :
        if DEBUG:
            print >> sys.stderr, "ValueError: ", strerror
        usage()
        sys.exit(1)

    # Run the appropriate server code
    while True:
        try:
            if DEBUG:
                print >> sys.stderr, strftime("%Y/%m/%d %H:%M:%S"), "Stun server started"
            #thread.start_new_thread(servemain, (bounceaddr, serveraddr) )
            #bouncemain(serveraddr)
            servemain(bounceaddr, serveraddr)

        except (KeyboardInterrupt, SystemExit):

            if DEBUG:
                print >> sys.stderr, "Exiting ..."

            sys.exit(1)

        #except:
            #if DEBUG:
                #print >> sys.stderr, "Unexpected error:", sys.exc_info()[0]
