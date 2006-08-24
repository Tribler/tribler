# written by Yuan Yuan
# see LICENSE.txt for license information

# single torrent checking without Thread
from BitTornado.bencode import bdecode
from random import shuffle
from urllib import urlopen
from time import time


def trackerChecking(torrent):    
    single_no_thread(torrent)              
        
def single_no_thread(torrent):
    
    (seeder, leecher) = (-2, -2)
    if ( torrent["info"].get("announce-list", "") == "" ):        # no announce-list
        try:
            announce = torrent["info"]["announce"]                    # get the single tracker
            (seeder, leecher) = singleTrackerStatus(torrent, announce)
        except:
            print "no tracker"
            pass
    else:                                                # have announce-list
        for announces in torrent["info"]["announce-list"]:
            a_len = len(announces)
            if (a_len == 0):                            # length = 0
                continue
            if (a_len == 1):                            # length = 1
                announce = announces[0]
                (seeder, leecher) = singleTrackerStatus(torrent, announce)
            else:                                        # length > 1
                aindex = torrent["info"]["announce-list"].index(announces)                                    
                shuffle(announces)
                for announce in announces:                # for eache announce
                    (seeder, leecher) = singleTrackerStatus(torrent, announce)
                    if (seeder != 0 or leecher != 0):
                        break;
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
            torrent["seeder"] = 0
            torrent["leecher"] = 0
        elif (torrent["seeder"] == -1 and torrent["leecher"] == -1):
            torrent["status"] = "unknown"
            torrent["seeder"] = 0
            torrent["leecher"] = 0
        else:
            torrent["status"] = "dead"
            torrent["seeder"] = 0
            torrent["leecher"] = 0
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
        (seeder, leecher) = getStatus(url, info_hash)
    except:
        print "Should Never Be Here"
        (seeder, leecher) = (-2, -2)
    return (seeder, leecher)

# generate the query URL
def getUrl(announce, info_hash):
    announce_index = announce.rfind("announce")
    if (announce == -1):                        # tracker url error
        return None                                # return None
    last_index = announce.rfind("/")    
    
    url = announce    
    if (last_index +1 == announce_index):        # srape supprot
        url = url.replace("announce","scrape")
    url += "?info_hash=" + info_hash
#    print url
    return url

def getStatus(url, info_hash):
    try:
        connection = urlopen(url)    
        response = connection.read()    
    except IOError:
#        print "IOError"
        return (-1, -1)                    # unknown
    except AttributeError:
#        print "AttributeError"
        return (-2, -2)                    # dead
    
    try:
        response_dict = bdecode(response)
#        print response
    except:
#        print "DeCode Error "  + response
        return (-2, -2)                    # dead
    
    try:
        status = response_dict["files"][info_hash]
        seeder = status["complete"]
        leecher = status["incomplete"]
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