# written by Yuan Yuan
# see LICENSE.txt for license information

# single torrent checking without Thread
import sys
from Tribler.Core.Utilities.bencode import bdecode
from urlparse import urlparse
from random import shuffle, randint, choice
from struct import *

import urllib
import socket
import Tribler.Core.Utilities.timeouturlopen as timeouturlopen
from time import time
from traceback import print_exc
from binascii import unhexlify

HTTP_TIMEOUT = 30  # seconds

DEBUG = True
ioErrors = {}


def trackerChecking(torrent):
    single_no_thread(torrent)


def multiTrackerChecking(torrent, multiscrapeCallback):
    return single_no_thread(torrent, multiscrapeCallback)


def single_no_thread(torrent, multiscrapeCallback=None):
    multi_announce_dict = {}
    multi_announce_dict[torrent['infohash']] = (-2, -2)

    # determine trackers
    trackers = []
    if (torrent["info"].get("announce-list", "") == ""):  # no announce-list
        trackers.append(torrent["info"]["announce"])
    else:  # have announce-list
        for announces in torrent["info"]["announce-list"]:
            a_len = len(announces)
            if (a_len == 0):  # length = 0
                continue

            if (a_len == 1):  # length = 1
                trackers.append(announces[0])

            else:  # length > 1
                aindex = torrent["info"]["announce-list"].index(announces)
                shuffle(announces)

                # Arno: protect against DoS torrents with many trackers in announce list.
                trackers.extend(announces[:10])

    trackers = [(-ioErrors.get(tracker, 0), tracker) for tracker in trackers if tracker.startswith('http') or tracker.startswith('udp')]
    trackers.sort(reverse=True)  # sorting reverse will prefer udp over http trackers

    if DEBUG:
        print >> sys.stderr, "TrackerChecking: Checking", torrent["infohash"], trackers

    for _, announce in trackers:
        announce_dict = singleTrackerStatus(torrent, announce, multiscrapeCallback)

        for key, values in announce_dict.iteritems():
            # merge results
            if key in multi_announce_dict:
                cur_values = list(multi_announce_dict[key])
                cur_values[0] = max(values[0], cur_values[0])
                cur_values[1] = max(values[1], cur_values[1])
                multi_announce_dict[key] = cur_values
            else:
                multi_announce_dict[key] = values

        (seeder, _) = multi_announce_dict[torrent["infohash"]]
        if seeder > 0:
            break

    if DEBUG:
        print >> sys.stderr, "TrackerChecking: Result", multi_announce_dict[torrent["infohash"]]

    return multi_announce_dict


def singleTrackerStatus(torrent, announce, multiscrapeCallback):
    # return (-1, -1) means the status of torrent is unknown
    # return (-2. -2) means the status of torrent is dead
    # return (-3, -3) means the interval problem
    info_hashes = [torrent["infohash"]]
    if multiscrapeCallback:
        info_hashes.extend(multiscrapeCallback(announce))

    defaultdict = {torrent["infohash"]: (-2, -2)}

    url = getUrl(announce, info_hashes)  # whether scrape support
    if url:
        if DEBUG:
            print >> sys.stderr, "TrackerChecking: Checking", url

        try:
            dict = None
            if announce.startswith('http'):
                # print 'Checking url: %s' % url
                dict = getStatus(announce, url, torrent["infohash"], info_hashes)
            elif announce.startswith('udp'):
                dict = getStatusUDP(announce, url, torrent["infohash"], info_hashes)

            if dict:
                if DEBUG:
                    print >> sys.stderr, "TrackerChecking: Result", announce, dict
                return dict
        except:
            if DEBUG:
                print_exc()
            pass
    return defaultdict

# generate the query URL


