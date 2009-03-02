#Utilities for moderationcast (including databases)
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from sha import sha
DEBUG = False

# NO_RECENT_OWN_MODERATIONS_PER_HAVE = 13
# NO_RANDOM_OWN_MODERATIONS_PER_HAVE = 12
# NO_RECENT_FORWARD_MODERATIONS_PER_HAVE = 13
# NO_RANDOM_FORWARD_MODERATIONS_PER_HAVE = 12
# NO_MODERATIONS_PER_HAVE = NO_RECENT_OWN_MODERATIONS_PER_HAVE + NO_RANDOM_OWN_MODERATIONS_PER_HAVE +\
#                             NO_RECENT_FORWARD_MODERATIONS_PER_HAVE + NO_RANDOM_FORWARD_MODERATIONS_PER_HAVE
# UPLOAD_BANDWIDTH_LIMIT = 5*1024    #5KByte/s
# DOWNLOAD_BANDWIDTH_LIMIT = 20*1024    #20KByte/s

# MAX_HAVE_LENGTH = NO_MODERATIONS_PER_HAVE * 40    #40 bytes per (infohash, timestamp, size-combination)?
# MAX_REQUEST_LENGTH = NO_MODERATIONS_PER_HAVE * 25    #25 bytes per infohash?

SINGLE_HAVE_LENGTH = 40                 #40 bytes per (infohash, timestamp, size-combination)?
SINGLE_REQUEST_LENGTH = 25              #25 bytes per infohash?
MAX_REPLY_LENGTH = 2 * 1024 * 1024      #2 MByte

HAVE_COMPRESSION = True
REQUEST_COMPRESSION = True
REPLY_COMPRESSION = True

TIMESTAMP_IN_FUTURE = 5 * 60    # 5 minutes is okay
MAX_THUMBNAIL_SIZE = 20 * 1024    # 20 Kilobyte
MAX_SUBTITLE_SIZE = 100 * 1024    # 100 Kilobyte
MAX_DESCRIPTION_SIZE = 2 * 1024    # 2 Kilobyte
MAX_TAGS = 50                # 50 tags max
MAX_TAG_SIZE = 30                # 30 characters max per tag

BLOCK_HAVE_TIME = 30    # Do not reply a have message with a have message, to peers that have received one in the last 30 seconds

LANGUAGES = {                #The language-codes and their representations for languages that we allow (ISO-639-3)
    'ron':'Romanian',
    'jpn':'Japanese',
    'swe':'Swedish',
    'por':'Portuguese',
    'ita':'Italian',
    'ara':'Arabic',
    'pol':'Polish',
    'nld':'Dutch',
    'ind':'Indonesian',
    'spa':'Spanish',
    'fra':'French',
    'est':'Estonian',
    'ell':'Modern Greek (1453-)',
    'eng':'English',
    'hrv':'Croatian',
    'tur':'Turkish',
    'heb':'Hebrew',
    'kor':'Korean',
    'fin':'Finnish',
    'hun':'Hungarian',
    'fas':'Persian',
    'dan':'Danish',
    'ces':'Czech',
    'bul':'Bulgarian',
    'rus':'Russian',
    'nor':'Norwegian',
    'vie':'Vietnamese',
    'deu':'German',
    'srp':'Serbian',
    'slk':'Slovak',
    'zho':'Chinese'
}

#For debugging messages
import sys
from traceback import print_exc

#For validity-checks
from types import StringType, ListType, DictType
from time import time
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Overlay.permid import verify_data
from os.path import exists, isfile
from M2Crypto import Rand,EC,EVP
#For BlockList
import thread

#For image
from mimetypes import guess_type
from cStringIO import StringIO

#For Messages-toString
from binascii import hexlify
from time import gmtime, asctime
from Tribler.Core.Utilities.utilities import show_permid_short

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

