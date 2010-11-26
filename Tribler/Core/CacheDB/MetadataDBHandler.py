# Written by Andrea Reale
# see LICENSE.txt for license information

from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.CacheDB.SqliteCacheDBHandler import BasicDBHandler
import threading
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB

import sys
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import SignatureException, \
    MetadataDBException
from Tribler.Core.Utilities.utilities import bin2str, str2bin
import sqlite3
import time


SUBTITLE_LANGUAGE_CODE = "lang"
SUBTITLE_PATH = "path"

METADATA_TABLE = "Metadata"

MD_ID_KEY = "metadata_id"
MD_PUBLISHER_KEY = "publisher_id"
MD_INFOHASH_KEY = "infohash"
MD_DESCRIPTION_KEY = "description"
MD_TIMESTAMP_KEY = "timestamp"
MD_SIGNATURE_KEY = "signature"


SUBTITLES_TABLE = "Subtitles"

SUB_MD_FK_KEY = "metadata_id_fk"
SUB_LANG_KEY = "subtitle_lang"
SUB_LOCATION_KEY = "subtitle_location"
SUB_CHECKSUM_KEY = "checksum"

SUBTITLES_HAVE_TABLE = "SubtitlesHave"

SH_MD_FK_KEY = "metadata_id_fk"
SH_PEER_ID_KEY = "peer_id"
SH_HAVE_MASK_KEY = "have_mask"
SH_TIMESTAMP = "received_ts"


# maximum number of have entries returned
# by the database (-1 for unlimited)
SH_RESULTS_LIMIT = 200

DEBUG = False

#it's good to have all of the queries in one place:
#the code is more easy to read, and if some query is wrong
#it is easier to correct them all
SELECT_SUBS_JOIN_BASE = "SELECT sub." + SUB_MD_FK_KEY + ", sub." + SUB_LANG_KEY \
             + ", sub." + SUB_LOCATION_KEY \
             + ", sub." + SUB_CHECKSUM_KEY \
             + " FROM " + METADATA_TABLE + " AS md " \
             + "INNER JOIN " \
             + SUBTITLES_TABLE + " AS sub " \
             + "ON md." + MD_ID_KEY + " = sub." + SUB_MD_FK_KEY
             
MD_SH_JOIN_CLAUSE = \
            METADATA_TABLE + " AS md " \
            + "INNER JOIN " \
            + SUBTITLES_HAVE_TABLE + " AS sh " \
            + "ON md." + MD_ID_KEY + " = sh." + SH_MD_FK_KEY


