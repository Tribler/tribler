import unittest

from Tribler.TUPT.TUPTControl import MovieTorrent
from Tribler.TUPT.TUPTControl import MovieTorrentIterator

from Tribler.Test.TUPT.test_StubPluginManager import PluginManagerStub
  

class TestMovieTorrentIterator(unittest.TestCase):
    
    def test_append(self):
        #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',['HD'],['SD'])
        #Act        
        movies.append(movieTorrent)
        #Assert
        self.assertEqual(movieTorrent, movies.GetNextMovie())
        
    def test_HasHDTorrent_HasHDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',['HD'],['SD'])
        movies.append(movieTorrent)
        #Act        
        result = movies.HasHDTorrent(0)
        #Assert
        self.assertTrue(result)
    
    def test_HasHDTorrent_HasHDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',[],['SD'])
        movies.append(movieTorrent)
        #Act        
        result = movies.HasHDTorrent(0)
        #Assert
        self.assertFalse(result)
  
    def test_HasSDTorrent_HasSDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',['HD'],['SD'])
        movies.append(movieTorrent)
        #Act        
        result = movies.HasSDTorrent(0)
        #Assert
        self.assertTrue(result)
    
    def test_HasSDTorrent_HasNoSDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',['HD'],[])
        movies.append(movieTorrent)
        #Act        
        result = movies.HasSDTorrent(0)
        #Assert
        self.assertFalse(result)
        
    def test_GetNextHDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',[1,2],[])
        movies.append(movieTorrent)
        #Act        
        result = movies.GetNextHDTorrent(0)
        #Assert
        self.assertEqual(1, result)
        
    def test_GetNextSDTorrent(self):
         #Arrange
        movies =  MovieTorrentIterator()
        movieTorrent = MovieTorrent('Title',[1,2],[1,2])
        movies.append(movieTorrent)
        #Act        
        result = movies.GetNextSDTorrent(0)
        #Assert
        self.assertEqual(1, result)
        


class TestMovieTorrent(unittest.TestCase):
    
    def test_HasHDTorrent_HasTorrents(self):
        
     def test_HasHDTorrent_HasHDTorrents(self):
        #Arrange
        movieTorrent = MovieTorrent('NaN',['NaN'],['NaN'])
        #Act
        result = movieTorrent.HasHDTorrent()
        #Assert
        self.assertTrue(result)
        
    def test_HasHDTorrent_HasNoHDTorrents(self):
        #Arrange
        movieTorrent = MovieTorrent('NaN',[],['NaN'])
        #Act
        result = movieTorrent.HasHDTorrent()
        #Assert
        self.assertFalse(result)
        
    def test_HasSDTorrent_HasSDTorrents(self):
        #Arrange
        movieTorrent = MovieTorrent('NaN',['NaN'],['NaN'])
        #Act
        result = movieTorrent.HasSDTorrent()
        #Assert
        self.assertTrue(result)
        
    def test_HasSDTorrent_HasNoSDTorrents(self):
        #Arrange
        movieTorrent = MovieTorrent('NaN',['NaN'],[])
        #Act
        result = movieTorrent.HasSDTorrent()
        #Assert
        self.assertFalse(result)
        
    def test_HasTorrents_HasTorrent(self):
         #Arrange
        movieTorrent = MovieTorrent('NaN',['NaN'],[])
        #Act
        result = movieTorrent.HasTorrent()
        #Assert
        self.assertTrue(result)
    
    def test_HasTorrents_HasNoTorrent(self):
         #Arrange
        movieTorrent = MovieTorrent('NaN',[],[])
        #Act
        result = movieTorrent.HasTorrent()
        #Assert
        self.assertFalse(result)



if __name__ == '__main__':
    unittest.main()