def validSignature(moderation):
    """ Returns True iff the (signature, moderator) in moderation is correct for this moderation """
   
    #return True
    #UNFREEZE LATER
    print >>sys.stderr, "Checking signature of moderation:", repr(moderation)
    blob = str2bin(moderation['signature'])
    permid = str2bin(moderation['mod_id'])
    #Plaintext excludes signature:
    del moderation['signature']
    plaintext = bencode(moderation)
    moderation['signature'] = bin2str(blob)
    signature = verify_data(plaintext,permid, blob)
    
    print >> sys.stderr,"Checking signature of moderation after verify_data:", repr(moderation)    

    r = verify_data(plaintext, permid, blob)
    if not r:
        print >>sys.stderr, "Invalid signature"
    else:
        print >>sys.stderr, "Proper signature:", moderation['signature']
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

def validSize(size):
    """ Returns True iff size is a valid size """
    r = size is not None and (type(size) == int or type(size) == double) and size > 0
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid size"
    return r

def validThumbnail(thumbnail):
    """ Returns True iff thumbnail is a valid thumbnail """
    r = type(thumbnail) == str
    if not r:
        if DEBUG:
            print >>sys.stderr, "Invalid thumbnail: type(thumbnail) ==", str(type(thumbnail))
        return False
    
    r = len(thumbnail) <= MAX_THUMBNAIL_SIZE
    if not r:
        print >>sys.stderr, "Invalid thumbnail: len(thumbnail) ==", str(len(thumbnail))
        return False
        
    return True

def validUIThumbnail(thumbnail):
    """ Returns True iff thumbnail is a valid thumbnail """
    r = type(thumbnail) == str and exists(thumbnail) and isfile(thumbnail)
    if not r:
        print >>sys.stderr, "Invalid UIthumbnail"    
    return r

def validDBThumbnail(thumbnail):
    """ Returns True """
    return True

def validDescription(description):
    """ Returns True iff description is a valid description """
    r = (type(description) == str or type(description) == unicode) and len(description) <= MAX_DESCRIPTION_SIZE
    if not r:
        print >>sys.stderr, "Invalid DBDescription"
    return r

def validSubtitles(subtitles):
    """ Returns True iff subtitles is a valid collection of subtitles """
    if type(subtitles) != dict:    #Dictionary
        print >>sys.stderr, "Invalid subtitles: type(subtitles) ==", str(type(subtitles))
        return False
    
    for (language, data) in subtitles.iteritems():                                #Valid language and data
        if not validLanguage(language):
            return False
        if type(data) != str or len(data) > MAX_SUBTITLE_SIZE:
            print >>sys.stderr, "Invalid subtitle:", language, "has invalid data"
            return False
    
    return True                                                    #Ok

def validUISubtitles(subtitles):
    """ Returns True iff subtitles is a valid collection of subtitles """
    if type(subtitles) != dict:    #Dictionary
        return False
    
    for (language, file) in subtitles.iteritems():                                #Valid language and file
        if not validLanguage(language):
            return False
        if type(file) != str or not exists(file) or not isfile(file):
            print >>sys.stderr, "Invalid UISubtitle:", language, "has invalid file"
            return False
    
    return True  

def validDBSubtitles(subtitles):
    """ Returns True """
    return True

def validTags(tags):
    """ Returns True iff tags is a valid collection of tags """
    if type(tags) != tuple and type(tags) != list:
        print >>sys.stderr, "Invalid tags: non-list/tuple"
        return False
    
    if len(tags) > MAX_TAGS:
        print >>sys.stderr, "Invalid tags: too many tags:", str(len(tags))
        return False
    
    for tag in tags:
        if (type(tag) != str and type(tag) != unicode) or len(tag) > MAX_TAG_SIZE:
            print >>sys.stderr, "Invalid tags: too long tag:", tag
            return False
    
    return True

def validLanguage(language):
    """ Returns True iff language is a valid language """
    r = (type(language) == str or type(language) == unicode) and language in LANGUAGES.keys()
    if not r:
        print >>sys.stderr, "Invalid language"
    return r