QUERIES = { 
           "SELECT SUBS JOIN HASH ALL" : 
           SELECT_SUBS_JOIN_BASE  
             + " WHERE md." + MD_INFOHASH_KEY + " = ?"\
             + " AND md." + MD_PUBLISHER_KEY + " = ?;",
           
           "SELECT SUBS JOIN HASH ONE" :
           SELECT_SUBS_JOIN_BASE 
             + " WHERE md." + MD_INFOHASH_KEY + " = ?"\
             + " AND md." + MD_PUBLISHER_KEY + " = ?"\
             + " AND sub." + SUB_LANG_KEY + " = ?;",
             
           "SELECT SUBS FK ALL" :
           "SELECT * FROM " + SUBTITLES_TABLE  
             + " WHERE " + SUB_MD_FK_KEY + " = ?;",
           
           "SELECT SUBS FK ONE" :
           "SELECT * FROM " + SUBTITLES_TABLE  
             + " WHERE " + SUB_MD_FK_KEY + " = ?"\
             + " AND " + SUB_LANG_KEY + " = ?;",
             
           "SELECT METADATA" : 
           "SELECT * FROM " \
             + METADATA_TABLE + " WHERE " + MD_INFOHASH_KEY + " = ?" \
             + " AND " + MD_PUBLISHER_KEY + " = ?;",
           
           "SELECT PUBLISHERS FROM INFOHASH":
           "SELECT " + MD_PUBLISHER_KEY + " FROM " + METADATA_TABLE \
             + " WHERE " + MD_INFOHASH_KEY + " = ?;",
             
           "UPDATE METADATA" : 
           "UPDATE " + METADATA_TABLE \
             + " SET "  \
             + MD_DESCRIPTION_KEY + " = ?, " \
             + MD_TIMESTAMP_KEY + " = ?, " \
             + MD_SIGNATURE_KEY + " = ?" \
             + " WHERE " + MD_INFOHASH_KEY + " = ?" \
             + " AND " + MD_PUBLISHER_KEY + " = ?;",
             
           "UPDATE SUBTITLES" : 
           "UPDATE " + SUBTITLES_TABLE \
             + " SET " + SUB_LOCATION_KEY + "= ?, " \
             + SUB_CHECKSUM_KEY + "= ?" \
             + " WHERE " + SUB_MD_FK_KEY + "= ?" \
              + " AND " + SUB_LANG_KEY + "= ?;",
            
           "DELETE ONE SUBTITLES" :
           "DELETE FROM " + SUBTITLES_TABLE \
            + " WHERE " + SUB_MD_FK_KEY + "= ? " \
            + " AND " + SUB_LANG_KEY + "= ?;",
            
            "DELETE ONE SUBTITLE JOIN" :
            "DELETE FROM " + SUBTITLES_TABLE \
            + " WHERE " + SUB_MD_FK_KEY  \
            + " IN ( SELECT " + MD_ID_KEY + " FROM " + METADATA_TABLE \
            + " WHERE " + MD_PUBLISHER_KEY + " = ?"  \
            + " AND " + MD_INFOHASH_KEY + " = ? )"  \
            + " AND " + SUB_LANG_KEY + "= ?;",
            
           "DELETE ALL SUBTITLES" :
           "DELETE FROM " + SUBTITLES_TABLE \
            + " WHERE " + SUB_MD_FK_KEY + "= ?;",
            
           "DELETE METADATA PK" :
           "DELETE FROM " + METADATA_TABLE \
            + " WHERE " + MD_ID_KEY + " = ?;",
           
           "INSERT METADATA" :
           "INSERT or IGNORE INTO " + METADATA_TABLE + " VALUES " \
             + "(NULL,?,?,?,?,?)",
             
           "INSERT SUBTITLES" : 
           "INSERT INTO " + SUBTITLES_TABLE + " VALUES (?, ?, ?, ?);",
           
           "SELECT SUBTITLES WITH PATH":
           "SELECT sub." + SUB_MD_FK_KEY + ", sub." + SUB_LOCATION_KEY  + ", sub." \
           + SUB_LANG_KEY + ", sub." + SUB_CHECKSUM_KEY \
           + ", m." + MD_PUBLISHER_KEY + ", m." + MD_INFOHASH_KEY \
           + " FROM " + METADATA_TABLE + " AS m " \
           +"INNER JOIN " + SUBTITLES_TABLE + " AS sub "\
           + "ON m." + MD_ID_KEY + " = " + " sub." + SUB_MD_FK_KEY \
           + " WHERE " \
           + SUB_LOCATION_KEY + " IS NOT NULL;",
           
           "SELECT SUBTITLES WITH PATH BY CHN INFO":
           "SELECT sub." + SUB_LOCATION_KEY  + ", sub." \
           + SUB_LANG_KEY + ", sub." + SUB_CHECKSUM_KEY \
           + " FROM " + METADATA_TABLE + " AS m " \
           +"INNER JOIN " + SUBTITLES_TABLE + " AS sub "\
           + "ON m." + MD_ID_KEY + " = " + " sub." + SUB_MD_FK_KEY \
           + " WHERE sub." \
           + SUB_LOCATION_KEY + " IS NOT NULL" \
           + " AND m." + MD_PUBLISHER_KEY + " = ?"\
           + " AND m." + MD_INFOHASH_KEY + " = ?;" ,
           
           "INSERT HAVE MASK":
           "INSERT INTO " + SUBTITLES_HAVE_TABLE + " VALUES " \
           + "(?, ?, ?, ?);",
           
           "GET ALL HAVE MASK":
           "SELECT sh." + SH_PEER_ID_KEY + ", sh." + SH_HAVE_MASK_KEY \
           + ", sh." + SH_TIMESTAMP \
           + " FROM " + MD_SH_JOIN_CLAUSE + " WHERE md." + MD_PUBLISHER_KEY \
           + " = ? AND md." + MD_INFOHASH_KEY + " = ? "\
           + "ORDER BY sh." + SH_TIMESTAMP + " DESC" \
           + " LIMIT " + str(SH_RESULTS_LIMIT) + ";",
           
           "GET ONE HAVE MASK":
           "SELECT sh." + SH_HAVE_MASK_KEY \
           + ", sh." + SH_TIMESTAMP \
           + " FROM " + MD_SH_JOIN_CLAUSE + " WHERE md." + MD_PUBLISHER_KEY \
           + " = ? AND md." + MD_INFOHASH_KEY + " = ? AND sh." + SH_PEER_ID_KEY \
           + " = ?;",
           
           "UPDATE HAVE MASK":
           "UPDATE " + SUBTITLES_HAVE_TABLE \
           + " SET " + SH_HAVE_MASK_KEY + " = ?, " \
           + SH_TIMESTAMP + " = ?" \
           + " WHERE " + SH_PEER_ID_KEY + " = ?" \
           + " AND " + SH_MD_FK_KEY + " IN " \
           + "( SELECT + " + MD_ID_KEY+  " FROM " \
           +  METADATA_TABLE + " WHERE + "\
           +  MD_PUBLISHER_KEY + " = ?"\
           + " AND " + MD_INFOHASH_KEY + " = ? );",
           
           "DELETE HAVE":
           "DELETE FROM " + SUBTITLES_HAVE_TABLE \
           + " WHERE " + SH_PEER_ID_KEY + " = ?" \
           + " AND " + SH_MD_FK_KEY + " IN " \
           + "( SELECT + " + MD_ID_KEY+  " FROM " \
           +  METADATA_TABLE + " WHERE + "\
           +  MD_PUBLISHER_KEY + " = ?"\
           + " AND " + MD_INFOHASH_KEY + " = ? );",
           
           "CLEANUP OLD HAVE":
           "DELETE FROM " + SUBTITLES_HAVE_TABLE \
           + " WHERE " + SH_TIMESTAMP + " < ? " \
           + " AND " + SH_PEER_ID_KEY + " NOT IN " \
           + "( SELECT md." + MD_PUBLISHER_KEY + " FROM " \
           + METADATA_TABLE + " AS md WHERE md." + MD_ID_KEY \
           + " = " + SH_MD_FK_KEY + " );"   
           }

