import os
from socket import gethostbyname

_trackers = [(u"dispersy1.tribler.org", 6421),
             (u"dispersy2.tribler.org", 6422),
             (u"dispersy3.tribler.org", 6423),
             (u"dispersy4.tribler.org", 6424),
             (u"dispersy5.tribler.org", 6425),
             (u"dispersy6.tribler.org", 6426)]

def get_bootstrap_hosts(working_directory):
    """
    Reads WORKING_DIRECTORY/bootstraptribler.txt and returns the hosts therein, otherwise it
    returns _TRACKERS.
    """
    trackers= []
    filename = os.path.join(working_directory, "bootstraptribler.txt")
    try:
        for line in open(filename, "r"):
            line = line.strip()
            if not line.startswith("#"):
                host, port = line.split()
                trackers.append((host.decode("UTF-8"), int(port)))
    except:
        pass

    if trackers:
        return trackers

    else:
        return _trackers

def get_bootstrap_addresses(working_directory):
    """
    Returns a list with all known bootstrap peers.

    Bootstrap peers are retrieved from WORKING_DIRECTORY/bootstraptribler.txt if it exits.
    Otherwise it is created using the trackers defined in _TRACKERS.

    Each bootstrap peer gives either None or a (ip-address, port) tuple.  None values can be caused
    by malfunctioning DNS.
    """
    def get_address(host, port):
        try:
            return gethostbyname(host), port
        except:
            return None

    return [get_address(host, port) for host, port in get_bootstrap_hosts(working_directory)]
