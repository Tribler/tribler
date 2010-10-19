# Written by Andrea Reale
# see LICENSE.txt for license information


from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import \
    LanguagesProvider
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import \
    RichMetadataException
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.Utilities import utilities
from Tribler.Core.Utilities.utilities import isValidPermid, bin2str
import sys
import threading

DEBUG = True


class SubtitlesSupport(object):
    '''
    Subtitle dissemination system facade.
    
    Acts as the only faced between the subtitle dissemination system and 
    the GUI (or whoever needs to subtitles).
    
    Provides methods to query the subtitles database. Allows publishers to
    add their own subtitles, and if necessary permits to retrieve the subtitle
    remotely if not available.
    '''

    __single = None
    _singletonLock = threading.RLock()
    
    def __init__(self):
        
        #singleton pattern not really enforced if someone just calls 
        # the normal constructor. But this way I can test the instance easier
        try:
            SubtitlesSupport._singletonLock.acquire()
            SubtitlesSupport.__single = self
        finally:
            SubtitlesSupport._singletonLock.release()
            
        self.richMetadata_db = None
        self.subtitlesHandler = None
        self.channelcast_db = None
        self.langUtility = LanguagesProvider.getLanguagesInstance()
        self._registered = False
    
    @staticmethod
    def getInstance(*args, **kw):
        try:
            SubtitlesSupport._singletonLock.acquire()
            if SubtitlesSupport.__single == None:
                SubtitlesSupport(*args, **kw)
        finally:
            SubtitlesSupport._singletonLock.release()
        
        return SubtitlesSupport.__single
        
    def _register(self, richMetadataDBHandler, subtitlesHandler,
                 channelcast_db, my_permid, my_keypair, peersHaveManger,
                 ol_bridge):
        assert richMetadataDBHandler is not None
        assert subtitlesHandler is not None
        assert channelcast_db is not None
        assert peersHaveManger is not None
        assert ol_bridge is not None
        assert isValidPermid(my_permid)
        
        self.richMetadata_db = richMetadataDBHandler
        self.subtitlesHandler = subtitlesHandler
        self.channelcast_db = channelcast_db
        self.my_permid = my_permid
        self.my_keypair = my_keypair
        self._peersHaveManager = peersHaveManger
        #used to decouple calls to SubtitleHandler
        self._ol_bridge = ol_bridge
        self._registered = True
        
    
    def getSubtileInfosForInfohash(self, infohash):
        '''
        Retrieve available information about subtitles for the given infohash.
        
        Given the infohash of a .torrent, retrieves every
        information about subtitles published for that .torrent that is
        currently available in the DB. 
        
        @param infohash: a .torrent infohash (binary)
        @return: a dictionary. The dictionary looks like this::
                { 
                  channel_id1 : {langCode : L{SubtitleInfo}, ...} ,
                  channel_id2 : {langCode : L{SubtitleInfo}, ... },
                  ...
                } 
            Each entry in the dictionary has the following semantics:
                - channel_id is the permid identifiying the channel (binary).
                - langCode is an ISO 693-2 three characters language code
        '''
        assert utilities.isValidInfohash(infohash)
        assert self._registered, "Instance is not registered"
        
        returnDictionary = dict()
        
        #a metadataDTO corrisponds to all metadata for a pair channel, infohash
        metadataDTOs = self.richMetadata_db.getAllMetadataForInfohash(infohash)
        
        for metadataDTO in metadataDTOs:
            channel = metadataDTO.channel
            subtitles = metadataDTO.getAllSubtitles()
            if len(subtitles) > 0 :
                returnDictionary[channel] = subtitles
        
        return returnDictionary
        
    
    
    def getSubtitleInfos(self, channel, infohash):
        '''
        Retrieve subtitles information for the given channel-infohash pair.
        
        Searches in the local database for information about subtitles that
        are currently availabe.
        
        @param channel: the channel_id (perm_id) of a channel (binary)
        @param infohash: a .torrent infohash (binary)
        @return: a dictionary of SubtitleInfo instances. The keys are the 
                language codes of the subtitles
        '''
        assert self._registered, "Instance is not registered"
        metadataDTO = self.richMetadata_db.getMetadata(channel,infohash)
        if metadataDTO is None:
            #no results
            return {}
        else:
            return metadataDTO.getAllSubtitles()
        
    
    def publishSubtitle(self, infohash, lang, pathToSrtSubtitle):
        '''
        Allows an user to publish an srt subtitle file in his channel.
        
        Called by a channel owner this method inserts a new subtitle for
        a torrent published in his channel. 
        The method assumes that the torrent identified by the infohash
        parameter is already in the channel, and that the parameter 
        pathToSrtSubtitle points to an existing srt file on the local
        filesystem.
        If a subtitle for the same language was already associated to the 
        specified infohash and channel, it will be overwritten.
        After calling this method the newly inserted subtitle will be 
        disseminated via Channelcast.
        
        @param infohash: the infohash of the torrent to associate the subtitle
                         with, binary
        @param lang: a 3 characters code for the language of the subtitle as
                     specified in ISO 639-2. Currently just 32 language codes
                     will be supported.
        @param pathToSrtSubtitle: a path in the local filesystem to a subtitle
                                  in srt format.
        
        @raise RichMetadataException: if something "general" goes wrong while
                                      adding new metadata
        @raise IOError: if disk related problems occur
        '''
        assert utilities.isValidInfohash(infohash), "Invalid Infohash"
        assert lang is not None and self.langUtility.isLangCodeSupported(lang)
        assert self._registered, "Instance is not registered"
  
        channelid = bin2str(self.my_permid)
        base64infohash = bin2str(infohash)
        # consisnstency check: I want to assure that this method is called
        # for an item that is actually in my channel
        consinstent = self.channelcast_db.isItemInChannel(channelid,base64infohash)
        
        if not consinstent:
            msg = "Infohash %s not found in my channel. Rejecting subtitle" \
                    % base64infohash
            if DEBUG:
                print >> sys.stderr, msg
            raise RichMetadataException(msg)
        
        try:
        
            filepath = \
                self.subtitlesHandler.copyToSubtitlesFolder(pathToSrtSubtitle,
                                                            self.my_permid,infohash,
                                                            lang)   
        except Exception,e:
            if DEBUG:
                print >> sys.stderr, "Failed to read and copy subtitle to appropriate folder: %s" % str(e)


        
        # retrieve existing metadata from my channel, infoahash
        metadataDTO = self.richMetadata_db.getMetadata(self.my_permid, infohash)
        # can be none if no metadata was available
        if metadataDTO is None:
            metadataDTO = MetadataDTO(self.my_permid, infohash)
        else:
            #update the timestamp
            metadataDTO.resetTimestamp()
        
        newSubtitle = SubtitleInfo(lang, filepath)
        
        # this check should be redundant, since i should be sure that subtitle
        # exists at this point
        if newSubtitle.subtitleExists():
            newSubtitle.computeChecksum()
        else:
            msg = "Inconsistency found. The subtitle was"\
                                        "not published"
            if DEBUG:
                print >> sys.stderr, msg
            raise RichMetadataException(msg)
        
        metadataDTO.addSubtitle(newSubtitle)
        metadataDTO.sign(self.my_keypair)
        
        #channelid is my permid. I received the metadata from myself
        self.richMetadata_db.insertMetadata(metadataDTO)
        


    def retrieveSubtitleContent(self, channel, infohash, subtitleInfo, callback = None):
        '''
        Retrieves the actual subtitle file from a remote peer.
        
        If not already locally available this function tries to retrieve the
        actual subtitle content from remote peers. The parameter subtitleInfo
        describes the subtitle to retrieve the content for.
        
        A callback can be provided. It will be called by the
        OLThread once the actual subtitle is available, or never
        in case of failure. 
        The callback function should have exactly one parameter that will
        be bound to a new SubtitleInfo instance, with the path field updated
        to the path where the downloaded subtitle resides.
        
        Usually this method should be called when the value of 
        subtitleInfo.path is None, meaning that the subtitle of the content
        is not available locally. If subtitleInfo.path is not None, tha path
        will be checked for validity and in case it is not valid the method
        will try to fetch a new subtitle. If it points to a valid subtitle
        with the correct checksum, nothing will be done and the user callback
        will be immediately scheduled.
        
        The current implementation queries for subtitle up to 5 peers
        ithat manifested the availability for that subtitle through channelcast.
        The requests are sent in parallel but only the first response is 
        considered.
        
        @param channel: the channel where the subtitle was published. (binary channel_id)
        
        @param infohash: the infohash of the item we want to retrieve the
                         subtitle for. (binary)
        
        @param subtitleInfo: an intance of SubtitleInfo describing the
                             subtitle to be downloaded
                             
        @param callback: a function that will be called when the subtitle is 
                         succesfully retrieved. See the description for
                         further details. If None nothing will be called.
        '''
        assert self._registered, "Instance is not registered"
        assert subtitleInfo.checksum is not None , "Cannot retrieve a subtitle"\
            "whose checksum is not known"
        
        if subtitleInfo.subtitleExists():
            if subtitleInfo.verifyChecksum():
                #subtitle is available call the callback
                callback(subtitleInfo)
                return
            else:
                #delete the existing subtitle and ask for a new
                #one
                if DEBUG:
                    print >> sys.stderr, "Subtitle is locally available but has invalid" \
                          "checksum. Issuing another download"
                subtitleInfo.path = None
        

        languages = [subtitleInfo.lang]
        
        def call_me_when_subtitle_arrives(listOfLanguages):
            if callback is not None:
                #since this was a request for a single subtitle
                assert len(listOfLanguages) == 1
                
                #retrieve the updated info from the db
                sub = self.richMetadata_db.getSubtitle(channel,infohash,
                                                       listOfLanguages[0])
                
                #call the user callback
                
                callback(sub)
            
            
        self._queryPeersForSubtitles(channel, infohash, languages,
                                             call_me_when_subtitle_arrives)

        
    
    def retrieveMultipleSubtitleContents(self, channel, infohash, listOfSubInfos, callback=None):
        '''
        Query remote peers of severela subtitles given the infohash
        of the torrent they refer to, and the channel_id of the channel
        they where published in.
        
        @param channel: channel_id (permid) of the channel where the subtitles where published
                        (binary)
        @param infohash: infohash of the torrent the subtitles are associated to (binary)
        @param listOfSubInfos: a list of SubtitleInfo instances, specifing the subtitles to
                               retrieve
                               
        @param callback: a callback function that will be called whenever any of the requested
                        subtitles are retrieved. The function may be called multiple times
                        if different requested subtitles arrive at different times, but it is
                        guaranteed that it will be called at most once for each different
                        subtitle arrived.
                        The function MUST have one parameter, that will be bound to a list
                        of updated SubtitleInfo s, reflecting the subtitles that have been
                        received
        
        @rtype: None
        @return:  always None
        '''
        assert self._registered, "Instance is not registered"
        
        languages = []
        locallyAvailableSubs = []
        for subtitleInfo in listOfSubInfos:
            if subtitleInfo.checksum is None:
                if DEBUG:
                    print >> sys.stderr, "No checksum for subtitle %s. Skipping it in the request"\
                        % subtitleInfo
                continue
            
            if subtitleInfo.subtitleExists():
                if subtitleInfo.verifyChecksum():
                    #subtitle is available call the callback
                    locallyAvailableSubs.append(subtitleInfo)
                    continue
                else:
                    #delete the existing subtitle and ask for a new
                    #one
                    if DEBUG:
                        print >> sys.stderr, "Subtitle is locally available but has invalid" \
                              "checksum. Issuing another download"
                    subtitleInfo.path = None
                    
            languages.append(subtitleInfo.lang)
        
            
        if len(locallyAvailableSubs) > 0 and callback is not None:
            callback(locallyAvailableSubs)
        
        def call_me_when_subtitles_arrive(listOfLanguages):
            if callback is not None:
                assert len(listOfLanguages) > 0 
                
                subInfos = list()
                
                #better to perform a single read from the db
                allSubtitles = self.richMetadata_db.getAllSubtitles(channel,infohash)
                for lang in listOfLanguages:
                    subInfos.append(allSubtitles[lang])
    
                callback(subInfos)
        
        if len(languages) > 0:
            self._queryPeersForSubtitles(channel, infohash, languages,
                                                  call_me_when_subtitles_arrive)
            
        
       
    def _queryPeersForSubtitles(self, channel, infohash, languages, callback):
        '''
        Queries remote peers for subtitle contents  specified by 'infohash' 
        published in a channel identified by 'channel' in the languages specified
        by the languages list. 
        Once any of theses subtitles arrive callback is called.
        NOTE: calls send() on the OverlayThreadingBridge 
        
        @param channel: the channel_id of the channel were the subtitles to retrieve
                        were published (binary string)
        @param infohash: the infohash of a torrent to whom the subtitles to retrieve
                        refer (binary string)
        @param languages: a list of language codes (see Languages.py) for the subtitles
                          contents to retrieve
        @param callback: a callback function that will be called when some (or all) of the
                         requested subtitles are received. The provided function must
                         accept one parameter, that will be bound to a list of language codes
                         corresponding to the languages of the subtitles that were received.
                         Notice that if subtitles for different languages are received at multiple
                         times, the callback my be called multiple times. Notice also
                         that the callback will be called at most once for each of the requested
                         languages.
        '''
        
        def task():
            bitmask  = self.langUtility.langCodesToMask(languages)
            
            if not bitmask > 0:
                if DEBUG:
                    print >> sys.stderr, "Will not send a request for 0 subtitles"
                return
                
            peers_to_query = self._peersHaveManager.getPeersHaving(channel, infohash, bitmask)
            
            assert len(peers_to_query) > 0, "Consistency error: there should always be some result"
        
            
            #ask up to 5 peers for the same subtitle. The callback will be called only at the
            # first received response (the others should be dropped)
            for peer in peers_to_query:
                self.subtitlesHandler.sendSubtitleRequest(peer, channel, infohash,
                                                                   languages, callback)
        
        self._ol_bridge.add_task(task)
        
            
            
    
        
        
        
            
    def runDBConsinstencyRoutine(self):
        '''
        Clean the database from incorrect data.
        
        Checks the databases for the paths of subtitles presumably locally available.
        If those subtitles are not really available at the given path, updates
        the database in a consistent way.
        '''
        result = self.richMetadata_db.getAllLocalSubtitles()
        
        for channel in result:
            for infohash in result[channel]:
                for subInfo in result[channel][infohash]:
                    if not subInfo.subtitleExists():
                        #If a subtitle published by me was removed delete the whole entry
                        if channel == self.my_permid:
                            metadataDTO = self.richMetadata_db.getMetadata(channel,infohash)
                            metadataDTO.removeSubtitle(subInfo.lang)
                            metadataDTO.sign(self.my_keypair)
                            self.richMetadata_db.insertMetadata(metadataDTO)
                        #otherwise just set the path to none
                        else:
                            self.richMetadata_db.updateSubtitlePath(channel, infohash, subInfo.lang,None)
            
        
        
                
        
        
