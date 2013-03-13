# Written by Arno Bakker, Jan David Mol
# see LICENSE.txt for license information
#
# Code to guess the IP address of a host by which it is reachable on the
# Internet, given the host is not behind a firewall or NAT.
#
# For all OSes (Linux,Windows,MacOS X) we first look at the routing table to
# see what the gateway for the default route is. We then try to establish
# our IP address that's on the same network as the gateway. That is our
# external/WAN address.
#
# This code does not support IPv6, that is, IPv6 address are ignored.
#
# Arno, Jan David, 2006-06-30
#
import os
import sys
import socket
from traceback import print_exc

DEBUG = False

def is_valid_ipv4_host(address):
    try:
        socket.inet_aton(address)
    except socket.error:
        return False
    return True

def get_my_wan_ip():
    try:
        if sys.platform == 'win32':
            return get_my_wan_ip_win32()
        elif sys.platform == 'darwin':
            return get_my_wan_ip_darwin()
        else:
            return get_my_wan_ip_linux()
    except:
        print_exc()
        return None

def get_my_wan_ip_win32():

    routecmd = "netstat -nr"
    ifcmd = "ipconfig /all"

    gwip = None
    for line in os.popen(routecmd).readlines():
        words = line.split()
        if len(words) >= 3:
            if words[0] == 'Default' and words[1] == 'Gateway:':
                gwip = words[-1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    myip = None
    mywanip = None
    ingw = 0
    for line in os.popen(ifcmd).readlines():
        words = line.split()
        if len(words) >= 3:
            if (words[0] == 'IPv4' and words[1] == 'Address.') or (words[0] == 'IP' and words[1] == 'Address.') or (words[1] == 'IP' and words[2] == 'Address.'): # Autoconfiguration entry
                ip = words[-1]
                if ip.endswith('(Preferred)'):
                    ip = ip[:-len('(Preferred)')]
                try:
                    socket.getaddrinfo(ip,None,socket.AF_INET)
                    myip = ip
                    if DEBUG:
                        print "ipconfig found IP address",myip
                except socket.gaierror:
                    if DEBUG:
                        print "ipconfig ignoring IPv6 address",ip
                    pass
            elif words[0] == 'Default' and words[1] == 'Gateway':
                if words[-1] == ':':
                    if DEBUG:
                        print "ipconfig ignoring empty default gateway"
                    pass
                else:
                    ingw = 1
        if ingw >= 1:
            # Assumption: the "Default Gateway" list can only have 2 entries,
            # one for IPv4, one for IPv6. Since we don't know the order, look
            # at both.
            gwip2 = None
            ingw = (ingw + 1) % 3
            try:
                socket.getaddrinfo(words[-1],None,socket.AF_INET)
                gwip2 = words[-1]
                if DEBUG:
                    print "ipconfig found default gateway",gwip2
            except socket.gaierror:
                if DEBUG:
                    print "ipconfig ignoring IPv6 default gateway",words[-1]
                pass
            if gwip == gwip2:
                mywanip = myip
                break
    return mywanip


def get_my_wan_ip_linux():
    routecmd = '/bin/netstat -nr'
    ifcmd = '/sbin/ifconfig -a'

    gwif = None
    gwip = None
    for line in os.popen(routecmd).readlines():
        words = line.split()
        if len(words) >= 3:
            if words[0] == '0.0.0.0':
                gwif = words[-1]
                gwip = words[1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    mywanip = None
    for line in os.popen(ifcmd).readlines():
        words = line.split()
        if len(words) >= 2:
            if words[0] == gwif:
                flag = True
            elif words[0] == 'inet':
                words2 = words[1].split(':') # "inet addr:130.37.192.1" line
                if len(words2) == 2 and words2[1] != '127.0.0.1' and is_valid_ipv4_host(words2[1]):
                    mywanip = words2[1]
                    break
                elif len(words2) == 1 and words2[0] != '127.0.0.1' and is_valid_ipv4_host(words2[0]):
                    mywanip = words2[0]
                    break
                else:
                    flag = False
            else:
                flag = False
    return mywanip


def get_my_wan_ip_darwin():
    routecmd = '/usr/sbin/netstat -nr'
    ifcmd = '/sbin/ifconfig -a'

    gwif = None
    gwip = None
    for line in os.popen(routecmd).readlines():
        words = line.split()
        if len(words) >= 3:
            if words[0] == 'default':
                gwif = words[-1]
                gwip = words[1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    mywanip = None
    flag = False
    for line in os.popen(ifcmd).readlines():
        words = line.split()
        if len(words) >= 2:
            if words[0] == "%s:" % gwif:
                flag = True
            elif words[0] == 'inet' and flag and is_valid_ipv4_host(words[1]):
                mywanip = words[1] # "inet 130.37.192.1" line
                break
    return mywanip



if __name__ == "__main__":
    DEBUG = True
    ip = get_my_wan_ip()
    print "External IP address is",ip
