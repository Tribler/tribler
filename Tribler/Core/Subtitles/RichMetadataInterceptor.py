# Written by Andrea Reale
# see LICENSE.txt for license information

import sys
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import deserialize
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import SerializationException,\
    RichMetadataException
from Tribler.Core.Utilities.utilities import isValidPermid, bin2str,\
    show_permid_short, uintToBinaryString, binaryStringToUint
from copy import copy
from Tribler.Core.simpledefs import NTFY_RICH_METADATA, NTFY_UPDATE, NTFY_INSERT


DEBUG = False


class RichMetadataInterceptor(object):
    
  
    
    def __init__(self, metadataDbHandler, voteCastDBHandler, myPermId,
                 subSupport=None, peerHaveManager = None, notifier = None):
        '''
        Builds an instance of RichMetadataInterceptor.
        
        @param metadataDbHandler: an registered instance of
            L{MetadataDBHandler}
        @param voteCastDBHandler: a registered instance of VoteCastDBHandler
        @param myPermId: the PermId of the client.
        @param subSupport: a registered instance of L{SubtitlesSupport}
        @param peerHaveManager: an instance of L{PeerHaveManager}
        @param notifier: an instance of Notifier
        '''
#        assert isinstance(metadataDbHandler, MetadataDBHandler), \
#            "Invalid RichMetadata DB Handler"
#        assert isinstance(voteCastDBHandler, VoteCastDBHandler), \
#            "Invalid Votecast DB Handler"
        #hack to make a fast test DELETE THIS CONDITION