class MetadataDBHandler (object, BasicDBHandler):
    
    """
    Data Access Layer for the subtitles database.
    """
    
    __single = None    # used for multithreaded singletons pattern
    _lock = threading.RLock()
    
    @staticmethod
    def getInstance(*args, **kw):        
        if MetadataDBHandler.__single is None:
            MetadataDBHandler._lock.acquire()   
            try:
                if MetadataDBHandler.__single is None:
                    MetadataDBHandler(*args, **kw)
            finally:
                MetadataDBHandler._lock.release()
        return MetadataDBHandler.__single
    
    
    def __init__(self, db=SQLiteCacheDB.getInstance()):
        # notice that singleton pattern is not enforced.
        # This way the code is more easy
        # to test.
        
        try:
            MetadataDBHandler._lock.acquire()
            MetadataDBHandler.__single = self
        finally:
            MetadataDBHandler._lock.release()
        
        try:
            self._db = db
            # Don't know what those life should know. Assuming I don't need 
            # them 'till a countrary proof! (Ask Nitin) 
            # BasicDBHandler.__init__(self,db,METADATA_TABLE)
            # BasicDBHandler.__init__(self,db,SUBTITLES_TABLE)
            print >> sys.stderr, "Metadata: DB made" 
        except: 
            print >> sys.stderr, "Metadata: couldn't make the tables"
        
        
        print >> sys.stderr, "Metadata DB Handler initialized"
        
    def commit(self):
        self._db.commit()
                
#    Commented for the sake of API simplicity
#    But then uncommented for coding simplicity :P
    def getAllSubtitles(self, channel, infohash):
        """
        Get all the available subtitles for a channel and infohash.
        
        Returns a list representing subtitles that are available for
        a givenchannel and infohash. 
        
        @param channel: the perm_id of the channel owner (binary)
        @param infohash: the infhash of a channel elements as it
                         is announced in ChannelCast (binary)
        @return: a dictionary of { lang : SubtitleInfo instance}
        """
        
        query = QUERIES["SELECT SUBS JOIN HASH ALL"]
        infohash = bin2str(infohash)
        channel = bin2str(channel)
          
        results = self._db.fetchall(query, (infohash, channel))
        
        subsDict = {}
        for entry in results:
            subsDict[entry[1]] = SubtitleInfo(entry[1], entry[2], entry[3])
     
        return subsDict
    
    def _deleteSubtitleByChannel(self, channel, infohash, lang):
        '''
        Remove a subtitle for a channel infohash
        
        @param channel: the channel where the subtitle is (binary)
        @param infohash: the infohash of the torrent referred by the subtitle
                        (binary)
        @param lang: ISO-639-2 language code of the subtitle to remove
        
        '''
        
        query = QUERIES["DELETE ONE SUBTITLE JOIN"]
        
        infohash = bin2str(infohash)
        channel = bin2str(channel)
        
        self._db.execute_write(query,(channel, infohash, lang))


    def _getAllSubtitlesByKey(self, metadataKey):
        '''
        Retrieves every subtitles given a Metadata table key
        
        Given an instance of the Metadata table artificial key, retrieves
        every subtitle instance associated to that key
        
        @param metadataKey: a value of an artificial key in the Metadata table
        @return : a dictionary of type {lang : SubtitleInfo}, empty if no results
        '''
        query = QUERIES["SELECT SUBS FK ALL"]
        
          
        results = self._db.fetchall(query, (metadataKey,))
        subsDict = {}
        for entry in results:
            subsDict[entry[1]] = SubtitleInfo(entry[1], entry[2], str2bin(entry[3]))
     
        return subsDict

        
