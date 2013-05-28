import unittest

from Tribler.TUPT.TorrentFinder.SortedTorrentList import SortedTorrentList
from Tribler.TUPT.TorrentFinder.MovieTorrentDef import IMovieTorrentDef
from Tribler.TUPT.Movie import Movie

class testMovieTorrentDef(IMovieTorrentDef):
    """Test class with trivial values for testing.
        Allows tester to set return values directly.
        Overwrite by setting variable with lowercase first letter:
         MethodName returns methodName
    """

    def GetSeeders(self):
        return self.getSeeders if hasattr(self, 'getSeeders') else 800

    def GetLeechers(self):
        return self.getLeechers if hasattr(self, 'getLeechers') else 400

    def IsHighDef(self):
        return self.isHighDef if hasattr(self, 'isHighDef') else True

    def GetMovieDescriptor(self):
        stdMovie = Movie()
        stdMovie.dictionary = {'Title':'Apes in Space', 'Director':'Bob Robson', 'Actors':'Sly Schwarzenegger, Brad Stallone'}
        return self.getMovieDescriptor if hasattr(self, 'getMovieDescriptor') else stdMovie

    def GetTorrentName(self):
        return self.getTorrentName if hasattr(self, 'getTorrentName') else '[DVDRip,BBCRipz]Apes.in.space:.odyssey1080p' 

    def GetTorrentURL(self):
        return self.getTorrentURL if hasattr(self, 'getTorrentURL') else 'http://www.google.com/[DVDRip,BBCRipz]Apes.in.space:.odyssey1080p.torrent'

    def GetTorrentProviderName(self):
        return self.getTorrentProviderName if hasattr(self, 'getTorrentProviderName') else 'www.google.com'


class TestSortedTorrentList(unittest.TestCase):
    '''Test class to test PluginManager'''

    def test_DownloadSpeedSort(self):
        '''Test the algorithm prioritizing potential download speed
            given there are no other distinguishable differences.
        '''
        #Arrange
        stList = SortedTorrentList()
        torrentDef1 = testMovieTorrentDef()
        torrentDef1.getSeeders = 10
        torrentDef1.getLeechers = 0 
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getSeeders = 20
        torrentDef2.getLeechers = 0 
        #Act
        stList.Insert(torrentDef1, 1)
        stList.Insert(torrentDef2, 1)
        #Assert     
        assert len(stList.GetList()) == 2
        assert stList.GetList()[0] == torrentDef2
        assert stList.GetList()[1] == torrentDef1
        
    def test_DownloadSpeedSort2(self):
        '''Test the algorithm prioritizing potential download speed
            given there are no other distinguishable differences.
        '''
        #Arrange
        stList = SortedTorrentList()
        torrentDef1 = testMovieTorrentDef()
        torrentDef1.getSeeders = 10
        torrentDef1.getLeechers = 50 
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getSeeders = 20
        torrentDef2.getLeechers = 0 
        #Act
        stList.Insert(torrentDef1, 1)
        stList.Insert(torrentDef2, 1)
        #Assert     
        assert len(stList.GetList()) == 2
        assert stList.GetList()[0] == torrentDef1
        assert stList.GetList()[1] == torrentDef2
        
           
if __name__ == '__main__':
    unittest.main()
    
    