def getUrl(announce, info_hashes):
    if announce.startswith('http'):
        announce_index = announce.rfind("announce")
        last_index = announce.rfind("/")

        url = announce
        if (last_index + 1 == announce_index):  # srape support
            url = url.replace("announce", "scrape")
        url += "?"
        for info_hash in info_hashes:
            url += "info_hash=" + urllib.quote(info_hash) + "&"
        return url[:-1]

    elif announce.startswith('udp'):
        url = urlparse(announce)
        host = url.netloc
        try:
            port = int(url.port)

        except:
            port = 80

        if host.find(':') > 0:
            try:
                port = int(host[host.find(':') + 1:])
            except:
                port = 80
            host = host[:host.find(':')]

        return (host, port)

    return None  # return None


def getStatus(announce, url, info_hash, info_hashes):
    returndict = {}
    try:
        resp = timeouturlopen.urlOpenTimeout(url, timeout=HTTP_TIMEOUT)
        response = resp.read()

        response_dict = bdecode(response)
        for cur_infohash, status in response_dict["files"].iteritems():
            seeder = max(0, status["complete"])
            leecher = max(0, status["incomplete"])

            returndict[cur_infohash] = (seeder, leecher)

        registerSuccess(announce)
        return returndict

    except IOError:
        registerIOError(announce)
        return {info_hash: (-1, -1)}

    except KeyError:
        try:
            if "flags" in response_dict:  # may be interval problem
                if "min_request_interval" in response_dict["flags"]:
                    return {info_hash: (-3, -3)}
        except:
            pass
    except:
        pass
    return None


def getStatusUDP(announce, url, info_hash, info_hashes):
    # restrict to 74 max
    info_hashes = [info_hash] + info_hashes[:73]
    assert all(len(infohash) == 20 for infohash in info_hashes)

    udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # step 1: Get a connection-id
        action = 0
        connection_id = 0x41727101980
        transaction_id = randint(0, 2147483647)
        msg = pack('!qii', connection_id, action, transaction_id)
        udpSocket.sendto(msg, url)

        result = udpSocket.recv(1024)
        if len(result) >= 16:
            raction, rtransaction_id, rconnection_id = unpack('!iiq', result)
            if raction == action and rtransaction_id == transaction_id:
                # step 2: Send scrape
                action = 2
                transaction_id = randint(0, 2147483647)

                format = "!qii" + "20s" * len(info_hashes)
                data = [rconnection_id, action, transaction_id]
                data.extend(info_hashes)
                msg = pack(format, *data)
                udpSocket.sendto(msg, url)

                # 74 infohashes are roughly 7400 bits
                result = udpSocket.recv(8000)
                if len(result) >= 8:
                    header = result[:8]
                    body = result[8:]

                    raction, rtransaction_id = unpack('!ii', header)
                    if raction == action and rtransaction_id == transaction_id:
                        returndict = {}
                        for infohash in info_hashes:
                            cur = body[:12]
                            body = body[12:]

                            seeders, completed, leechers = unpack('!iii', cur)
                            returndict[infohash] = (seeders, leechers)

                        registerSuccess(announce)
                        return returndict
        else:
            registerIOError(announce)
    except:
        if DEBUG:
            print_exc()
    finally:
        try:
            udpSocket.close()
        except:
            pass

    return {info_hash: (-1, -1)}


def registerIOError(announce):
    if DEBUG:
        print >> sys.stderr, "TrackerChecking: No repsonse for", announce

    ioErrors[announce] = ioErrors.get(announce, 0) + 1
    if len(ioErrors) > 100:
        key = choice(ioErrors.keys())
        del ioErrors[key]


def registerSuccess(announce):
    if announce in ioErrors:
        ioErrors[announce] = max(ioErrors[announce] - 1, 0)

if __name__ == '__main__':
    infohash = unhexlify('174E3CDD9610E79849304FCB9A835CDC6851B6F0')

    print >> sys.stderr, len(infohash)
    tracker = 'udp://tracker.openbittorrent.com:80/announce'
    url = getUrl(tracker, [])
    print >> sys.stderr, getStatusUDP(tracker, url, infohash, [])
