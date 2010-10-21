# Written by Andrea Reale
# see LICENSE.txt for license information



from Tribler.Core.BitTornado.BT1.MessageID import SUBS, GET_SUBS
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import \
    LanguagesProvider
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import \
    SubtitleMsgHandlerException
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FOURTEENTH
from Tribler.Core.Utilities import utilities
from Tribler.Core.Utilities.utilities import show_permid_short, validInfohash, \
    validPermid, bin2str, uintToBinaryString, binaryStringToUint
from time import time
from traceback import print_exc
import sys
import threading
    
SUBS_LOG_PREFIX = "subtitles: "

REQUEST_VALIDITY_TIME = 10 * 60 #10 minutes
CLEANUP_PERIOD = 5 * 60#5 minutes

DEBUG = False
    
class SubsMessageHandler(object):
    
    def __init__(self, overlayBridge, tokenBucket, maxSubsSize):
        self._languagesUtility = LanguagesProvider.getLanguagesInstance()
        self._overlay_bridge = overlayBridge
        
        # handleMessage() is called by the OLThread
        # registerListener is called by the OLThread
        # no synchronization should be needed for this list :)
        self._listenersList = list()
        
        self._tokenBucket = tokenBucket
        
        #controls the interval the uploadQueue gets checked
        self._nextUploadTime = 0
        
        
        #dictionary of type { "".join(channel_id,infohash) : _RequestedSubtitlesEntry}
        #bits get cleaned when subtitles are received
        #when the bitmask is 000 the entry is removed from the dictionary
        #also entries older then REQUEST_VALIDITY_TIME get dropped
        
        self.requestedSubtitles = {}
        self._requestsLock = threading.RLock()
        
        self._nextCleanUpTime = int(time()) + CLEANUP_PERIOD

        #subtitles to send get queued in this queue
        #each subtitle message to send is a dictionary whose keys are:
        #permid: destination of the message
        #channel_id: identifier of the channel from which the subtitles to upload are
        #infohash: identifier of the torrent for which the subtitles to upload are
        #subtitles: a dictionary of the form {langCode : path} for the subtitles to send
        #selversion: 
    
        self._uploadQueue = []
        self._requestValidityTime = REQUEST_VALIDITY_TIME
        self._maxSubSize = maxSubsSize
        
        
    def setTokenBucket(self, tokenBucket):
        assert tokenBucket is not None
        self._tokenBucket = tokenBucket
        
    def getTokenBucket(self):
        return self._tokenBucket
    
    tokenBucket = property(getTokenBucket,setTokenBucket)
    
    def _getRequestedSubtitlesKey(self, channel_id, infohash):
        #requested subtitle is a dictionary whose keys are the
        #concatenation of (channel_id,infohash)

        return "".join((channel_id, infohash))
    
    def sendSubtitleRequest(self, dest_permid, requestDetails, 
                            msgSentCallback = None, usrCallback = None, selversion=-1):
        """
        Create and send a subtitle request to dest_permid.
        
        Creates, encodes and sends (through the OLBridge) an GET_SUBS request
        to the given dest_permid. Notice that even when this method return
        succesfully the message by have been still not sent. 
        
        @param dest_permid: the permid of the peer where the message should be 
                            sent. Binary.
        @param requestDetails: a dictionary containing the details of the request
                               to be sent:
                               a 'channel_id' entry which is the binary channel
                               identifier (permid) of the desired subtitles
                               a 'infohash' entry which is the binary infohash
                               of the torrent the requested subtitles refer to
                               a 'languages' entry which is a list of 3-characters
                               codes identifying the need subtitles
        @type msgSentCallback: function
        @param msgSentCallback: a function that will be called when the message has been
                          sent. It must have 5 parameters: exc (bounded to a possible
                          exception), dest_permid, channel_id, infohash, bitmask)
        @type usrCallback: function
        @param usrCallback: a function that will be called whenever some of the requested
                      subtitles are retrieved. Only one parameter: ie a list that will
                      be bound to the received language codes
                          
        @raise SubtitleMsgHandlerException: if something fails before attempting
                                            to send the message. 
        """

        
        channel_id = requestDetails['channel_id']
        infohash = requestDetails['infohash']
        languages = requestDetails['languages']
        
        bitmask = self._languagesUtility.langCodesToMask(languages)
        if bitmask != 0:
            try:
                # Optimization: don't connect if we're connected, although it won't 
                # do any harm.
                if selversion == -1: # not currently connected
                    self._overlay_bridge.connect(dest_permid,
                                                lambda e, d, p, s:
                                                self._get_subs_connect_callback(e, d, p, s, channel_id,
                                                                                infohash, bitmask,
                                                                                msgSentCallback, usrCallback))
                else:
                    self._get_subs_connect_callback(None, None, dest_permid,
                                                   selversion, channel_id, infohash,
                                                   bitmask, msgSentCallback, usrCallback)
                
            except Exception,e:
                if DEBUG:
                    print >> sys.stderr, SUBS_LOG_PREFIX + "Unable to send: %s" % str(e)
                raise SubtitleMsgHandlerException(e)
        else:
            raise SubtitleMsgHandlerException("Empty request, nothing to send")
        
        
    def sendSubtitleResponse(self, destination, response_params, selversion = -1):
        """
        Send a subtitle response message to destination permid.
        
        @param destination: the permid of the destionation of the message
        @param response_params: a tuple containing channel_id,infohash, and a 
                                dictionary of contents, in that order
        @type selversion: int
        @param selversion: the protocol version of the destination (default -1)
        """
        
        channel_id, infohash, contentsList = response_params
        
                
        task = {
                'permid' : destination,
                'channel_id' : channel_id,
                'infohash' : infohash,
                'subtitles' : contentsList,
                'selversion' : selversion
                }
        

        self._uploadQueue.append(task)
        
        if int(time()) >= self._nextUploadTime:
            self._checkingUploadQueue()
            
        return True
        
    
    def handleMessage(self, permid, selversion, message):
        """
        Must return True or False (for what I understood a return value of
        false closes the connection with permid, but I'm still not sure)
        """
        t = message[0]
        
        if t == GET_SUBS:   # the other peer requests a torrent
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Got GET_SUBS len: %s from %s" % \
                      (len(message), show_permid_short(permid))
            return self._handleGETSUBS(permid, message, selversion)
        elif t == SUBS:     # the other peer sends me a torrent
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Got SUBS len: %s from %s" %\
                     (len(message), show_permid_short(permid))

            return self._handleSUBS(permid, message, selversion)
        else:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Unknown Overlay Message %d" % ord(t)
            return False
    
    
    def _handleGETSUBS(self,permid, message, selversion):
        
        if selversion < OLPROTO_VER_FOURTEENTH:
            if DEBUG:
                print >> sys.stderr, "The peer that sent the GET_SUBS request has an old" \
                     "protcol version: this is strange. Dropping the msg"
            return False
        decoded = self._decodeGETSUBSMessage(message)
        
        if decoded is None:
            if DEBUG:
                print >> sys.stderr, "Error decoding a GET_SUBS message from %s" %\
                      utilities.show_permid_short(permid)
            return False
    
        if DEBUG:
            channel_id, infohash, languages = decoded
            bitmask = self._languagesUtility.langCodesToMask(languages)
            print >> sys.stderr, "%s, %s, %s, %s, %d, %d" % ("RG", show_permid_short(permid), 
                                                     show_permid_short(channel_id),
                                                     bin2str(infohash), bitmask, len(message))
        
        # no synch on _listenersList since both this method
        # and the registerListener method are called by
        # the OLThread
        for listener in self._listenersList:
            listener.receivedSubsRequest(permid, decoded, selversion)
        
        return True
    
    
    
    def _handleSUBS(self, permid, message, selversion):
        if selversion < OLPROTO_VER_FOURTEENTH:
            if DEBUG:
                print >> sys.stderr, "The peer that sent the SUBS request has an old" \
                     "protcol version: this is strange. Dropping the msg"
            return False
        
        decoded = self._decodeSUBSMessage(message)
        
        if decoded is None:
            if DEBUG:
                print >> sys.stderr, "Error decoding a SUBS message from %s" %\
                      utilities.show_permid_short(permid)
            return False
        
        
        channel_id, infohash, bitmask,contents = decoded
        #if no subtitle was requested drop the whole message
        
        if DEBUG:
            print >> sys.stderr, "%s, %s, %s, %s, %d, %d" % ("RS", show_permid_short(permid), 
                                                     show_permid_short(channel_id),
                                                     bin2str(infohash), bitmask, len(message))
        
        

        requestedSubs = self._checkRequestedSubtitles(channel_id,infohash,bitmask) 
        if requestedSubs == 0:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Received a SUBS message that was not"\
                      " requested. Dropping"
            return False
        
        requestedSubsCodes = self._languagesUtility.maskToLangCodes(requestedSubs)
        #drop from the contents subtitles that where not requested
        
        
        for lang in contents.keys():
            if lang not in requestedSubsCodes:
                del contents[lang]
        
        #remove the received subtitles from the requested 
        callbacks = \
            self._removeFromRequestedSubtitles(channel_id, infohash, bitmask)

        
        
        #the receiver does not need the bitmask
        tuple = channel_id, infohash, contents
        
        # no synch on _listenersList since both this method
        # and the registerListener method are called by
        # the OLThread
        for listener in self._listenersList:
            listener.receivedSubsResponse(permid, tuple, callbacks, selversion)
        
    
        return True
    
    def registerListener(self, listenerObject):
        '''
        Register an object to be notifed about the reception of subtitles
        related messages.

        Currently the messages that are notified are:
            - GET_SUBS
            - SUBS

        The appropriete method on listenerObject will be called by the
        OverlayThread upon reception of a message

        @param listenerObject: an object having two methods with the following
            signature:
                1. receivedSubsRequest(permid, decoded, selversion)
                2. receivedSubsResponse(permid, decoded, callbacks, selversion)
            Following is the explanation of the paramets:
                - permid: is the PermId of the peer of send the request
                  (response)
                - decoded is a tuple containing the decoded attributes of the
                  GET_SUBS message
                - selversion is the protocol version of the peer who sent the
                  request (response)
                - callbacks is a list of pairs. Each pair is like::
                    (mask, function)
                  mask is a bitmask, and function is the function that should
                  be called upon receival of subtitles for that mask.

        '''
        #Only called by OLThread
        self._listenersList.append(listenerObject)
        

    
    
    def _get_subs_connect_callback(self, exception, dns, permid, selversion,
                              channel_id, infohash, bitmask, msgSentCallback, usrCallback):
        """
        Called by the Overlay Thread when a connection with permid is established.
        
        Performs the actual action of sending a GET_SUBS request to the peer
        identified by permid. It is called by the OLThread when a connection
        with that peer is established.
    
        """
        
        if exception is not None:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + \
                      "GET_SUBS not sent. Unable to connect to " + \
                      utilities.show_permid_short(permid)
        else:
            
                    
            if (selversion > 0 and selversion < OLPROTO_VER_FOURTEENTH):
                msg = "GET_SUBS not send, the other peers had an old protocol version: %d" %\
                    selversion
                if DEBUG:
                    print >> sys.stderr, msg
                raise SubtitleMsgHandlerException(msg)
            
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "sending GET_SUBS to " + \
                      utilities.show_permid_short(permid)
            try :
                message = self._createGETSUBSMessage(channel_id, infohash,
                                                    bitmask)
                
                
                if DEBUG:
                    # Format:
                    # SS|SG, destination, channel, infohash, bitmask, size
                    print >> sys.stderr, "%s, %s, %s, %s, %d, %d" % ("SG",show_permid_short(permid), 
                                                             show_permid_short(channel_id),
                                                             bin2str(infohash),bitmask,len(message))
                
                self._overlay_bridge.send(permid, message,
                                          lambda exc, permid: \
                                            self._sent_callback(exc,permid,
                                                            channel_id,
                                                            infohash,
                                                            bitmask,
                                                            msgSentCallback,
                                                            usrCallback))
        
            except Exception,e:
                print_exc()
                msg = "GET_SUBS not sent: %s" % str(e)
                raise SubtitleMsgHandlerException(e)
            
    def _sent_callback(self,exc,permid,channel_id,infohash,bitmask, msgSentCallback, usrCallback):
        """
        Called by the OverlayThread after a GET_SUBS request has been sent.
        """
        if exc is not None:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Unable to send GET_SUBS to: " + \
                      utilities.show_permid_short(permid) + ": " + exc
        else:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "GET_SUBS sent to %s" % \
                       (utilities.show_permid_short(permid))
            self._addToRequestedSubtitles(channel_id, infohash, bitmask, usrCallback)
            if msgSentCallback is not None:
                msgSentCallback(exc,permid,channel_id,infohash,bitmask)
        
                
    def _createGETSUBSMessage(self, channel_id, infohash, bitmask):
        """
        Bencodes a GET_SUBS message and adds the appropriate header.
        """
        
        binaryBitmask = uintToBinaryString(bitmask)
        body = bencode((channel_id, infohash, binaryBitmask))
        head = GET_SUBS
        return head + body
    
    
            
    def _decodeGETSUBSMessage(self, message):
        """
        From a bencoded GET_SUBS messages, returns its decoded contents.
        
        Decodes and checks for validity a bencoded GET_SUBS messages.
        If the message is succesfully decoded returns the tuple
        (channel_id,infohash,languages).
        
        channel_id is the binary identifier of the chanel that published
        the requested subtitles.
        infohash is the binary identifier of the torrent wich the subtitle
        refers to
        languages is a list of 3 characters language codes, for the languages
        of the requested subtitles
        
        @return: (channel_id,infohash,languages) or None if something is wrong
        """
        assert message[0] == GET_SUBS, SUBS_LOG_PREFIX + \
            "Invalid GET_SUBS Message header: %s" % message[0]
        
        try:
            values = bdecode(message[1:])
        except:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Error bdecoding message"
            return None
        
        if len(values) != 3:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid number of fields in GET_SUBS"
            return None
        channel_id, infohash, bitmask = values[0], values[1], values[2]
        if not validPermid(channel_id):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid channel_id in GET_SUBS"
            return None
        elif not validInfohash(infohash):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid infohash in GET_SUBS"
            return None
        elif not isinstance(bitmask, str) or not len(bitmask)==4:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid bitmask in GET_SUBS"
            return None
        
        try:
            bitmask = binaryStringToUint(bitmask)
            languages = self._languagesUtility.maskToLangCodes(bitmask)
        except:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid bitmask in GET_SUBS"
            return None
        
        return channel_id, infohash, languages
    
    
    def _decodeSUBSMessage(self, message):
        """
        From a bencoded SUBS message, returns its decoded contents.
        
        Decodes and checks for validity a bencoded SUBS message.
        If the message is succesfully decoded returns the tuple
        (channel_id, infohash, bitmask, contentsDictionary )
        
        channel_id is the binary identifier of the chanel that published
        the requested subtitles.
        infohash is the binary identifier of the torrent wich the subtitle
        refers to
        contentsDictionary is a dictionary having each entry like 
        {langCode : subtitleContents}.
        
        @return: the above described tuple, or None if something is wrong
        """
        assert message[0] == SUBS, SUBS_LOG_PREFIX + \
            "Invalid SUBS Message header: %s" % message[0]
            
        try:
            values = bdecode(message[1:])
        except:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Error bdecoding SUBS message"
            return None
        
        if len(values) != 4:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid number of fields in SUBS"
            return None
        channel_id, infohash, bitmask, contents = values[0], values[1], \
            values[2], values[3]
        
        if not validPermid(channel_id):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid channel_id in SUBS"
            return None
        elif not validInfohash(infohash):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid infohash in SUBS"
            return None
        elif not isinstance(bitmask, str) or not len(bitmask) == 4:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid bitmask in SUBS"
            return None
        
        try:
            bitmask = binaryStringToUint(bitmask)
            languages = self._languagesUtility.maskToLangCodes(bitmask)
        except:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid bitmask in SUBS"
            return None
        
        if not isinstance(contents, list):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Invalid contents in SUBS"
            return None
        if len(languages) != len(contents):
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Bitmask and contents do not match in"\
                      " SUBS"
            return None
        
        numOfContents = len(languages)
        if numOfContents == 0:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Empty message. Discarding."
            return None
        
        
        contentsDictionary = dict()
        for i in range(numOfContents):
            lang = languages[i]
            subtitle = contents[i]
            if len(subtitle) <= self._maxSubSize:
                contentsDictionary[lang] = subtitle
            else:
                #drop that subtitle
                if DEBUG:
                    print >> sys.stderr, SUBS_LOG_PREFIX + "Dropping subtitle, too large", len(subtitle), self._maxSubSize
                continue
            
        bitmask = self._languagesUtility.langCodesToMask(contentsDictionary.keys())
        return channel_id, infohash, bitmask, contentsDictionary
    

    def _checkingUploadQueue(self):
        """
        Uses a token bucket to control the subtitles upload rate.
        
        Every time this method is called, it will check if there are enough
        tokens in the bucket to send out a SUBS message.
        Currently fragmentation is not implemented: all the reuquested subtitles
        are sent in a single SUBS messages if there are enough tokens:
        too big responses are simply discarded.
        
        The method tries to consume all the available tokens of the token
        bucket until there are no more messages to send. If there are no
        sufficiente tokens to send a message, another call to this method
        is scheduled in a point in time sufficiently distant.
        """
        
        if DEBUG:
            print >> sys.stderr, SUBS_LOG_PREFIX + "Checking the upload queue..."
        
        if not self._tokenBucket.upload_rate > 0:
            return 
        
        if not len(self._uploadQueue) > 0:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "Upload queue is empty."
            
        while len(self._uploadQueue) > 0 :
            responseData = self._uploadQueue[0]
            encodedMsg = self._createSingleResponseMessage(responseData)
            
            if encodedMsg is None:
                if DEBUG:
                    print >> sys.stderr, SUBS_LOG_PREFIX + "Nothing to send"
                del self._uploadQueue[0]
                continue #check other messages in the queue
            
            msgSize = len(encodedMsg) / 1024.0 #in kilobytes
            
            if msgSize > self._tokenBucket.capacity: 
                #message is too big, discarding
                print >> sys.stderr, "Warning:" + SUBS_LOG_PREFIX + "SUBS message too big. Discarded!"
                del self._uploadQueue[0]
                continue #check other messages in the queue
            
            #check if there are sufficiente tokens
            if self._tokenBucket.consume(msgSize):
                
                if DEBUG:
                    # Format:
                    # S|G, destination, channel, infohash, bitmask, size
                    keys = responseData['subtitles'].keys()
                    bitmask = self._languagesUtility.langCodesToMask(keys)
                    print >> sys.stderr, "%s, %s, %s, %s, %d, %d" % ("SS",show_permid_short(responseData['permid']),
                                                             show_permid_short(responseData['channel_id']),
                                                             bin2str(responseData['infohash']),bitmask,int(msgSize*1024))
                    
                self._doSendSubtitles(responseData['permid'], encodedMsg, responseData['selversion'])
                del self._uploadQueue[0]
            else: 
                #tokens are insufficient wait the necessary time and check again
                neededCapacity = max(0, msgSize - self._tokenBucket.tokens)
                delay = (neededCapacity / self._tokenBucket.upload_rate)
                self._nextUploadTime = time() + delay
                self.overlay_bridge.add_task(self._checkingUploadQueue, delay)
                return
        
        #The cycle breaks only if the queue is empty
    
    
    def _createSingleResponseMessage(self, responseData):
        """
        Create a bencoded SUBS message to send in response to a GET_SUBS
        
        The format of the sent message is a not encoded SUBS character and then
        the bencoded form of
        (channel_id,infohash,bitmask,[listOfSubtitleContents])
        the list of subtitle contents is ordered as the bitmask
        
        """
        
        orderedKeys = sorted(responseData['subtitles'].keys())

        payload = list()
        #read subtitle contents
        for lang in orderedKeys:
            
            fileContent = responseData['subtitles'][lang]
                
            if fileContent is not None and len(fileContent) <= self._maxSubSize:
                payload.append(fileContent)
            else:
                print >> sys.stderr, "Warning: Subtitle in % for ch: %s, infohash:%s dropped. Bigger then %d" % \
                            (lang, responseData['channel_id'], responseData['infohash'], 
                             self._maxSubSize)

                
        
        if not len(payload) > 0:
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "No payload to send in SUBS"
            return None
        
        bitmask = \
            self._languagesUtility.langCodesToMask(orderedKeys)
        
        binaryBitmask = uintToBinaryString(bitmask, length=4)
        header = (responseData['channel_id'], responseData['infohash'], binaryBitmask)
        
        message = bencode((
                           header[0],
                           header[1],
                           header[2],
                           payload
                           ))
        
        return SUBS + message
    
    
    def _doSendSubtitles(self, permid, msg, selversion):
        """
        Do sends the SUBS message through the overlay bridge.
        """
        if DEBUG:
            print >> sys.stderr, SUBS_LOG_PREFIX + "Sending SUBS message to %s..." % \
                  show_permid_short(permid)
    
        # Optimization: we know we're currently connected
        #DOUBLE CHECK THIS. I just assuemed it was true 
        # since it is true for MetadataHandler
        self._overlay_bridge.send(permid, msg, self._subs_send_callback)
    
    def _subs_send_callback(self, exc, permid):
        '''
        Called by the OLThread when a SUBS message is succesfully sent
        '''
        if exc is not None:
            print >> sys.stderr, "Warning: Sending of SUBS message to %s failed: %s" % \
                (show_permid_short(permid), str(exc))
        else:
            if DEBUG:
                print >> sys.stderr, "SUBS message succesfully sent to %s" % show_permid_short(permid)
        
        
    def _addToRequestedSubtitles(self, channel_id, infohash, bitmask, callback=None):
        """
        Add (channel_id, infohash, bitmask) to the history of requested subs.
        
        Call this method after a request for subtitles for a torrent
        identified by infohash in channel channel_id, has been sent for the 
        languages identified by the bitmask.
        """
        
        assert 0 <= bitmask < 2**32, "bitmask must be a 32  bit integer"

        if(int(time()) >= self._nextCleanUpTime):
            self._cleanUpRequestedSubtitles() #cleanup old unanswered requests
        
        key = self._getRequestedSubtitlesKey(channel_id, infohash)
        if key in self.requestedSubtitles.keys():
            rsEntry = self.requestedSubtitles[key]
            rsEntry.newRequest(bitmask)
        else :
            rsEntry = _RequestedSubtitlesEntry()
            rsEntry.newRequest(bitmask, callback)
            self.requestedSubtitles[key] = rsEntry


    
    def _cleanUpRequestedSubtitles(self):
        """
        Cleans up unanswered requests.
        
        A request is considered unanswered when it was last updated more then
        REQUESTE_VALIDITY_TIME seconds ago.
        If a response arrives after a request gets deleted, it will be dropped.
        """
 
        keys = self.requestedSubtitles.keys()
        now = int(time())
        for key in keys:
            rsEntry = self.requestedSubtitles[key]
            somethingDeleted = rsEntry.cleanUpRequests(self._requestValidityTime)
            if somethingDeleted:
                if DEBUG:
                    print >> sys.stderr, "Deleting subtitle request for key %s: expired.", key
            
            #no more requests for the (channel,infohash, pair)
            if rsEntry.cumulativeBitmask == 0:
                del self.requestedSubtitles[key]
                
        self._nextCleanUpTime = now + CLEANUP_PERIOD

        
        
    
    
    def _removeFromRequestedSubtitles(self, channel_id, infohash, bitmask):
        """
        Remove (channel_id,infohash,bitmask) from the history of requested subs.
        
        Call this method after a request for subtitles for a torrent
        identified by infohash in channel channel_id, has been recevied for the 
        languages identified by the bitmask.
        """

        key = self._getRequestedSubtitlesKey(channel_id, infohash)
        if key not in self.requestedSubtitles.keys():
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "asked to remove a subtitle that" + \
                        "was never requested from the requestedList"
            return None
        else:
            rsEntry = self.requestedSubtitles[key]
            callbacks = rsEntry.removeFromRequested(bitmask)
            
            if rsEntry.cumulativeBitmask == 0:
                del self.requestedSubtitles[key]
            return callbacks
            
    def _checkRequestedSubtitles(self, channel_id, infohash, bitmask):
        """
        Given a bitmask returns a list of language from the ones in the bitmask
        that have been actually requested
        """

        key = self._getRequestedSubtitlesKey(channel_id, infohash)
        if key not in self.requestedSubtitles.keys():
            if DEBUG:
                print >> sys.stderr, SUBS_LOG_PREFIX + "asked to remove a subtitle that" + \
                        "was never requested from the requested List"
            return 0
        else:
            rsEntry = self.requestedSubtitles[key]
            reqBitmask = rsEntry.cumulativeBitmask & bitmask
            return reqBitmask

            
            
