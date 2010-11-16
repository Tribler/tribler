# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import socket


class AddrError(Exception):
    pass

class IP6Addr(AddrError):
    pass
#TODO2: IPv6 support


#TODO2: move binary functions from identifier

def compact_port(port):
    return ''.join(
        [chr(port_byte_int) for port_byte_int in divmod(port, 256)])

'''
def uncompact_port(c_port_net):
    return ord(bin_str[0]) * 256 + ord(bin_str[1])
'''

def compact_addr(addr):
    return socket.inet_aton(addr[0]) + compact_port(addr[1])
'''
def uncompact_addr(c_addr):
    try:
        return (socket.inet_ntoa(c_addr[:-2],
                                 uncompact_port(c_addr[-2:])))
    except (socket.error):
        raise AddrError
'''
compact_peer = compact_addr
