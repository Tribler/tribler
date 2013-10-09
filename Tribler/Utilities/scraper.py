import urllib
import socket, random, struct

from libtorrent import bdecode

def scrape_udp(tracker, infohashes):
    tracker = tracker.lower()
    host, port = tracker[6:].split(':')
    addr = (host, int(port.split('/')[0]))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(6)

    # Connection request
    conn_req = struct.pack("!QII", 0x41727101980, 0, random.getrandbits(32))
    sock.sendto(conn_req, addr)

    # Process connection response
    conn_resp, _ = sock.recvfrom(1024)
    action, _, connection_id = struct.unpack_from("!IIQ", conn_resp)
    if action != 0:
        return

    # Scrape request
    transaction_id = random.getrandbits(32)
    scrp_req = struct.pack("!QII", connection_id, 2, transaction_id) + ''.join([struct.pack("!20s", i) for i in infohashes])
    sock.sendto(scrp_req, addr)

    # Process scrape response
    scrp_resp, _ = sock.recvfrom(1024)
    action, scrp_transaction_id = struct.unpack_from("!II", scrp_resp)
    if action != 2 or scrp_transaction_id != transaction_id:
        return

    result = {}
    for index, infohash in enumerate(infohashes):
        t = struct.unpack_from("!III", scrp_resp, 8 + (index * 12))
        result[infohash] = dict(zip(['complete', 'downloaded', 'incomplete'], t))
    return result

def scrape_tcp(tracker, infohashes):
    infohashes_quoted = [urllib.quote(infohash) for infohash in infohashes]
    tracker = tracker.replace("announce", "scrape")
    tracker = tracker + ('?' if tracker.find('?') == -1 else '&') + 'info_hash=' + '&info_hash='.join(infohashes_quoted)
    response = urllib.urlopen(tracker).read()
    response = bdecode(response)

    result = {}
    for h, i in response['files'].iteritems():
        result[h] = {"complete" : i["complete"], "downloaded" : i["downloaded"], "incomplete" : i["incomplete"]}
    return result