def validUILanguage(language):
    """ Returns True iff language is a valid language """
    r = (type(language) == str or type(language) == unicode) and language in LANGUAGES.values()
    if not r:
        print >>sys.stderr, "Invalid UIlanguage"
    return r

def validDBModeration(moderation):
   
    required = {'infohash':validInfohash, 'mod_id':validPermid, 'time_stamp':validTimestamp, 'signature':validSignature, 'size':validSize}    
    
    #Check for DictType
    if type(moderation) != DictType:
        print >> sys.stderr, "moderation is non-DictType, but of type:", str(type(moderation))
        return False
    
    #Check required-keys and their values
    for key, check_function in required.iteritems():
        if not moderation.has_key(key):
            print >> sys.stderr, "moderation does not have", key+"-key"
            return False
        if not check_function(moderation[key]):
            print >> sys.stderr, "moderation has invalid required", key+"-value"
            return False
    
   
    return True

def validUIModeration(moderation):
   
    required = {'infohash':validInfohash, 'mod_id':validPermid, 'time_stamp':validTimestamp, 'signature':lambda x:True}
    
    #Check for DictType
    if type(moderation) != DictType:
        print >> sys.stderr, "moderation is non-DictType, but of type:", str(type(moderation))
        return False
    
    #Check required-keys and their values
    for key, check_function in required.iteritems():
        if not moderation.has_key(key):
            print >> sys.stderr, "moderation does not have", key+"-key"
            return False
        if not check_function(moderation[key]):
            print >> sys.stderr, "moderation has invalid required", key+"-value"
            return False
    
    return True    

def validModeration(moderation):
    
    required = {'infohash':validInfohash, 'mod_id':validPermid, 'time_stamp':validTimestamp, 'signature':lambda x:validSignature(moderation)}
    
    #Check for DictType
    if type(moderation) != DictType:
        print >> sys.stderr, "moderation is non-DictType, but of type:", str(type(moderation))
        return False
    
    #Check required-keys and their values
    for key, check_function in required.iteritems():
        if not moderation.has_key(key):
            print >> sys.stderr, "moderation does not have", key+"-key"
            return False
        if not check_function(moderation[key]):
            print >> sys.stderr, "moderation has invalid required", key+"-value"
            return False
    
    return True

def validModerationCastHaveMsg(data):
    """ MODERATIONCAST_HAVE-message should be a of type: [(infohash, time_stamp)] """

    if data is None or not type(data) == ListType:
        print >>sys.stderr, "validModerationCastMsg: non-ListType"
        return False
            
    for item in data:
        if not type(item) == ListType or len(item) != 2:
            print >>sys.stderr, "validModerationCastMsg: item non-3-list:"
            print >>sys.stderr, "type(item):", str(type(item))
            print >>sys.stderr, "len(item) != 3:", str(len(item) != 3)
            return False
            
        (infohash, timestamp) = item
        if not validInfohash(infohash) or not validTimestamp(timestamp):
            print >>sys.stderr, "validModerationCastMsg: item invalid:"
            print >>sys.stderr, "validInfohash(infohash):", str(validInfohash(infohash))
            print >>sys.stderr, "validTimestamp(timestamp):", str(validTimestamp(timestamp))
            #print >>sys.stderr, "validSize(size):", str(validSize(size))
            return False
        
    return True

def validModerationCastRequestMsg(data):
    """ Returns True iff MODERATIONCAST_REQUEST-message is valid, shoud be of type: [infohash] """
    if data is None or not type(data) == ListType:
        return False
            
    for item in data:
        if not validInfohash(item):
            return False

    return True

def validModerationCastReplyMsg(data):
    """ Returns True iff MODERATIONCAST_REPLY-message is valid, should be a of type: [moderation] """
    if data is None or not type(data) == ListType:
        return False
            
    for item in data:
        if not validModeration(item):
            return False

    return True

