import unittest

import difflib
import time
import thread

from Tribler.TUPT.Channels.MovieChannelControl import MovieChannelControl
from Tribler.Main.Utility.GuiDBTuples import Channel

class ChannelManagerStub(object):
    
    #id, dispersy_cid, name, description, nr_torrents, nr_favorites, nr_spam, my_vote, modified, my_channel
    miniDB = [Channel(0,0,"Movies of 1999","Auto-generated TUPT channel for movies of the year 1999",0,0,0,0,0,1),  #Normal
              Channel(1,0,"Movies of 2000","Auto-generated TUPT channel for movies of the year 2000",0,0,0,0,0,1),  #Normal 
              Channel(2,0,"Movies of 2001","Auto-generated TUPT channel for movies of the year 2001",0,0,0,0,0,1),  #Normal
              Channel(3,0,"Movies of 2001","I'm faking it",0,0,0,0,0,0),                                    #Bad description
              Channel(4,0,"A channel","Movies of 2001",0,0,0,0,0,0),                                        #Bad name
              Channel(5,0,"Movies of 2001","Auto-generated TUPT channel for movies of the year 2001",5,0,0,0,0,0)]  #More popular
    
    search = []
    
    def setSearchKeywords(self, list):
        self.search = list
    
    def getChannelHits(self):
        hits = []
        for channel in self.miniDB:
            for kw in self.search:
                if difflib.SequenceMatcher(None, kw, channel.name).ratio() == 1 or difflib.SequenceMatcher(None, kw, channel.description).ratio() == 1:
                    hits.append(channel)
                    break
        return len(hits), hits, hits    #Our new hits equal our hits
    
    def fakeDBInsertion(self, name, description):
        time.sleep(0.3)
        channel = Channel(len(self.miniDB),0,name,description,0,0,0,0,0,1)
        self.miniDB.append(channel)
        
    def createChannel(self, name, description):
        thread.start_new(self.fakeDBInsertion, (name, description))
    
    def getMyChannels(self):
        out = []
        for channel in self.miniDB:
            if channel.my_channel == 1:
                out.append(channel)
        return 1, out
    
    def getChannel(self, id):
        return self.miniDB[id]
    
    def createTorrentFromDef(self, channelid, tdef):
        return "This is a Torrent object"
    
    def removeTorrent(self, channelid, infohash):
        pass

class TestChannelControl(unittest.TestCase):
    '''Tests for adding channels with the ChannelControl'''
    
    def setUp(self):
        #Arrange
        self.__channelControl = MovieChannelControl(True)
        self.__fakeManager = ChannelManagerStub()
        self.__channelControl.initWithChannelSearchManager(self.__fakeManager)
    
    def test_ChannelObjectFromID(self):
        #Arrange
        id = 3
        #Act
        channel = self.__channelControl.GetChannelObjectFromID(1)
        #Assert
        self.assertEqual(channel, self.__fakeManager.miniDB[1])
    
    def test_NewChannelIDFromYear(self):
        #Arrange
        year = 2005
        #Act
        id = self.__channelControl.GetChannelIDForYear(year)
        #Assert
        self.assertEqual(id, 6)
    
    def test_ExistingChannelIDFromYear(self):
        #Arrange
        year = 2000
        #Act
        id = self.__channelControl.GetChannelIDForYear(year)
        #Assert
        self.assertEqual(id, 1)
    
    def test_UniformChannelDescription(self):
        #Arrange
        year = 1999
        #Act
        name = self.__channelControl.GetChannelDescriptionForYear(year)
        #Assert
        self.assertEqual(name, "Auto-generated TUPT channel for movies of the year 1999")
    
    def test_UniformChannelName(self):
        #Arrange
        year = 1999
        #Act
        name = self.__channelControl.GetChannelNameForYear(year)
        #Assert
        self.assertEqual(name, "Movies of 1999")
    
if __name__ == '__main__':
    unittest.main()