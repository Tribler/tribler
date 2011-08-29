from socket import gethostbyname

_trackers = [(u"dispersy1.tribler.org", 6421)]

def get_bootstrap_addresses():
    """
    Returns a list with (id-address, port) tuples.

    The returned list can be empty, this can be caused by malfunctioning DNS.
    """
    def get_address(host, port):
        try:
            return gethostbyname(host), port
        except:
            return None

    return [address for address in (get_address(host, port) for host, port in _trackers)]