def validVoteCastMsg(data):
    """ Returns True if VoteCastMsg is valid, ie, be of type [(mod_id,vote) """
    if data is None or not type(data) == ListType:
        return False
    
    for record in data:
        if not type(record[0]) == StringType:
            return False
        if not type(record[1]) == int:
            return False
        
    
    return True

    
#*************************************************

def moderationCastHaveMsgToString(data):
    """ Pre:    data is a valid MODERATIONCAST_HAVE-message
        Post:   returns a string-representation of the MODERATIONCAST_HAVE-message
    """
    return repr(data)

def moderationCastRequestMsgToString(data):
    """ Pre:    data is a valid MODERATIONCAST_REQUEST-message
        Post:   returns a string-representation of the MODERATIONCAST_REQUEST-message
    """
    return repr(data)

def moderationCastReplyMsgToString(data):
    """ Pre:    data is a valid MODERATIONCAST_REPLY-message
        Post:   returns a string-representation of the MODERATIONCAST_REPLY-message
    """
    return repr(data)

def voteCastMsgToString(data):
    return repr(data)

class BandwidthLimiter:
    """ BandwidthLimiter keeps track of the bandwidth used (upload or download) and can be used
        to limit the bandwidth a process uses.
        BandwidthLimiter can handle multi-threading.
    """
    def __init__(self, bandwidth_limit, interval_size=60):
        """ Pre: bandwidth_limit >= 0 and interval_size > 0
            Post: Returns a BandwidthLimiter instance that has a bandwidth limit of bandwidth_limit
                  units per second and averages over interval_size seconds.
        """
        assert bandwidth_limit >= 0
        assert interval_size > 0
        self.limit = bandwidth_limit
        self.interval_size = interval_size
        self.usage = []
        self._lock = thread.allocate_lock()
    
    def use(self, size, t=None):
        """ Pre: size >= 0
            Post: Fact of using size units at time t is noted
        """
        if t == None:
            t = time()
        assert size >= 0
        self._lock.acquire()
        
        self.usage.append( (size, t) )
        #clean old usage
        usage = [(size, t) for (size, t) in self.usage if t + self.interval_size >= time()]
        self.usage = usage
        
        self._lock.release()
    
    def getAvailableSize(self):
        """ Returns the available size within the current interval [now-interval_size, now] """
        self._lock.acquire()
        
        stoptime = time()
        starttime = stoptime-self.interval_size
        used = sum([size for (size, t) in self.usage if t >= starttime and t <= stoptime])
        result = (stoptime - starttime) * self.limit - used
        
        self._lock.release()
        
        return result
    
    def getBandwidthUsed(self):
        """ Returns the bandwith used within the current interval [now-interval_size, now] """
        self._lock.acquire()
        
        stoptime = time()
        starttime = stoptime-self.interval_size
        used = sum([size for (size, t) in self.usage if t >= starttime and t <= stoptime])
        result = used / (stoptime - starttime)
        
        self._lock.release()
        
        return result

class SustainableBandwidthLimiter(BandwidthLimiter):
    """ SustainableBandwidthLimiter is a subclass of BandwidthLimiter that can be used to distribute
        the bandwidth more evenly between requests. In this subclass the getAvailableSize-method is
        overwritten to return a number of units based on the requests in the past minute.
    """
    def __init__(self, bandwidth_limit, interval_size=60, minimum_size=50*1024):
        """ Pre: bandwidth_limit >= 0 and interval_size > 0 and
                 minimum_size > 0 and minimum_size <= bandwidth_limit * interval_size
            Post: Returns a SustainableBandwidthLimiter-object with given parameters
        """
        BandwidthLimiter.__init__(self, bandwidth_limit, interval_size)
        assert minimum_size >= 0
        assert minimum_size <= bandwidth_limit * interval_size
        self.minimum_size = minimum_size
        self.requests = []
        self._lock2 = thread.allocate_lock()
    
    def getAvailableSize(self):
        """ Returns the number of units reserved to a request-allocation, with a minimum of self.minimum_size,
            or 0 if the mimimum_size cannot be allocated anymore.
        """
        #Check to see if there is enough bandwidth left:
        self._lock2.acquire()
        
        #Interval
        stoptime = time()
        starttime = stoptime-self.interval_size
        
        #Update requests (calls to getAvailableSize())
        self.requests.append(stoptime)
        requests = [t for t in self.requests if t >= starttime and t <= stoptime]
        self.requests = requests
        
        available = BandwidthLimiter.getAvailableSize(self)
        if available <= self.minimum_size:
            self._lock2.release()
            return 0
        
        tries_in_interval = max(len(self.requests), 1)
        
        self._lock2.release()
        
        #Return the number of units reserved to a request-allocation, with a minimum of self.minimum_size
        return max(self.limit * self.interval_size / tries_in_interval, self.minimum_size)

