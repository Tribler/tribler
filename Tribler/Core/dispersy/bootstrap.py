from socket import gethostbyname

_trackers = [(u"dispersy2.tribler.org", 6422)]

def get_bootstrap_addresses():
    """
    Returns a list with all known bootstrap peers.

    Each bootstrap peer gives either None or a (ip-address, port) tuple.  None values can be caused
    by malfunctioning DNS.
    """
    def get_address(host, port):
        try:
            return gethostbyname(host), port
        except:
            return None

    return [get_address(host, port) for host, port in _trackers]