class _RequestedSubtitlesEntry():
    '''
    Convenience class to represent entries in the requestedSubtitles map
    from the SubtitleHandler.
    For each (channel, infohash tuple it keeps a cumulative bitmask
    of all the requested subtitles, and a list of the single different
    requests. Each single request bears a timestamp that is used
    to cleanup outdated requests
    '''
    
    def __init__(self):
        self.requestsList = list()
        self.cumulativeBitmask = 0
        
    def newRequest(self, req_bitmask, callback = None):
        assert 0 <= req_bitmask < 2**32
        
        self.requestsList.append([req_bitmask,callback,int(time())])
        self.cumulativeBitmask = int(self.cumulativeBitmask | req_bitmask)

            
    
    def removeFromRequested(self, rem_bitmask):

        callbacks = list()
        self.cumulativeBitmask = self.cumulativeBitmask & (~rem_bitmask)
        
        length = len(self.requestsList)
        i=0
        while i < length:
            entry = self.requestsList[i]
            receivedLangs = entry[0] & rem_bitmask
            #if something was received for the request
            if receivedLangs != 0:
                callbacks.append((entry[1],receivedLangs))
                updatedBitmask = entry[0] & (~receivedLangs)
                # no more subtitles to receive for 
                # thath request
                if updatedBitmask == 0:
                    del self.requestsList[i]
                    i -=1
                    length -=1
                else:
                    entry[0] = updatedBitmask
            i += 1
             
        return callbacks
    

    
    
    
    def cleanUpRequests(self, validityDelta):

        somethingDeleted = False
        now = int(time())
        
        length = len(self.requestsList)
        i=0
        while i < length:
            entry = self.requestsList[i]
            requestTime = entry[2]
            #if the request is outdated
            if requestTime + validityDelta < now :
                #remove the entry
                self.cumulativeBitmask = self.cumulativeBitmask & \
                    (~entry[0])
                del self.requestsList[i]
                i -= 1
                length -= 1
                somethingDeleted = True
            
            i += 1
        
        return somethingDeleted
    

