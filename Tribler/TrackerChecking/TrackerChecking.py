# written by Yuan Yuan
# see LICENSE.txt for license information

# single torrent checking without Thread
from BitTornado.bencode import bdecode
from random import shuffle
import urllib, httplib
import socket
import timeouturlopen
from time import time
from traceback import print_exc

HTTP_TIMEOUT = 30 # seconds

def trackerChecking(torrent):    
    single_no_thread(torrent)              
        
def single_no_thread(torrent):
    
    (seeder, leecher) = (-2, -2)        # default dead
    if ( torrent["info"].get("announce-list", "") == "" ):        # no announce-list
        try:
            announce = torrent["info"]["announce"]                    # get the single tracker
            (s, l) = singleTrackerStatus(torrent, announce)
            seeder = max(seeder, s)
            leecher = max(leecher, l)
        except:
            pass
    else:                                                # have announce-list
        for announces in torrent["info"]["announce-list"]:
            a_len = len(announces)
            if (a_len == 0):                            # length = 0
                continue
            if (a_len == 1):                            # length = 1
                announce = announces[0]
                (s, l) = singleTrackerStatus(torrent, announce)
                seeder = max(seeder, s)
                leecher = max(leecher, l)
            else:                                        # length > 1
                aindex = torrent["info"]["announce-list"].index(announces)                                    
                shuffle(announces)
                for announce in announces:                # for eache announce
                    (s, l) = singleTrackerStatus(torrent, announce)
                    seeder = max(seeder, s)
                    leecher = max(leecher, l)
                    if seeder > 0:  # good
                        break
                if (seeder > 0 or leecher > 0):        # put the announce\
                    announces.remove(announce)            # in front of the tier
                    announces.insert(0, announce)                    
                    torrent["info"]["announce-list"][aindex] = announces
#                    print "one changed"
            if (seeder > 0):
                break
    if (seeder == -3 and leecher == -3):
        pass        # if interval problem, just keep the last status
    else:
        torrent["seeder"] = seeder
        torrent["leecher"] = leecher
        if (torrent["seeder"] > 0 or torrent["leecher"] > 0):
            torrent["status"] = "good"
        elif (torrent["seeder"] == 0 and torrent["leecher"] == 0):
            torrent["status"] = "unknown"
#            torrent["seeder"] = 0
#            torrent["leecher"] = 0
        elif (torrent["seeder"] == -1 and torrent["leecher"] == -1):    # unknown
            torrent["status"] = "unknown"
#            torrent["seeder"] = -1
#            torrent["leecher"] = -1
        else:        # if seeder == -2 and leecher == -2, dead
            torrent["status"] = "dead"
            torrent["seeder"] = -2
            torrent["leecher"] = -2
    torrent["last_check_time"] = long(time())
    return torrent


def singleTrackerStatus(torrent, announce):
    # return (-1, -1) means the status of torrent is unknown
    # return (-2. -2) means the status of torrent is dead
    # return (-3, -3) means the interval problem 
    info_hash = torrent["infohash"]
    url = getUrl(announce, info_hash)            # whether scrape support
    if (url == None):                            # tracker url error
        return (-2, -2)                            # use announce instead
    try:
        #print 'Checking url: %s' % url
        (seeder, leecher) = getStatus(url, info_hash)
    except:
        (seeder, leecher) = (-2, -2)
    return (seeder, leecher)

# generate the query URL
def getUrl(announce, info_hash):
    if (announce == -1):                        # tracker url error
        return None                                # return None
    announce_index = announce.rfind("announce")
    last_index = announce.rfind("/")    
    
    url = announce    
    if (last_index +1 == announce_index):        # srape supprot
        url = url.replace("announce","scrape")
    url += "?info_hash=" + info_hash
#    print url
    return url


            
def getStatus(url, info_hash):
    try:
        resp = timeouturlopen.urlOpenTimeout(url,timeout=HTTP_TIMEOUT)
        response = resp.read()
        
    except IOError:
#        print "IOError"
        return (-1, -1)                    # unknown
    except AttributeError:
#        print "AttributeError"
        return (-2, -2)                    # dead
    
    try:
        response_dict = bdecode(response)

    except:
#        print "DeCode Error "  + response
        return (-2, -2)                    # dead
    
    try:
        status = response_dict["files"][info_hash]
        seeder = status["complete"]
        if seeder < 0:
            seeder = 0
        leecher = status["incomplete"]
        if leecher < 0:
            leecher = 0
        
    except KeyError:
#        print "KeyError "  + info_hash + str(response_dict)
        try:
            if response_dict.has_key("flags"): # may be interval problem        
                if response_dict["flags"].has_key("min_request_interval"):
#                    print "interval problem"
                    return (-3 ,-3)
        except:
            pass
#        print "KeyError "  + info_hash + str(response_dict)
        return (-2, -2)                    # dead
    
    return (seeder, leecher)