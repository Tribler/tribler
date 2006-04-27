import os
import sys
from traceback import print_exc

#
# Code to guess the IP address of a host by which it is reachable on the
# Internet, given the host is not behind a firewall or NAT.
#
# For both Linux and Windows we first look at the routing table to
# see what the gateway for the default route is. We then try to establish
# our IP address that's on the same network as the gateway. That is our
# external/WAN address.
#
# Arno, Jan David, 2006-04-20
#

DEBUG = False

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
        list = line.split()
        if len(list) >= 3:
            if list[0] == 'Default' and list[1] == 'Gateway:':
                gwip = list[-1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    myip = None
    mywanip = None
    for line in os.popen(ifcmd).readlines():
        list = line.split()
        if len(list) >= 3:
            if list[0] == 'IP' and list[1] == 'Address.':
                myip = list[-1]
                if DEBUG:
                    print "ipconfig found IP address",myip
            elif list[0] == 'Default' and list[1] == 'Gateway':
                gwip2 = list[-1]
                if DEBUG:
                    print "ipconfig found default gateway",gwip2
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
        list = line.split()
        if len(list) >= 3:
            if list[0] == '0.0.0.0':
                gwif = list[-1]
                gwip = list[1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    mywanip = None
    for line in os.popen(ifcmd).readlines():
        list = line.split()
        if len(list) >= 2:
            if list[0] == gwif:
                flag = True
            elif list[0] == 'inet' and flag:
                list2 = list[1].split(':') # "inet addr:130.37.192.1" line
                if len(list2) == 2:
                    mywanip = list2[1]
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
        list = line.split()
        if len(list) >= 3:
            if list[0] == 'default':
                gwif = list[-1]
                gwip = list[1]
                if DEBUG:
                    print "netstat found default gateway",gwip
                break

    mywanip = None
    flag = False
    for line in os.popen(ifcmd).readlines():
        list = line.split()
        if len(list) >= 2:
            if list[0] == "%s:" % gwif:
                flag = True
            elif list[0] == 'inet' and flag:
                mywanip = list[1] # "inet 130.37.192.1" line
                break
    return mywanip



if __name__ == "__main__":
    ip = get_my_wan_ip()
    print "External IP address is",ip
