import random
import socket
import struct

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
    assert 0 < min_port <= max_port <= 65535, "Invalid min_port and mac_port values %s, %s" % (min_port, max_port)

    working_port = None
    try_port = random.randint(min_port, max_port)
    while try_port <= 65535:
        if check_random_port(try_port, socket_type):
            working_port = try_port
            break
        try_port += 1

    if working_port:
        CLAIMED_PORTS.append(working_port)

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

    s = None
    try:
        s = socket.socket(family, sock_type)
        if sock_type == socket.SOCK_STREAM:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        s.bind(('', port))
        is_port_working = True
    except socket.error:
        is_port_working = False
    finally:
        if s:
            s.close()
    return is_port_working