#    commented for the sake of API simplicity
#    def hasSubtitleInLang(self,channel,infohash, lang):
#        """
#        Checks whether an item in a channel as available subitltles.
#        
#        @param channel: a perm_id identifying the owner of the channel.
#        @param infohash: the infohash of an item, as announced in channelcast
#                         messages.
#        @param lang: a 3 characters ISO 639-2 language code, identifying
#                     the desired subtitle langugage
#        @return:  bool
#        """
#        sub = self.getSubtitle(channel, infohash, lang)
#        return sub is not None
#    
    
#    commented for the sake of api simplicity
#    But then uncommented for coding simplicity :P
    def getSubtitle(self, channel, infohash, lang):
        """
        Get a subtitle for a language for a given item in a given channel.
        
        Returns the details reguarding a subtitles in a given language for a
        given item in a given channel, if it exists. Otherwise it returns
        None.
        
        @param channel: a perm_id identifying the owner of the channel.
        @param infohash: the infohash of an item, as announced in channelcast
                         messages.
        @param lang: a 3 characters ISO 639-2 language code, identifying
                     the desired subtitle langugage
        @return: a SubtitleInfo instance
        """
        query = QUERIES["SELECT SUBS JOIN HASH ONE"]
        
        infohash = bin2str(infohash)
        channel = bin2str(channel)
          
          
        res = self._db.fetchall(query, (infohash, channel, lang))
        if len(res) == 0 :
            return None
        elif len(res) == 1 :
            checksum = str2bin(res[0][3])
            return SubtitleInfo(res[0][1], res[0][2], checksum)
        else : 
            # This should be not possible to database constraints
            raise MetadataDBException("Metadata DB Constraint violeted!")
    

            
    def _getSubtitleByKey(self, metadata_fk, lang):
        """
        Return a subtitle in a given language for a key of the Metadata table.
        
        Given an instance of the artificial key in the metadata table,
        retrieves a SubtitleInfo instance for that key and the language passed in.
        
        @param metadata_fk: a key in the metadata table
        @param lang: a language code for the subtitle to be retrieved
        
        @return: a SubtitleInfo instance, or None
        """
        query = QUERIES["SELECT SUBS FK ONE"]
          
          
        res = self._db.fetchall(query, (metadata_fk, lang))
        if len(res) == 0 :
            return None
        elif len(res) == 1 :
            checksum = str2bin(res[0][3])
            return SubtitleInfo(res[0][1], res[0][2], checksum)
        else : 
            # This should be not possible to database constraints
            raise MetadataDBException("Metadata DB Constraint violeted!")
        
        
    def getMetadata(self, channel, infohash):
        """
        Returns a MetadataDTO instance for channel/infohash if available in DB
        
        Given a channel/infhash couple returns a MetadataDTO instance, built
        with the values retrieved from the Metadata and Subtitles DB. If
        no result returns None
        
        @param channel: the permid of the channel's owner (binary)
        @param infohash: the infohash of the item the metadata refers to
                         (binary)
        @return: a MetadataDTO instance comprehensive of subtitles if any
                 metadata is found in the DB. None otherwise.
        """
        
        query = QUERIES["SELECT METADATA"]
        
        infohash = bin2str(infohash)
        channel = bin2str(channel)
        
        res = self._db.fetchall(query, (infohash, channel))
        
        if len(res) == 0:
            return None
        if len(res) > 1:
            raise MetadataDBException("Metadata DB Constraint violated")
        
        metaTuple = res[0]
        
        subsDictionary = self._getAllSubtitlesByKey(metaTuple[0])
        
        publisher = str2bin(metaTuple[1])
        infohash =  str2bin(metaTuple[2])
        timestamp = int(metaTuple[4])
        description = unicode(metaTuple[3])
        signature = str2bin(metaTuple[5])
        
        toReturn = MetadataDTO(publisher, infohash,
                               timestamp, description, None,
                               signature)
        
        for sub in subsDictionary.itervalues():
            toReturn.addSubtitle(sub)
        
        return toReturn

    
    def getAllMetadataForInfohash(self, infohash):
        """
        Returns a list of MetadataDTO instances for a given infohash
        
        Given a torrent infohash returns a list of MetadataDTO instances for
        that infohash. Each one of the MetadataDTO refers to a different
        channel.
        
        @param infohash: the infohash for the torrent (binary)
        @return: a list of MetadataDTO isntances (or empty list if nothing
                 is found)
        """
        
        assert infohash is not None
        
        strinfohash = bin2str(infohash)
        
        query = QUERIES["SELECT PUBLISHERS FROM INFOHASH"]
        
        channels = self._db.fetchall(query, (strinfohash,))
        
        return [self.getMetadata(str2bin(entry[0]), infohash) for entry in channels]
        
      
        
    
    def hasMetadata(self, channel, infohash):
        """
        Checks whether there exists some metadata for an item in a channel.
        
        @param channel: a perm_id identifying the owner of the channel.
        @param infohash: the infohash of an item, as announced in channelcast
                         messages.
        @return boolean
        """
        query = QUERIES["SELECT METADATA"]
        
        infohash = bin2str(infohash)
        channel = bin2str(channel)
        
        res = self._db.fetchall(query, (infohash, channel))
        return len(res) != 0
    
    
    def insertMetadata(self, metadata_dto):
        '''
        Insert the metadata contained in a Metadata DTO in the database.
        
        If an entry relative to the same channel and infohash of the provided 
        dto already exists in the db, the db is updated only if the timestamp
        of the new dto is newer then the entry in the database. 
        If there is no such an entry, a new wan in the Metadata DB is created
        along with the required entries in the SubtitleInfo DB
        
        @type metadata_dto: MetadataDTO 
        @param metada_dto: an instance of MetadataDTO describing metadata
        
        @return True if an existing entry was updated,  false if a new entry
                was interested. Otherwise None.
        
        '''
        assert metadata_dto is not None
        assert isinstance(metadata_dto, MetadataDTO)
        #try to retrieve a correspindng record for channel,infhoash
        
        #won't do nothing if the metadata_dto is not correctly signed
        if not metadata_dto.verifySignature():
            raise SignatureException("Metadata to insert is not properly" \
                                     "signed")
        
        select_query = QUERIES["SELECT METADATA"]
          
        signature = bin2str(metadata_dto.signature)
        infohash = bin2str(metadata_dto.infohash)
        channel = bin2str(metadata_dto.channel)
        
        res = self._db.fetchall(select_query,
                                (infohash, channel))
    
        isUpdate = False
    
        if len(res) != 0 :
            #updated if the new message is newer
            if metadata_dto.timestamp > res[0][4] :
                query = QUERIES["UPDATE METADATA"]
                
                
                self._db.execute_write(query,
                                    (metadata_dto.description,
                                    metadata_dto.timestamp,
                                    signature,
                                    infohash,
                                    channel,),
                                   False) #I don't want the transaction to commit now
                
                fk_key = res[0][0]
                
                isUpdate = True
        
            else:
                return
                
        else: #if is this a whole new metadata item
            query = QUERIES["INSERT METADATA"]
            
            self._db.execute_write(query,
                                   (channel,
                                    infohash,
                                    metadata_dto.description,
                                    metadata_dto.timestamp,
                                    signature,
                                    ),
                                   True) 
            
            if DEBUG:
                print >> sys.stderr, "Performing query on db: " + query
            
            newRows = self._db.fetchall(select_query,
                                (infohash, channel))
            
            
            if len(newRows) == 0 : 
                raise IOError("No results, while there should be one")
            
            fk_key = newRows[0][0]
            
            
        self._insertOrUpdateSubtitles(fk_key, metadata_dto.getAllSubtitles(), \
                                      False)
            
        self._db.commit() #time to commit everything
        
        return isUpdate        
        
                
                            
    def _insertOrUpdateSubtitles(self, fk_key, subtitles, commitNow=True):
        """
        Given a dictionary of subtitles updates the corrisponding entries.
        
        This method takes as input a foreign key for the Metadata table,
        and a dictionary of type {lang : SubtitleInfo}. Then it updates the 
        SubtitleInfo table, updating existing entries, deleting entries that are
        in the db but not in the passed dictionary, and inserting entries
        that are in the dictionary but not in the db.
        
        @param fk_key: a foreign key from the Metadata table. Notice that
                       sqlite does not enforce the fk constraint. Be careful!
        @param subtitles: a dictionary {lang : SubtitleInfo} (subtitle must be
                          an instance of SubtitleInfo)
        @param commitNow: if False the transaction is not committed
        """
        
        
        allSubtitles = self._getAllSubtitlesByKey(fk_key)
        oldSubsSet = frozenset(allSubtitles.keys())
        newSubsSet = frozenset(subtitles.keys())
        
        commonLangs = oldSubsSet & newSubsSet
        newLangs = newSubsSet - oldSubsSet
        toDelete = oldSubsSet - newSubsSet
        
        #update existing subtitles
        for lang in commonLangs:
            self._updateSubtitle(fk_key, subtitles[lang], False)
        
        
        #remove subtitles that are no more in the set
        for lang in toDelete:
            self._deleteSubtitle(fk_key, lang, False)
            
        #insert new subtitles
        for lang in newLangs:
            self._insertNewSubtitle(fk_key, subtitles[lang], False)
        
        if commitNow:
            self._db.commit()
            
            
            
        
    def _updateSubtitle(self, metadata_fk, subtitle, commitNow=True):
        """
        Update an entry in the Subtitles database.
        
        If the entry identified by metadata_fk, subtitle.lang does not exist
        in the subtitle database this method does nothing.
        
        @param metadata_fk: foreign key of the metadata table
        @param subtitle: instance of Subitle containing the data to insert
        @param commitNow: if False, this method does not commit the changes to
                          the database
        """
        assert metadata_fk is not None
        assert subtitle is not None
        assert isinstance(subtitle, SubtitleInfo)
                 
        toUpdate = self._getSubtitleByKey(metadata_fk, subtitle.lang)
        
        if toUpdate is None:
            return
        
       
        query = QUERIES["UPDATE SUBTITLES"]
        
        checksum = bin2str(subtitle.checksum)
                            
        self._db.execute_write(query, (subtitle.path,
                        checksum, metadata_fk, subtitle.lang),
                        commitNow) 
        
    def updateSubtitlePath(self, channel, infohash, lang, newPath, commitNow=True):
        """
        Updates a subtitle entry in the database if it exists.
        
        Given the channel, the infohash, and a SubtitleInfo instance,
        the entry relative to that subtitle is updated accordingly 
        to the details in the SubtitleInfo instance.
        If an instance for the provided channel, infohash, and language
        does not already exist in the db, nothing is done.
        
        @param channel: the channel id (permid) of the channel for the
                        subtitle (binary)
        @param infohash: the infohash of the item the subtitle refrs to
                        (binary)
        @param lang: the language of the subtitle to update
        @param path: the new path of the subtitle. None to indicate that the
                    subtitle is not available
        @return True if an entry was updated in the db. False if nothing
                got written on the db
                
        @precondition: subtitle.lang is not None
        """
        query = QUERIES["SELECT SUBS JOIN HASH ONE"]
        
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        
        res = self._db.fetchall(query, (infohash, channel, lang))
        
        if len(res) > 1 :
            raise MetadataDBException("Metadata DB constraint violated")
        elif len(res) == 0 :
            if DEBUG:
                print >> sys.stderr, "Nothing to update for channel %s, infohash %s, lang"\
                        " %s. Doing nothing." % (channel[-10:],\
                                                 infohash, lang)
            return False
        else:
            query = QUERIES["UPDATE SUBTITLES"]
            self._db.execute_write(query, (newPath,
                        res[0][3], res[0][0], lang),
                        commitNow) 
            return True
        
        
        
        
        
    
    def _deleteSubtitle(self, metadata_fk, lang, commitNow=True):
        """
        Delete an entry from the subtitles table.
        
        Given a foreign key from the metadata table  and a language delets
        the corresponding entry in the subtitle table. If the entry
        is not found, it does nothing.
        
        @param metadata_fk: a foreign key from the Metadata table
        @param lang: a 3 characters language code 
        @param commitNow: if False does not commit the transaction
        """
        assert metadata_fk is not None
        assert lang is not None
        
        query = QUERIES["DELETE ONE SUBTITLES"]
        self._db.execute_write(query, (metadata_fk, lang), commitNow)
        
    
    def _insertNewSubtitle(self, metadata_fk, subtitle, commitNow=True) :
        """
        Insert a new subtitle entry in the Subtitles table.
        
        Given a foreign key from the Metadata table, and a SubtitleInfo instance
        describing the subtitle to insert, adds it to the metadata table.
        This method assumes that that entry does not already exist in the
        table.
        NOTICE that sqlite  does not enforce the foreign key constraint,
        so be careful about integrity
        """
        assert metadata_fk is not None
        assert subtitle is not None
        assert isinstance(subtitle, SubtitleInfo)
        
        query = QUERIES["INSERT SUBTITLES"]
        
        checksum = bin2str(subtitle.checksum)
        self._db.execute_write(query, (metadata_fk, subtitle.lang,
                                       subtitle.path, checksum),
                                       commitNow)
    
    def deleteMetadata(self, channel, infohash):
        """
        Removes all the metadata associated to a channel/infohash.
        
        Everything is dropped from both the Metadata and Subtitles db.
        
        @param channel: the permid of the channel's owner
        @param infohash: the infhoash of the entry
        """
        
        assert channel is not None
        assert infohash is not None
        
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        
        query = QUERIES["SELECT METADATA"]
        
        if DEBUG:
            print >> sys.stderr, "Performing query on db: " + query
        
        res = self._db.fetchall(query, (infohash, channel))
        
        if len(res) == 0 :
            return
        if len(res) > 1 :
            raise IOError("Metadata DB constraint violated")
        
        metadata_fk = res[0][0]
        
        self._deleteAllSubtitles(metadata_fk, False)
        
        query = QUERIES["DELETE METADATA PK"]
        
        self._db.execute_write(query, (metadata_fk,), False)
        
        self._db.commit()
        
        
        
        
    
    def _deleteAllSubtitles(self, metadata_fk, commitNow):
        query = QUERIES["DELETE ALL SUBTITLES"]
        
        self._db.execute_write(query, (metadata_fk,), commitNow)
        
    def getAllLocalSubtitles(self):
        '''
        Returns a structure containing all the subtitleInfos that are pointing
        to a local path
        
        @return a dictionary like this:
                { ...
                  channel1 : { infohash1 : [ SubtitleInfo1, ...] }
                  ...
                }
        '''
        query = QUERIES["SELECT SUBTITLES WITH PATH"]
        res = self._db.fetchall(query)
        
        result = {}
        
        for entry in res:
            # fk = entry[0]
            path = entry[1]
            lang = entry[2]
            checksum = str2bin(entry[3])
            channel = str2bin(entry[4])
            infohash = str2bin(entry[5])
            
            s = SubtitleInfo(lang, path, checksum)
            
            if channel not in result:
                result[channel] = {}
            if infohash not in result[channel]:
                result[channel][infohash] = []
            
            result[channel][infohash].append(s)
            
        return result
    
    def getLocalSubtitles(self, channel, infohash):
        '''
        Returns a dictionary containing all the subtitles pointing
        to a local pathm for the given channel, infohash
        @param channel: binary channel_id(permid)
        @param infohash: binary infohash
        
        @rtype: dict
        @return: a dictionary like this:
                {
                 ...
                 langCode : SubtitleInfo,
                 ...
                }
                The dictionary will be empty if no local subtitle
                is available.
        '''
        query = QUERIES["SELECT SUBTITLES WITH PATH BY CHN INFO"]
        
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        res = self._db.fetchall(query,(channel,infohash))
        
        result  = {}
        
        for entry in res:
            location = entry[0]
            language = entry[1]
            checksum = str2bin(entry[2])
            subInfo = SubtitleInfo(language, location, checksum)
            result[language] = subInfo
        
        return result
            
    
    def insertHaveMask(self, channel, infohash, peer_id, havemask, timestamp=None):
        '''
        Store a received have mask in the db
        
        Each inserted rows represent a delcaration of subtitle 
        availability from peer_id, for some subtitles for
        a torrent identified by infohash in a channel identified
        by channel.
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @type peer_id: str
        @param peer_id: peer from whom the infomask was received.(ie its binary permid)
        
        @type havemask: int
        @param havemask: a non-negative integer. It must be smaller
                        then 2**32.
                        
        @precondition: an entry for (channel, infohash) must already
                       exist in the database
        '''
        query = QUERIES["SELECT METADATA"]
        
        if timestamp is None:
            timestamp = int(time.time())
            
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        peer_id = bin2str(peer_id)
        
        res = self._db.fetchall(query, (infohash, channel))
        
        if len(res) != 1:
            raise MetadataDBException("No entry in the MetadataDB for %s, %s" %\
                                      (channel[-10:],infohash))
                                      
        metadata_fk = res[0][0]
        
        insertQuery = QUERIES["INSERT HAVE MASK"]
        
        try:
            self._db.execute_write(insertQuery, (metadata_fk, peer_id, havemask, timestamp))
        except sqlite3.IntegrityError,e:
            raise MetadataDBException(str(e))
            
    
    def updateHaveMask(self,channel,infohash,peer_id, newMask, timestamp=None):
        '''
        Store a received have mask in the db
        
        (See insertHaveMask for description)
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @type peer_id: str
        @param peer_id: peer from whom the infomask was received.(ie its binary permid)
        
        @type havemask: int
        "param havemask: a non-negative integer. It must be smaller
                        then 2**32.
        '''
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        peer_id = bin2str(peer_id)
        
        updateQuery = QUERIES["UPDATE HAVE MASK"]
        if timestamp is None:
            timestamp = int(time.time())
        self._db.execute_write(updateQuery, 
                               (newMask,timestamp,peer_id, channel, infohash))
    
    def deleteHaveEntry(self, channel, infohash, peer_id):
        '''
        Delete a row from the SubtitlesHave db.
        
        If the row is not in the db nothing happens.
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @type peer_id: str
        @param peer_id: peer from whom the infomask was received.(ie its binary permid)
        
        @postcondition: if a row identified by channel, infohash, peer_id
                        was in the database, it will no longer be there
                        at the end of this method call
        
        '''
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        peer_id = bin2str(peer_id)
        deleteQuery = QUERIES["DELETE HAVE"]
        self._db.execute_write(deleteQuery,
                               (peer_id,channel,infohash))
    
    def getHaveMask(self, channel, infohash, peer_id):
        '''
        Returns the have mask for a single peer if available.
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @type peer_id: str
        @param peer_id: peer from whom the infomask was received.(ie its binary permid)
        
        @rtype: int
        @return: the have mask relative to channel, infohash, and peer.
                 If not available returns None
                 
        @postcondition: the return value is either None or a non-negative
                        integer smaller then 2**32
        '''
        
        query = QUERIES["GET ONE HAVE MASK"]
        
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        peer_id = bin2str(peer_id)
        
        res = self._db.fetchall(query,(channel,infohash,peer_id))
        
        if len(res) <= 0:
            return None
        elif len(res) > 1:
            raise AssertionError("channel,infohash,peer_id should be unique")
        else:
            return res[0][0]
        
    
    def getHaveEntries(self, channel, infohash):
        '''
        Return a list of have entries for subtitles for a torrent
        in a channel.
        
        This method returns a list of tuple, like:
        [ 
          ...
          (peer_id, haveMask, timestamp),
          ...
        ]
        
        (peer_id) is the perm_id of a Tribler
        Peer, haveMask is an integer value representing a 
        bitmask of subtitles owned by that peer. 
        Timestamp is the timestamp at the time the havemask
        was received. 
        The results are ordered by descending timestamp.
        If there are no
        entris for the givenn channel,infohash pair, the returned
        list will be empty
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @rtype: list
        @return: see description
        
        '''
        query = QUERIES["GET ALL HAVE MASK"]
        
        channel = bin2str(channel)
        infohash = bin2str(infohash)
        
        res = self._db.fetchall(query,(channel,infohash))
        returnlist = list()
        
        for entry in res:
            peer_id = str2bin(entry[0])
            haveMask = entry[1]
            timestamp = entry[2]
            returnlist.append((peer_id, haveMask, timestamp))
            
        return returnlist
    
    def cleanupOldHave(self, limit_ts):
        '''
        Remove from the SubtitlesHave database every entry
        received at a timestamp that is (strictly) less then limit_ts
        
        This method does not remove have messages sent by
        the publisher of the channel.
        
        @type limit_ts: int
        @param limit_ts: a timestamp. All the entries in the
                         database having timestamp lessere then
                         limit_ts will be removed, excpet if
                         they were received by the publisher
                         of the channel
        '''
        cleanupQuery = QUERIES["CLEANUP OLD HAVE"]
        
        self._db.execute_write(cleanupQuery,(limit_ts,))
        
    
    def insertOrUpdateHave(self, channel, infohash, peer_id, havemask, timestamp=None):
        '''
        Store a received have mask in the db
        
        Each inserted rows represent a delcaration of subtitle 
        availability from peer_id, for some subtitles for
        a torrent identified by infohash in a channel identified
        by channel.
        
        If a row for the given (channel, infohash, peer_id) it 
        is updated accordingly to the parameters. Otherwise
        a new row is added to the db
        
        @type channel: str
        @param channel: channel_id (binary)
        
        @type infohash: str
        @param infohash: the infohash of a torrent (binary)
        
        @type peer_id: str
        @param peer_id: peer from whom the infomask was received.(ie its binary permid)
        
        @type havemask: int
        @param havemask: a non-negative integer. It must be smaller
                        then 2**32.
                        
        @precondition: an entry for (channel, infohash) must already
                       exist in the database
        '''
        
        if timestamp is None:
            timestamp = int(time.time())

            
        if self.getHaveMask(channel, infohash, peer_id) is not None:
            self.updateHaveMask(channel, infohash, peer_id, havemask, timestamp)
        else:
            self.insertHaveMask(channel, infohash, peer_id, havemask, timestamp)
            
        
    
    
    


