"""
This module contains some utility functions for networking.
"""
import logging
import random
import socket
import struct
import sys

logger = logging.getLogger(__name__)

CLAIMED_PORTS = []


def get_random_port(socket_type="all", min_port=5000, max_port=60000):
    """Gets a random port number that works.
    @param socket_type: Type of the socket, can be "all", "tcp", or "udp".
    @param min_port: The minimal port number to try with.
    @param max_port: The maximal port number to try with.
    @return: A working port number if exists, otherwise None.
    """
    assert socket_type in ("all", "tcp", "udp"), "Invalid socket type %s" % type(socket_type)
    assert isinstance(min_port, int), "Invalid min_port type %s" % type(min_port)
    assert isinstance(max_port, int), "Invalid max_port type %s" % type(max_port)
    assert 0 < min_port <= max_port <= 65535, f"Invalid min_port and mac_port values {min_port}, {max_port}"

    working_port = None
    try_port = random.randint(min_port, max_port)
    while try_port <= 65535:
        if check_random_port(try_port, socket_type):
            working_port = try_port
            break
        try_port += 1

    if working_port:
        CLAIMED_PORTS.append(working_port)

    logger.debug("Got a working random port %s", working_port)
    return working_port


def check_random_port(port, socket_type="all"):
    """Returns an usable port number that can be bound with by the specific type of socket.
    @param socket_type: Type of the socket, can be "all", "tcp", or "udp".
    @param port: The port to try with.
    @return: True or False indicating if port is available.
    """
    assert socket_type in ("all", "tcp", "udp"), "Invalid socket type %s" % type(socket_type)
    assert isinstance(port, int), "Invalid port type %s" % type(port)
    assert 0 < port <= 65535, "Invalid port value %s" % port

    # only support IPv4 for now
    _family = socket.AF_INET

    _sock_type = None
    if socket_type == "udp":
        _sock_type = socket.SOCK_DGRAM
    elif socket_type == "tcp":
        _sock_type = socket.SOCK_STREAM

    is_port_working = False
    if port in CLAIMED_PORTS:
        return False
    if socket_type == "all":
        # try both UDP and TCP
        if _test_port(_family, socket.SOCK_DGRAM, port):
            is_port_working = _test_port(_family, socket.SOCK_STREAM, port)
    else:
        is_port_working = _test_port(_family, _sock_type, port)

    return is_port_working


def _test_port(family, sock_type, port):
    """Tests if a port is available.
    @param family: The socket family, must be socket.AF_INET.
    @param sock_type: The socket type, can be socket.SOCK_DGRAM or socket.SOCK_STREAM.
    @param port: The port number to test with.
    @return: True if the port is available or there is no problem with the socket, otherwise False.
    """
    assert family in (socket.AF_INET,), "Invalid family value %s" % family
    assert sock_type in (socket.SOCK_DGRAM, socket.SOCK_STREAM), "Invalid sock_type value %s" % sock_type
    assert 0 < port <= 65535, "Invalid port value %s" % port

    try:
        with socket.socket(family, sock_type) as s:
            if sock_type == socket.SOCK_STREAM:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            s.bind(('', port))
        is_port_working = True
    except OSError as e:
        logger.debug("Port test failed (port=%s, family=%s, type=%s): %s",
                     port, family, sock_type, e)
        is_port_working = False
    return is_port_working


def autodetect_socket_style():
    if sys.platform.find('linux') < 0:
        return 1
    else:
        try:
            with open('/proc/sys/net/ipv6/bindv6only') as f:
                dual_socket_style = int(f.read())
            return int(not dual_socket_style)
        except (OSError, ValueError):
            return 0


def is_valid_address(address):
    """
    Returns True when ADDRESS is valid.

    ADDRESS must be supplied as a (HOST string, PORT integer) tuple.

    An address is valid when it meets the following criteria:
    - HOST must be non empty
    - HOST must be non '0.0.0.0'
    - PORT must be > 0
    - HOST must be 'A.B.C.D' where A, B, and C are numbers higher or equal to 0 and lower or
      equal to 255.  And where D is higher than 0 and lower than 255
    """
    assert isinstance(address, tuple), type(address)
    assert len(address) == 2, len(address)
    assert isinstance(address[0], str), type(address[0])
    assert isinstance(address[1], int), type(address[1])

    if address[0] == "":
        return False

    if address[0] == "0.0.0.0":
        return False

    if address[1] <= 0:
        return False

    try:
        socket.inet_aton(address[0])
    except OSError:
        return False

    # ending with .0
    # Niels: is now allowed, subnet mask magic call actually allow for this
    #        if binary[3] == "\x00":
    #            return False

    # ending with .255
    # Niels: same for this one, if the netmask is /23 a .255 could indicate 011111111 which is allowed
    #        if binary[3] == "\xff":
    #            return False

    return True
