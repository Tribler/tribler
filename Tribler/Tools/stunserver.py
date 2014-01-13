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
def usage():

    print("Usage:")
    print("     python natserver.py <serverport> <bounceip> <bounceport>")


# Serve client connections (if server 1 or 2)
def servemain(bounceaddr, serveraddr):

    # Set up the sockets
    try:
        udpsock = socket(AF_INET, SOCK_DGRAM)
        udpsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        udpsock.bind(serveraddr)

    except error as xxx_todo_changeme4:

        (errno, strerror) = xxx_todo_changeme4.args

        if udpsock:
            udpsock.close()

        if DEBUG:
            print("Could not open socket: %s" % (strerror), file=sys.stderr)
        sys.stdout.flush()

        sys.exit(1)

    try:
        udpsock.setblocking(0)
    except error:
        pass

    # Loop forever receiving messages and sending pings
    while True:

        if DEBUG:
            print(serveraddr, "Waiting for connection...", file=sys.stderr)

        try:
            ready_to_read, ready_to_write, errors = select.select([udpsock], [], [])

        except (KeyboardInterrupt, SystemExit):

            if udpsock:
                udpsock.close()

            if DEBUG:
                print("Exiting ...", file=sys.stderr)

            sys.exit(1)

        except select.error as xxx_todo_changeme2:

            (errno, strerror) = xxx_todo_changeme2.args

            if udpsock:
                udpsock.close()

            if DEBUG:
                print("I/O error: %s" % (strerror), file=sys.stderr)

            sys.exit(1)

        for i in ready_to_read:

            if DEBUG:
                print("Incoming connection...", file=sys.stderr)

            # Serve udp connections
            if i == udpsock:

                BUFSIZ = 1024
                try:
                    data, clientaddr = udpsock.recvfrom(BUFSIZ)
                    print(strftime("%Y/%m/%d %H:%M:%S"), "...connected from:", clientaddr, file=sys.stderr)

                except error as xxx_todo_changeme1:
                    (errno, strerr) = xxx_todo_changeme1.args
                    if DEBUG:
                        print(strerr, file=sys.stderr)
                    break

                if data == "ping1":  # The client is running Test I

                    if DEBUG:
                        print("received ping1", file=sys.stderr)

                    reply = "%s:%s" % (clientaddr[0], clientaddr[1])
                    try:
                        udpsock.sendto(reply, clientaddr)
                    except:
                        break

                if data == "ping2":  # The client is running Test II

                    if DEBUG:
                        print("received ping2", file=sys.stderr)

                    reply = "%s:%s" % (clientaddr[0], clientaddr[1])
                    try:
                        udpsock.sendto(reply, bounceaddr)
                    except:
                        break
                    if DEBUG:
                        print("bounce request is", reply, file=sys.stderr)
                        print("bounce request sent to ", (bounceaddr), file=sys.stderr)

                if data == "ping3":  # The client is running Test III

                    if DEBUG:
                        print("received ping3", file=sys.stderr)

                    # Create a new socket and bind it to a different port
                    try:

                        # serveraddr2 = (gethostbyname(gethostname()), int(sys.argv[1]) + 5)
                        serveraddr2 = (serveraddr[0], serveraddr[1] + 5)
                        udpsock2 = socket(AF_INET, SOCK_DGRAM)
                        udpsock2.bind(serveraddr2)
                        if DEBUG:
                            print("new socket bind at ", serveraddr2, file=sys.stderr)

                    except error as xxx_todo_changeme:

                        (errno, strerror) = xxx_todo_changeme.args

                        if udpsock2:
                            udpsock2.close()

                        if DEBUG:
                            print("Could not open socket: %s" % (strerror), file=sys.stderr)

                        break

                    # Send an echo back to the client using the new socket
                    reply = "%s:%s " % (clientaddr[0], clientaddr[1])
                    print("send an echo back to the client using the new socket... reply=", reply, "clientaddr=", clientaddr, file=sys.stderr)
                    udpsock2.sendto(reply, clientaddr)

                    udpsock2.close()

                else:
                    if DEBUG:
                        print("data is: ", data, file=sys.stderr)

                    try:
                        host, port = data.split(":")

                    except (ValueError):
                        break

                    try:
                        bouncedest = (host, int(port))

                    except ValueError:
                        break

                    try:
                        udpsock.sendto(data, bouncedest)
                    except:
                        break
                    if DEBUG:
                        print("Bounceping sent to", bouncedest, file=sys.stderr)

    udpsock.close()


