import unittest

from Tribler.TUPT.TUPTControl import MovieTorrent
from Tribler.TUPT.TUPTControl import MovieTorrentIterator
from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl

from Tribler.TUPT.Movie import Movie

from Tribler.Test.TUPT.test_StubPluginManager import PluginManagerStub
from Tribler.Test.TUPT.test_StubPluginManager import TorrentDefStub
  

class TestMovieTorrentIterator(unittest.TestCase):
    
    def setUp(self):
        self.__movies = MovieTorrentIterator()
        self.__torrentFinderControl = TorrentFinderControl(PluginManagerStub())
        self.__movie = MovieTorrent('Title', self.__torrentFinderControl)
        self.__hdTorrentDef = TorrentDefStub(True, Movie())
        self.__sdTorrentDef = TorrentDefStub(False, Movie())
    
    def test_append(self):
        #Act        
        self.__movies.append(self.__movie)
        #Assert
        self.assertEqual(self.__movie, self.__movies.GetMovie(0))
        
    def test_HasHDTorrent_HasHDTorrent(self):
        #Arrange
        self.__torrentFinderControl.ProcessTorrentDef(self.__hdTorrentDef, 0.5)
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.HasHDTorrent(0)
        #Assert
        self.assertTrue(result)
    
    def test_HasHDTorrent_HasNoHDTorrent(self):
         #Arrange
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.HasHDTorrent(0)
        #Assert
        self.assertFalse(result)
  
    def test_HasSDTorrent_HasSDTorrent(self):
         #Arrange
        self.__torrentFinderControl.ProcessTorrentDef(self.__sdTorrentDef, 0.5)
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.HasSDTorrent(0)
        #Assert
        self.assertTrue(result)
    
    def test_HasSDTorrent_HasNoSDTorrent(self):
         #Arrange
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.HasSDTorrent(0)
        #Assert
        self.assertFalse(result)
        
    def test_GetNextHDTorrent(self):
         #Arrange
        self.__torrentFinderControl.ProcessTorrentDef(self.__hdTorrentDef, 0.5)
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.GetNextHDTorrent(0)
        #Assert
        self.assertEqual(self.__hdTorrentDef, result)
        
    def test_GetNextSDTorrent(self):
         #Arrange         
        self.__torrentFinderControl.ProcessTorrentDef(self.__sdTorrentDef, 0.5)
        self.__movies.append(self.__movie)
        #Act        
        result = self.__movies.GetNextSDTorrent(0)
        #Assert
        self.assertEqual(self.__sdTorrentDef, result)
        


class TestMovieTorrent(unittest.TestCase):
    '''Class to test MovieTorrent'''
    
    def setUp(self):
        self.__torrentFinder = TorrentFinderControl(PluginManagerStub())
        self.__movie =  MovieTorrent('NaN',self.__torrentFinder)
    
    def test_HasHDTorrent_HasHDTorrents(self):
        #Arrange
        self.__torrentFinder.ProcessTorrentDef(TorrentDefStub(True, Movie()), 0.5)
        #Act
        result = self.__movie.HasHDTorrent()
        #Assert
        self.assertTrue(result)
        
    def test_HasHDTorrent_HasNoHDTorrents(self):
        #Act
        result = self.__movie.HasHDTorrent()
        #Assert
        self.assertFalse(result)
        
    def test_HasSDTorrent_HasSDTorrents(self):
        #Arrange
        self.__torrentFinder.ProcessTorrentDef(TorrentDefStub(False, Movie()), 0.5)
        #Act
        result = self.__movie.HasSDTorrent()
        #Assert
        self.assertTrue(result)
        
    def test_HasSDTorrent_HasNoSDTorrents(self):
        #Act
        result = self.__movie.HasSDTorrent()
        #Assert
        self.assertFalse(result)
        
    def test_HasTorrents_HasTorrent(self):
         #Arrange
        self.__torrentFinder.ProcessTorrentDef(TorrentDefStub(True, Movie()), 0.5)
        #Act
        result = self.__movie.HasTorrent()
        #Assert
        self.assertTrue(result)
    
    def test_HasTorrents_HasNoTorrent(self):
        #Act
        result = self.__movie.HasTorrent()
        #Assert
        self.assertFalse(result)



if __name__ == '__main__':
    unittest.main()