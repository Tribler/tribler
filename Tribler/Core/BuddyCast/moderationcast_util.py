# Written by Vincent Heinink and Rameez Rahman
# see LICENSE.txt for license information
#
#Utilities for moderationcast (including databases)
#
import sys

from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
#For validity-checks
from types import StringType, ListType, DictType
from time import time
from Tribler.Core.BitTornado.bencode import bencode
from Tribler.Core.Overlay.permid import verify_data
from os.path import exists, isfile


DEBUG = False

TIMESTAMP_IN_FUTURE = 5 * 60    # 5 minutes is okay

#*****************Validity-checks*****************
def validInfohash(infohash):
    """ Returns True iff infohash is a valid infohash """
    r = type(infohash) == str
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid infohash: type(infohash) ==", str(type(infohash))+\
            ", len(infohash) ==", str(len(infohash))
    return r

def validPermid(permid):
    """ Returns True iff permid is a valid Tribler Perm-ID """
    r = type(permid) == str and len(permid) <= 120
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid permid: type(permid) ==", str(type(permid))+\
            ", len(permid) ==", str(len(permid))
    return r

def now():
    """ Returns current-system-time in UTC, seconds since the epoch (type==int) """
    return int(time())

def validTimestamp(timestamp):
    """ Returns True iff timestamp is a valid timestamp """
    r = timestamp is not None and type(timestamp) == int and timestamp > 0 and timestamp <= now() + TIMESTAMP_IN_FUTURE
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid timestamp"
    return r

def validVoteCastMsg(data):
    """ Returns True if VoteCastMsg is valid, ie, be of type [(mod_id,vote)] """
    if data is None:
        print >> sys.stderr, "data is None"
        return False
     
    if not type(data) == ListType:
        print >> sys.stderr, "data is not List"
        return False
    
    for record in data:
        print >>sys.stderr, "validvotecastmsg: ", repr(record)
        if not validPermid(record[0]):
            print >> sys.stderr, "not valid permid: ", repr(record[0]) 
            return False
        if not type(record[1]) == int:
            print >> sys.stderr, "not int: ", repr(record[1]) 
            return False
    
    return True

def validChannelCastMsg(data):
    """ Returns True if ChannelCastMsg is valid, ie, it is of type [(publisher_id, timestamp)] """
    if data is None: 
        print >> sys.stderr, "data is None"
        return False
    
    if not type(data) == ListType:
        print >> sys.stderr, "data is not List"
        return False
    
    for record in data:
        if not validPermid(record[0]):
            print >> sys.stderr, "not valid permid: ", repr(record[0]) 
            return False
        if not validTimestamp(record[1]):
            print >> sys.stderr, "not valid timestamp: ", repr(record[1])
            return False
    
    return True
    
#*************************************************

def voteCastMsgToString(data):
    return repr(data)
