# Written by Lucia D'Acunto
# see LICENSE.txt for license information

# Ping back server

from socket import *
import sys
import time
import thread
import select


DEBUG = True


# Print usage information
def usage():

    print "Usage:"
    print " python pingback.py <serverport>"


def serveclient(message, udpsock, clientaddr):

    # Loop forever receiving pings and sending pongs
    data = message.split(':')

    if data[0] == "ping":

        if DEBUG:
            print >> sys.stderr, "received ping with delay", data[1], "from", clientaddr

        time.sleep(int(data[1]))

        if DEBUG:
            print >> sys.stderr, "sending pong back after", data[1], "seconds", "to", clientaddr

        pongMsg = (str("pong:" + data[1]))
        udpsock.sendto(pongMsg, clientaddr)


if __name__ == "__main__":

    if len(sys.argv) != 2:
        usage()
        sys.exit(1)

    serveraddr = None
    log = open("log.txt", "a")  # logfile

    try:
        serveraddr = (gethostbyname(gethostname()), int(sys.argv[1]))

    except ValueError as strerror:
        if DEBUG:
            print >> sys.stderr, "ValueError: ", strerror
        usage()
        sys.exit(1)

    # Set up the sockets
    try:
        udpsock = socket(AF_INET, SOCK_DGRAM)
        udpsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        udpsock.bind(serveraddr)

    except error as xxx_todo_changeme:

        (errno, strerror) = xxx_todo_changeme.args

        if udpsock:
            udpsock.close()

        if DEBUG:
            print >> sys.stderr, "Could not open socket: %s" % (strerror)
        sys.stdout.flush()

        sys.exit(1)

    if DEBUG:
        print >> sys.stderr, "waiting for connection..."

    # Loop forever receiving pings and sending pongs
    while True:

        BUFSIZ = 1024
        message = None
        clientaddr = None

        try:
            message, clientaddr = udpsock.recvfrom(BUFSIZ)
        except error:
            continue

        print >> sys.stderr, time.strftime("%Y/%m/%d %H:%M:%S"), "...connected from:", clientaddr
        log.write("%i %s %i\n" % (time.time(), str(clientaddr[0]), clientaddr[1]))
        log.flush()

        thread.start_new_thread(serveclient, (message, udpsock, clientaddr))
