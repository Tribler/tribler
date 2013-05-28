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
        
    def test_MatchingSort(self):
        '''Test the algorithm prioritizing better torrent name matches
            over worse name matches given there are no other 
            distinguishable differences.
        '''
        #Arrange
        wantedMovie = Movie()
        wantedMovie.dictionary = {'Title':'''Barbie's Pretty Pink Ponies'''}
        stList = SortedTorrentList()
        torrentDef1 = testMovieTorrentDef()
        torrentDef1.getMovieDescriptor = wantedMovie
        torrentDef1.getTorrentName = 'barbie pink pony'
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getMovieDescriptor = wantedMovie
        torrentDef2.getTorrentName = 'barbies pretty pink ponies'
        #Act
        stList.Insert(torrentDef1, 1)
        stList.Insert(torrentDef2, 1)
        #Assert     
        assert stList.GetList()[0] == torrentDef2
        assert stList.GetList()[1] == torrentDef1
        
    def test_UserWords(self):
        '''Test the algorithm prioritizing torrent names with special words
            over torrents without them given there are no other 
            distinguishable differences.
        '''
        #Arrange
        userDict = {'RELEASE_GROUP':'BBCRipz'}
        stList = SortedTorrentList()
        stList.SetUserDict(userDict)
        torrentDef1 = testMovieTorrentDef()
        torrentDef1.getTorrentName = '[BBCRipz]Documentary 32'
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getTorrentName = '[Whatevs]Documentary 32'
        #Act
        stList.Insert(torrentDef1, 1)
        stList.Insert(torrentDef2, 1)
        #Assert     
        assert stList.GetList()[0] == torrentDef1
        assert stList.GetList()[1] == torrentDef2
        
    def test_UserPreference(self):
        '''Test the algorithm prioritizing torrents that the user wants
            based on the releasing site. This will be enough to shift
            slight advantages one torrent may otherwise have over another.
        '''
        #Arrange
        stList = SortedTorrentList()
        torrentDef1 = testMovieTorrentDef()
        torrentDef1.getSeeders = 25         # 1.25 times as good as the other torrent
        torrentDef1.getLeechers = 0 
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getSeeders = 20
        torrentDef2.getLeechers = 0 
        #Act
        stList.Insert(torrentDef1, 0.7)     # Downgrade to 70% or 0.875 times as good
        stList.Insert(torrentDef2, 1)
        #Assert     
        assert stList.GetList()[0] == torrentDef2
        assert stList.GetList()[1] == torrentDef1
        
    def test_Complex(self):
        '''Test the algorithm prioritizing a torrent we probably want
            over one we probably don't. Note that we have 2 torrents
            where 1 is clearly 'better'.
        '''
        #Arrange
        userDict = {'RELEASE_GROUP':'BBCRipz'}
        stList = SortedTorrentList()
        stList.SetUserDict(userDict)
        torrentDef1 = testMovieTorrentDef()
        torrentDef2 = testMovieTorrentDef()
        torrentDef2.getSeeders = 850
        torrentDef2.getLeechers = 500 
        torrentDef2.getTorrentName = '[HorribleRips]Apes in space'
        #Act
        stList.Insert(torrentDef1, 0.75)
        stList.Insert(torrentDef2, 0.5)
        #Assert     
        assert stList.GetList()[0] == torrentDef1
        assert stList.GetList()[1] == torrentDef2
           
if __name__ == '__main__':
    unittest.main()
    
    