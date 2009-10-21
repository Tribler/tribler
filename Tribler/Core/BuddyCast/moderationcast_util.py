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
    r = ( type(infohash) == str or type(infohash) == unicode)
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid infohash: type(infohash) ==", str(type(infohash))+\
            ", len(infohash) ==", str(len(infohash))
    return r

def validPermid(permid):
    """ Returns True iff permid is a valid Tribler Perm-ID """
    r = (type(permid) == str or type(permid)== unicode) and len(permid) <= 125
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
        if DEBUG: 
            print >>sys.stderr, "validvotecastmsg: ", repr(record)
        if not validPermid(record[0]):
            if DEBUG:
                print >> sys.stderr, "not valid permid: ", repr(record[0]) 
            return False
        if not type(record[1]) == int:
            if DEBUG:
                print >> sys.stderr, "not int: ", repr(record[1]) 
            return False
    
    return True


def validChannelCastMsg(channelcast_data):
    """ Returns true if ChannelCastMsg is valid,
    format: {'signature':{'publisher_id':, 'publisher_name':, 'infohash':, 'torrenthash':, 'torrent_name':, 'timestamp':, 'signature':}} 
     """
    if not isinstance(channelcast_data,dict):
        return False
    for signature, ch in channelcast_data.items():
        if not isinstance(ch,dict):
            if DEBUG:
                print >>sys.stderr,"rvalidChannelCastMsg: a: value not dict"
            return False
        if len(ch) !=6:
            if DEBUG:
                print >>sys.stderr,"rvalidChannelCastMsg: a: #keys!=6"
            return False
        if not ('publisher_id' in ch and 'publisher_name' in ch and 'infohash' in ch and 'torrenthash' in ch and 'torrentname' in ch and 'time_stamp' in ch):
            if DEBUG:
                print >>sys.stderr,"validChannelCastMsg: a: key missing, got",d.keys()
            return False
        if not (validPermid(ch['publisher_id']) and (isinstance(ch['publisher_name'],str) or isinstance(ch['publisher_name'], unicode)) and validInfohash(ch['infohash']) and validInfohash(ch['torrenthash'])
                and (isinstance(ch['torrentname'],str) or isinstance(ch['torrentname'],unicode)) and validTimestamp(ch['time_stamp'])):
            if DEBUG:
                print >>sys.stderr,"validChannelCastMsg: something not valid"
            return False
        # now, verify signature
        l = (ch['publisher_id'],ch['infohash'], ch['torrenthash'], ch['time_stamp'])
        if not verify_data(bencode(l),str2bin(ch['publisher_id']),str2bin(signature)):
            if DEBUG:
                print >>sys.stderr, "validChannelCastMsg: verification failed!"
            return False
    return True
     
#*************************************************

def voteCastMsgToString(data):
    return repr(data)