#        if subSupp != None:
#            assert isinstance(subSupp, SubtitlesSupport)
        assert isValidPermid(myPermId),  "Invalid Permid"
            
        self.rmdDb = metadataDbHandler
        self.votecastDB = voteCastDBHandler
        self.my_permid = myPermId
        self.subSupport = subSupport
        self.peerHaveManager = peerHaveManager
        self.notifier = notifier

    
    def _splitChannelcastAndRichMetadataContents(self,enrichedChannelcastMessage):
        '''
        Takes a "enriched" channelcast message (protocol v.14 - the one with
        the 'rich_metadata' field inside), and extracts the rich metadata info
        from it
        
        @param enrichedChannelcastMessage: a channelcast message from protocol 
                                           version 14
                                           
        @return: a list tuples like (MetadataDTO, haveMask) instances extracted from the message. or
                 an empty list if nothing. Along with it there is a list
                 of the size of each entry in the message that is used to 
                 collect stats. if the announceStatsLog is disable this list
                 will always be empty
        '''
        if not isinstance(enrichedChannelcastMessage, dict):
            if DEBUG:
                print >> sys.stderr, "Invalid channelcast message received"
            return None
        
        rmdData = list()
        
        sizeList = list()
        for signature in iter(enrichedChannelcastMessage):
            msg = enrichedChannelcastMessage[signature]
            
            if 'rich_metadata' in msg.keys():
                metadataEntry = msg['rich_metadata']
                if metadataEntry is None \
                    or not validMetadataEntry(metadataEntry):
                    continue
                else:
                    channel_id = msg['publisher_id']
                    infohash = msg['infohash']

                    # rebuilding the serialized MetadataDTO structure
                    # that was broken in self.addRichMetadataContent
                    binary_havemask = metadataEntry.pop(-1)
                    havemask = binaryStringToUint(binary_havemask)
                    
                    metadataEntry.insert(0,infohash)
                    metadataEntry.insert(0,channel_id)
                    try:
                        curMetadataDTO = deserialize(metadataEntry)
                    except SerializationException,e:
                        if DEBUG:
                            print >> sys.stderr, "Invalid metadata message content: %s" % e
                        continue
                    
                    rmdData.append((curMetadataDTO,havemask))
        
        return rmdData, sizeList
    
    def handleRMetadata(self, sender_permid, channelCastMessage, fromQuery = False):
        '''
        Handles the reception of rich metadata.
        
        Called when an "erniched" channelCastMessage (v14) is received.
        @param sender_permid: the PermId of the peer who sent the message
        @param channelCastMessage: the received message
        @return: None
        '''
        metadataDTOs, sizeList = \
          self._splitChannelcastAndRichMetadataContents(channelCastMessage)
          
        if DEBUG:
            print >> sys.stderr, "Handling rich metadata from %s..." % show_permid_short(sender_permid)
        i=0
        for md_and_have in metadataDTOs:
            md = md_and_have[0]
            havemask = md_and_have[1]
            
            vote = self.votecastDB.getVote(bin2str(md.channel), 
                                       bin2str(self.my_permid))
            
            # the next if may seem useless, but since sizeList is defined only when
            # logging is enabled for debug, I get an error without this conditional statement
            # because the argument for the debug() call getsEvaluated before the logging
            # system understands that debug is disabled
            #if announceStatsLog.isEnabledFor(logging.INFO):
            if DEBUG:
                id = "RQ" if fromQuery else "R"
                print >> sys.stderr, "%c, %s, %s, %s, %d, %d" % \
                                       (id, md.channel, md.infohash, \
                                        show_permid_short(sender_permid), md.timestamp,
                                        sizeList[i])
                #format "R|S (R: received - S: sent), channel, infohash, sender|destination,metadataCreationTimestamp"
                # 30-06-2010: "RQ" as received from query
                i += 1
        
            # check if the record belongs to a channel 
            # who we have "reported spam" (negative vote)
            if  vote == -1:
                # if so, ignore the incoming record
                continue
            
            isUpdate =self.rmdDb.insertMetadata(md)
            
            self.peerHaveManager.newHaveReceived(md.channel,md.infohash,sender_permid,havemask)
            
            if isUpdate is not None:
                #retrieve the metadataDTO from the database in the case it is an update
                md = self.rmdDb.getMetadata(md.channel,md.infohash)
                self._notifyRichMetadata(md, isUpdate)
            
            # if I am a subscriber send immediately a GET_SUBS to the 
            # sender
            if vote == 2:
                if DEBUG:
                    print >> sys.stderr, "Subscribed to channel %s, trying to retrieve" \
                         "all subtitle contents" % (show_permid_short(md.channel),)
                
                self._getAllSubtitles(md)

    def _computeSize(self,msg):
        import Tribler.Core.BitTornado.bencode as bencode
        bencoded = bencode.bencode(msg)
        return len(bencoded)
    
    
    def _notifyRichMetadata(self, metadataDTO, isUpdate):
        if self.notifier is not None:
            eventType = NTFY_UPDATE if isUpdate else NTFY_INSERT
            self.notifier.notify(NTFY_RICH_METADATA, eventType, (metadataDTO.channel, metadataDTO.infohash))
            
    
    def _getAllSubtitles(self, md):
        
        subtitles = md.getAllSubtitles()
        
        try:
            self.subSupport.retrieveMultipleSubtitleContents(md.channel,md.infohash,
                                                             subtitles.values())
        except RichMetadataException,e:
            print >> sys.stderr, "Warning: Retrievement of all subtitles failed: " + str(e)
        
    
    def addRichMetadataContent(self,channelCastMessage, destPermid = None, fromQuery = False):
        '''
        Takes plain channelcast message (from OLProto v.13) and adds to it
        a 'rich_metadata' field.
        
        @param channelCastMessage: the old channelcast message in the format of
                                   protocol v13
        @param destPermid: the destination of the message. If not None it is used
                            for logging purposes only. If None, nothing bad happens.
        @return: the "enriched" channelcast message
        '''
        if not len(channelCastMessage) > 0:
            if DEBUG:
                print >> sys.stderr, "no entries to enrich with rmd"
            return channelCastMessage
        
        if DEBUG:
            if fromQuery: 
                print >> sys.stderr, "Intercepted a channelcast message as answer to a query"
            else:
                print >> sys.stderr, "Intercepted a channelcast message as normal channelcast"
        #otherwise I'm modifying the old one (even if there's nothing bad
        #it's not good for the caller to see its parameters changed :)
        newMessage = dict()
            
        # a channelcast message is made up of a dictionary of entries
        # keyed the signature. Every value in the dictionary is itself
        # a dictionary with the item informatino
        for key in iter(channelCastMessage):
            entryContent = copy(channelCastMessage[key])
            newMessage[key] = entryContent
            
            channel_id = entryContent['publisher_id']
            infohash = entryContent['infohash']
            #not clean but the fastest way :(
            # TODO: make something more elegant
            metadataDTO = self.rmdDb.getMetadata(channel_id, infohash)
            if metadataDTO is not None:
                try:
                    if DEBUG:
                        print >> sys.stderr, "Enriching a channelcast message with subtitle contents"
                    metadataPack = metadataDTO.serialize()
                    
                    # I can remove from the metadata pack the infohash, and channelId
                    # since they are already in channelcast and they would be redundant
                    metadataPack.pop(0)
                    metadataPack.pop(0)
                    
                    #adding the haveMask at the end of the metadata pack
                    havemask = self.peerHaveManager.retrieveMyHaveMask(channel_id, infohash)
                    binary_havemask = uintToBinaryString(havemask)
                    metadataPack.append(binary_havemask)
                    
                    
                    entryContent['rich_metadata'] = metadataPack
                    
                    if DEBUG:
                        size = self._computeSize(metadataPack)
                        # if available records also the destination of the message
                        dest = "NA" if destPermid is None else show_permid_short(destPermid)
                    
                        id = "SQ" if fromQuery else "S"
                        # format (S (for sent) | SQ (for sent as response to a query), channel, infohash, destination, timestampe, size)
                        print >> sys.stderr, "%c, %s, %s, %s, %d, %d" % \
                            (id, bin2str(metadataDTO.channel), \
                            bin2str(metadataDTO.infohash), \
                             dest, metadataDTO.timestamp, size)
                except Exception,e:
                    print >> sys.stderr, "Warning: Error serializing metadata: %s", str(e)
                    return channelCastMessage
            else:
                # better to put the field to None, or to avoid adding the
                # metadata field at all?
                ##entryContent['rich_metadata'] = None
                pass
            
            
        
            
        return newMessage
    
def validMetadataEntry(entry):
    if entry is None or len(entry) != 6:
        if DEBUG:
            print >> sys.stderr, "An invalid metadata entry was found in channelcast message"
        return False
    
    if not isinstance(entry[1], int) or entry[1] <= 0:
        if DEBUG:
            print >> sys.stderr, "Invalid rich metadata: invalid timestamp"
        return False
   
    if not isinstance(entry[2], basestring) or not len(entry[2]) == 4: #32 bit subtitles mask
        if DEBUG:
            print >> sys.stderr, "Invalid rich metadata: subtitles mask"
        return False
    
    if not isinstance(entry[3], list):
        if DEBUG:
            print >> sys.stderr, "Invalid rich metadata: subtitles' checsums"
        return False
    else:
        for checksum in entry[3]:
            if not isinstance(entry[2], basestring) or not len(checksum) == 20:
                if DEBUG:
                    print >> sys.stderr, "Invalid rich metadata: subtitles' checsums"
                return False

    
    if not isinstance(entry[2], basestring) or not len(entry[5]) == 4: #32 bit have mask
        if DEBUG:
            print >> sys.stderr, "Invalid rich metadata: have mask"
        return False
    
    return True
    
    