#class Image:
#    def __init__(self, path):
#        assert type(path) == str
#        #Path
#        self.path = path
#        
#        #Image
#        self.image = wx.Image(path)
#        
#        #Binary
#        FILE = open(path,"rb")
#        self.binary = FILE.read()
#        FILE.close()
#
#    def getData(self):
#        return self.binary
#
#    def getImage(self):
#        return self.image

class BlockList:
    """ BlockList keeps track of a list of (hashable) items that are blocked for a certain time 
        The BlockList has a fixed block-time, after which the items are not blocked anymore,
        this time is set by the constructor-parameter blocktime
        By default, after addition of an item the BlockList will be cleaned (old items removed),
        however this can be done manually by calling clean()
        BlockList can handle multi-threading
    """
    
    def __init__(self, blocktime, autoclean=True):
        """ Returns a BlockList-instance, with a blocktime of blocktime seconds
            Setting autoclean to False will give the user the responsibility of cleaning this instance (use clean())
        """
        assert type(blocktime) == float or type(blocktime) == int or type(blocktime) == double
        self._blocktime = blocktime
        self._data = {}
        self._autoclean = autoclean
        self._lock = thread.allocate_lock()
        if DEBUG:
            print "BlockList("+str(blocktime)+", "+str(autoclean)+") created."
    
    def add(self, item):
        """ Pre:     item is hashable
            Post:    Blocklist contains item for self.blocktime seconds
        """
        assert self._hashable(item)    #Item must be hashable
        
        self._lock.acquire()
        
        self._data[item] = self._now()
        if self._autoclean:
            self._clean()
        
        self._lock.release()

    def remove(self, item):
        """ Pre:    item is hashable
            Post:   Blocklist does not contain item
        """
        assert self._hashable(item)    #Item must be hashable
        
        self._lock.acquire()
        
        if item in self._data:
            del self.list[item]

        self._lock.release()

    def blocked(self, item):
        """ Pre:    item is hashable
            Post:   Returns true iff the item is blocked
        """
        assert self._hashable(item)    #Item must be hashable
        
        self._lock.acquire()
        
        r = None
        if not item in self._data:
            r = False
        elif self._data[item] + self._blocktime >= self._now():
            r = True
        else:
            del self._data[item]
            r = False

        self._lock.release()
        if DEBUG:
            print "BlockList returning:", str(r)
        return r

    def clean(self):
        """ Removes entries from the blocklist that have outlived their blocktime """
        self._lock.acquire()
        
        self._clean()

        self._lock.release()

    def _clean(self):
        """ USE clean()!!! """
        index = 0
        keys = self._data.keys()
        for key in keys:
            if self._data[key] + self._blocktime < self._now():
                del self._data[key]

    def _now(self):
        """ Returns the current systemtime (UTC) """
        return time()

    def _hashable(self, item):
        """ Returns True iff item is hashable (can be used as a dictionary-key) """
        if '__hash__' in dir(item):
            try:
                item.__hash__()
                return True
            except:
                return False
