# written by Yuan Yuan
# see LICENSE.txt for license information

# single torrent checking without Thread
import sys
from Tribler.Core.BitTornado.bencode import bdecode
from random import shuffle
import urllib
import socket
import Tribler.Core.Utilities.timeouturlopen as timeouturlopen
from time import time
from traceback import print_exc

HTTP_TIMEOUT = 30 # seconds

DEBUG = False

def trackerChecking(torrent):    
    single_no_thread(torrent)

def multiTrackerChecking(torrent, multiscrapeCallback):
    return single_no_thread(torrent, multiscrapeCallback)
        
def single_no_thread(torrent, multiscrapeCallback = None):
    multi_announce_dict = {} 
    multi_announce_dict[torrent['infohash']] = (-2, -2)
    
    #determine trackers
    trackers = []
    if (torrent["info"].get("announce-list", "")==""):  # no announce-list
        trackers.append(torrent["info"]["announce"])
    else:                                               # have announce-list
        for announces in torrent["info"]["announce-list"]:
            a_len = len(announces)
            if (a_len == 0):                            # length = 0
                continue

            if (a_len == 1):                            # length = 1
                trackers.append(announces[0])
                
            else:                                       # length > 1
                aindex = torrent["info"]["announce-list"].index(announces)                                    
                shuffle(announces)
                
                # Arno: protect against DoS torrents with many trackers in announce list. 
                trackers.extend(announces[:10])
    

    trackers = [tracker for tracker in trackers if tracker.startswith('http')]
    for announce in trackers:
        announce_dict = singleTrackerStatus(torrent, announce, multiscrapeCallback)
        
        for key, values in announce_dict.iteritems():
            
            #merge results
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
    
    #modify original torrent
    (seeder, leecher) = multi_announce_dict[torrent["infohash"]]
    if (seeder == -3 and leecher == -3):
        pass        # if interval problem, just keep the last status
    else:
        torrent["seeder"] = seeder
        torrent["leecher"] = leecher
        if torrent["seeder"] > 0 or torrent["leecher"] > 0:
            torrent["status"] = "good"
            
        elif torrent["seeder"] == 0 and torrent["leecher"] == 0:
            torrent["status"] = "unknown"
            
        elif torrent["seeder"] == -1 and torrent["leecher"] == -1:
            torrent["status"] = "unknown"
            
        else:
            torrent["status"] = "dead"
            torrent["seeder"] = -2
            torrent["leecher"] = -2
            
    torrent["last_check_time"] = long(time())
    
    return multi_announce_dict

def singleTrackerStatus(torrent, announce, multiscrapeCallback):
    # return (-1, -1) means the status of torrent is unknown
    # return (-2. -2) means the status of torrent is dead
    # return (-3, -3) means the interval problem
    info_hashes = [torrent["infohash"]]
    if multiscrapeCallback:
        info_hashes.extend(multiscrapeCallback(announce))
    
    if DEBUG:
        print >>sys.stderr,"TrackerChecking: Checking", announce, "for", info_hashes
    
    defaultdict = {torrent["infohash"]: (-2, -2)}
    
    url = getUrl(announce, info_hashes)            # whether scrape support
    if url:
        try:
            #print 'Checking url: %s' % url
            dict = getStatus(url, torrent["infohash"], info_hashes)
            
            if dict:    
                if DEBUG:
                    print >>sys.stderr,"TrackerChecking: Result", dict
                return dict
        except:
            pass
    return defaultdict 

# generate the query URL
def getUrl(announce, info_hashes):
    if (announce == -1) or not announce.startswith('http'):     # tracker url error
        return None                                             # return None
    announce_index = announce.rfind("announce")
    last_index = announce.rfind("/")    
    
    url = announce    
    if (last_index +1 == announce_index):        # srape supprot
        url = url.replace("announce","scrape")
    url +="?"
    for info_hash in info_hashes:
        url += "info_hash=" + urllib.quote(info_hash) + "&"
    return url[:-1]
            
def getStatus(url, info_hash, info_hashes):
    returndict = {}
    try:
        resp = timeouturlopen.urlOpenTimeout(url,timeout=HTTP_TIMEOUT)
        response = resp.read()
        
        response_dict = bdecode(response)
        for cur_infohash, status in response_dict["files"].iteritems():
            seeder = max(0, status["complete"])
            leecher = max(0, status["incomplete"])
            
            returndict[cur_infohash] = (seeder, leecher)
        
        return returndict
    
    except IOError:
        return {info_hash: (-1, -1)}
    
    except KeyError:
        try:
            if response_dict.has_key("flags"): # may be interval problem        
                if response_dict["flags"].has_key("min_request_interval"):
                    return {info_hash: (-3 ,-3)}
        except:
            pass
    except:
        pass
    
    return None