# Serve bounce connections
def bouncemain(serveraddr):

    # Set up the sockets
    try:
        udpsock = socket(AF_INET, SOCK_DGRAM)
        udpsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        udpsock.bind(serveraddr)

    except error as xxx_todo_changeme5:

        (errno, strerror) = xxx_todo_changeme5.args

        if udpsock:
            udpsock.close()

        if DEBUG:
            print("Could not open socket: %s" % (strerror), file=sys.stderr)

        sys.exit(1)

    try:
        udpsock.setblocking(0)
    except error:
        pass

    # Loop forever receiving messages and sending pings
    while True:

        if DEBUG:
            print(serveraddr, "Waiting for connection...", file=sys.stderr)

        try:
            ready_to_read, ready_to_write, errors = select.select([udpsock], [], [])

        except (KeyboardInterrupt, SystemExit):

            if udpsock:
                udpsock.close()

            if DEBUG:
                print("Exiting ...", file=sys.stderr)

            sys.exit(1)

        except select.error as xxx_todo_changeme3:

            (errno, strerror) = xxx_todo_changeme3.args

            if udpsock:
                udpsock.close()

            if DEBUG:
                print("I/O error: %s" % (strerror), file=sys.stderr)

            sys.exit(1)

        for i in ready_to_read:

            if DEBUG:
                print("Incoming connection...", file=sys.stderr)

            # Serve udp connections
            if i == udpsock:

                BUFSIZ = 1024
                data, clientaddr = udpsock.recvfrom(BUFSIZ)
                print(strftime("%Y/%m/%d %H:%M:%S"), "...connected from: ", clientaddr, file=sys.stderr)
                if DEBUG:
                    print("data is: ", data, file=sys.stderr)

                try:
                    host, port = data.split(":")

                except (ValueError):
                    break

                try:
                    bouncedest = (host, int(port))

                except ValueError:
                    break

                try:
                    udpsock.sendto(data, bouncedest)
                except:
                    break
                if DEBUG:
                    print("Bounceping sent to", bouncedest, file=sys.stderr)

    udpsock.close()


if __name__ == "__main__":

    # Server initialization

    if len(sys.argv) != (4):
        usage()
        sys.exit(1)

    bounceaddr = None
    serveraddr = None

    try:
        bounceaddr = (sys.argv[2], int(sys.argv[3]))

    except ValueError as strerror:
        if DEBUG:
            print("ValueError: ", strerror, file=sys.stderr)
        usage()
        sys.exit(1)

    try:
        # serveraddr = (gethostbyname(gethostname()), int(sys.argv[1]))
        serveraddr = ("0.0.0.0", int(sys.argv[1]))

    except ValueError as strerror:
        if DEBUG:
            print("ValueError: ", strerror, file=sys.stderr)
        usage()
        sys.exit(1)

    # Run the appropriate server code
    while True:
        try:
            if DEBUG:
                print(strftime("%Y/%m/%d %H:%M:%S"), "Stun server started", file=sys.stderr)
            # thread.start_new_thread(servemain, (bounceaddr, serveraddr) )
            # bouncemain(serveraddr)
            servemain(bounceaddr, serveraddr)

        except (KeyboardInterrupt, SystemExit):

            if DEBUG:
                print("Exiting ...", file=sys.stderr)

            sys.exit(1)

        # except:
            # if DEBUG:
                # print >> sys.stderr, "Unexpected error:", sys.exc_info()[0]
