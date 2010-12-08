# Written by Andrea Reale
# see LICENSE.txt for license information

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import LanguagesProvider
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import SerializationException
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.Overlay.permid import sign_data, verify_data
from Tribler.Core.Utilities.utilities import isValidInfohash, isValidPermid
from math import floor
from struct import pack, unpack
import sys
import time

DEBUG = False

_languagesUtil = LanguagesProvider.getLanguagesInstance()

class MetadataDTO(object):
    '''
    Metdata DataTransferObject
    '''


    def __init__(self, publisher,infohash,timestamp = None,
                 description=u"", subtitles=None,signature=None):
        """
        Create a MetataDTO instance.
        
        publisher and infohash are mandatory to be not null
        @param publisher: the permid  of the owner of the 
                          channel this instance refers to
        @param infohash: the infohash of the item in the channel this instance
                         refers to 
        @param timestamp: the timestamp of the creation of this metadata
                          instance. This can be later reset with 
                          resetTimestamp()
        @param description: an optional utf-8 string description for the item. 
                            Defaults to an empty string
        @param subtitles: a dictionary of type {langCode : SubtitleInfo}
        @param signature: signature of the packed version of this metadataDTO.
                          Defaults to None. It can be later signed with sign()
        """
        
        assert publisher is not None
        assert infohash is not None
        assert isValidPermid(publisher)
        assert isValidInfohash(infohash)
        
        #stringified permid of the owner of the channel
        self.channel = publisher
        
        #stringified infohash (bin2str) of the torrent
        self.infohash = infohash
        if timestamp is not None:
            timestring = int(floor(timestamp))
        else:
            timestring = int(floor(time.time()))
        
        #integer timestamp of the creation of this content
        #(the content, not the MetadataDTO instance)
        self.timestamp = timestring
        
        #utf-8 string description
        if isinstance(description, str):
            description = unicode(description, "utf-8")
            
        self.description = description
        
        if subtitles is None:
            subtitles = {}
        self._subtitles = subtitles
        self.signature = signature
        
        
    def resetTimestamp(self):
        """
        Sets the timestamp to the current time.
        """
        self.timestamp = int(floor(time.time()))
    
    def addSubtitle(self, subtitle):
        '''
        Adds a subtitle instance to the metadata dto.
        
        subtitle must be an instance of SubtitleInfo, and its language
        field must be correctly set to an ISO-639-2 language code
        (see Languages).
        
        @param subtitle: a SubtitleInfo instance
        @precondition: subtitle.lang is not None
        '''
        assert isinstance(subtitle, SubtitleInfo)
        assert subtitle.lang is not None
        
        self._subtitles[subtitle.lang] = subtitle
    
    def removeSubtitle(self, lang):
        '''
        Remove a subtitle instance from the dto.
        
        If the subtitles with the given language does not exist, it
        does nothing.
        
        @param lang: a language code for the subtitle to be removed
        '''
        if lang in self._subtitles.keys():
            del self._subtitles[lang]
        
    def getSubtitle(self,lang):
        '''
        Returns a SubtitleInfo instance for the given language if it exists.
        
        @param lang: an ISO-639-2 3 characters language code
        
        @rtype: SubtitleInfo.SubtitleInfo
        @return: a SubtitleInfo instance, or None
        '''
        if lang not in self._subtitles.keys():
            return None
        else:
            return self._subtitles[lang]
    
    def getAllSubtitles(self):
        '''
        Returns a copy of the subtitles for this dto.
        
        Notice that modifying this copy does not affect the languages in the
        metadata dto
        '''
        return self._subtitles.copy()
        
        
        
    def sign(self,keypair):
        """
        Signs the packed version of this instance.
        
        See _packData to see what packed version means.
        
        @param keypair: an ec keypair that will be used to create
                        the signature
        """ 
        bencoding = self._packData()
        signature = sign_data(bencoding, keypair)
        self.signature = signature
    
    def verifySignature(self):
        """
        Verifies the signature field of this instance.
        
        The signature is verified agains the packed version of this
        instance. See _packData
        
        """
        assert self.signature is not None
        toVerify = self._packData()
        binaryPermId = self.channel
        return verify_data(toVerify, binaryPermId, self.signature)
        
      
        
    def _packData(self):
        """
        Creates a bencode binary representation of this metadata instance.
        
        This representation is the one that is sent with ChannelCast messages.
        """
        if self.description is not None:
            assert isinstance(self.description, unicode)      
        if self.description is None:
            self.description = u""
        
        
        
        bitmask, checksums = self._getSubtitlesMaskAndChecksums()
        
        # The signature is taken over the bencoding of
        # binary representations of (channel,infohash,description,timestamp,bitmask)
        # that is the same message that is sent with channelcast
        tosign = (self.channel, 
                  self.infohash, 
                  self.description.encode("utf-8"),
                  self.timestamp,
                  pack("!L", bitmask),
                  checksums )
    
        bencoding = bencode(tosign)
        return bencoding
    
    def serialize(self):
        if self.signature is None:
            raise SerializationException("The content must be signed")
        pack = bdecode(self._packData())
        pack.append(self.signature)
        
        return pack
    

        
        
        
    
    
    def _getSubtitlesMaskAndChecksums(self):
        '''
        computes bitmask and checksums for subtitles.
        
        Computes the bitmask for available subtitles and produces also a tuple
        containing the checksums for the subtitles that are in the bitmask.
        The checksums are in the same order as the bits in the bitmask.
        '''
        
        languagesList = []
        checksumsList = []
        
        #cycling by sorted keys
        sortedKeys = sorted(self._subtitles.keys())
        
        for key in sortedKeys:
            sub = self._subtitles[key]
            assert sub.lang is not None
            assert sub.lang == key
            
            if sub.checksum is None:
                if sub.subtitleExists():
                    sub.computueCheksum()
                else :
                    if DEBUG:
                        print >> sys.stderr, "Warning: Cannot get checksum for " + sub.lang \
                                +" subtitle. Skipping it."
                    continue
            languagesList.append(sub.lang)
            checksumsList.append(sub.checksum)
            
            
        bitmask = _languagesUtil.langCodesToMask(languagesList)
        checksums = tuple(checksumsList)
        
        return bitmask, checksums
    
    def __eq__(self, other):
        if self is other:
            return True
        return self.channel == other.channel and \
               self.infohash == other.infohash and \
               self.description == other.description and \
               self.timestamp == other.timestamp and \
               self.getAllSubtitles() == other.getAllSubtitles()
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    
#-- Outside the class

def deserialize(packed):
    assert packed is not None
        
    message = packed
    if(len(message) != 7):
        raise SerializationException("Wrong number of fields in metadata")
        
    channel = message[0]
    infohash = message[1]
    description = message[2].decode("utf-8")
    timestamp = message[3]
    binarybitmask = message[4]
    bitmask, = unpack("!L", binarybitmask)
    listOfChecksums = message[5]
    signature = message[6]
    subtitles = _createSubtitlesDict(bitmask,listOfChecksums)
    
    dto = MetadataDTO(channel, infohash, timestamp, description, subtitles, signature)
    if not dto.verifySignature():
        raise SerializationException("Invalid Signature!")
    return dto
    
                                      

def _createSubtitlesDict(bitmask, listOfChecksums):
    langList = _languagesUtil.maskToLangCodes(bitmask)
    if len(langList) != len(listOfChecksums):
        raise SerializationException("Unexpected num of checksums")
     
    subtitles = {}
    for i in range(0, len(langList)):
        sub = SubtitleInfo(langList[i])
        sub.checksum = listOfChecksums[i]
        subtitles[langList[i]] = sub
    return subtitles
     
     
     
     
    
        
