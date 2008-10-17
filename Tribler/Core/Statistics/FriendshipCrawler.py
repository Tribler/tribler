# Written by Ali Abbas
# see LICENSE.txt for license information

import sys
import time
from traceback import print_exc

from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.CacheDB.SqliteCacheDBHandler import SQLiteCacheDB
from Tribler.Core.CacheDB.SqliteFriendshipStatsCacheDB import FriendshipStatisticsDBHandler

DEBUG = True

class FriendshipCrawler:
    __single = None

    @classmethod
    def get_instance(cls, *args, **kargs):
        if not cls.__single:
            cls.__single = cls(*args, **kargs)
        return cls.__single

    def __init__(self,session):
        self.session = session
        self.friendshipStatistics_db = FriendshipStatisticsDBHandler.getInstance()

    def query_initiator(self, permid, selversion, request_callback):
        """
        Established a new connection. Send a CRAWLER_DATABASE_QUERY request.
        @param permid The Tribler peer permid
        @param selversion The oberlay protocol version
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if DEBUG: 
            print >>sys.stderr, "crawler: friendship_query_initiator"
        
        get_last_updated_time = self.friendshipStatistics_db.getLastUpdateTimeOfThePeer(permid)
         
        msg_dict = {'current time':get_last_updated_time}
        msg = bencode(msg_dict)
        return request_callback(CRAWLER_FRIENDSHIP_STATS,msg)

    def handle_crawler_request(self, permid, selversion, channel_id, message, reply_callback):
        """
        Received a CRAWLER_FRIENDSHIP_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param reply_callback Call this function once to send the reply: reply_callback(payload [, error=123])
        """
        if DEBUG:
            print >> sys.stderr, "crawler: handle_friendship_crawler_database_query_request", message

        try:
            d = bdecode(message)
            
            stats = self.getStaticsFromFriendshipStatisticsTable(self.session.get_permid(),d['current time'])
            msg_dict = {'current time':d['current time'],'stats':stats}
            msg = bencode(msg_dict)
            reply_callback(msg)

        except Exception, e:
            print_exc()
            reply_callback(str(e), 1)

        return True

    def handle_crawler_reply(self, permid, selversion, channel_id, message, request_callback):
        """
        Received a CRAWLER_FRIENDSHIP_STATS request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        
        d = bdecode(msg)
        
        if DEBUG:
            print >> sys.stderr, "crawler: handle_friendship_crawler_database_query_reply"
            print >> sys.stderr, "crawler: friendship: Got",`d`

        self.saveFriendshipStatistics(permid,d['current time'],d['stats'])

        return True 

            
        
    def getStaticsFromFriendshipStatisticsTable(self, mypermid, last_update_time):
        return self.friendshipStatistics_db.getAllFriendshipStatistics(mypermid, last_update_time)
    
    def saveFriendshipStatistics(self,permid,currentTime,stats):
        
        self.friendshipStatistics_db.saveFriendshipStatisticData(stats)
    
    def getLastUpdateTime(self, permid):
        
        mypermid = self.session.get_permid()
        
        return self.friendshipStatistics_db.getLastUpdatedTime(permid)
        
