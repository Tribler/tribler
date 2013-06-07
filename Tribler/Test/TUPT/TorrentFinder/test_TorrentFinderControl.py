import unittest

from Tribler.Test.TUPT.TorrentFinder.TorrentFinderStubs import TorrentFinderPluginManagerStub
from Tribler.Test.TUPT.TorrentFinder.TorrentFinderStubs import TorrentDefStub

from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl
from Tribler.TUPT.Movie import Movie

class TestTorrentFinderControl(unittest.TestCase):
    '''Test class to test TorrentFinderControl'''
    
    def setUp(self):
        #Arrange
        self.__movie = Movie()
        self.__movie.dictionary['title'] = 'TestMovie'
        self.__torrentFinderControl = TorrentFinderControl(TorrentFinderPluginManagerStub(), self.__movie)       
     
    def test_FindTorrent_GetResults(self):      
        #Act
        self.__torrentFinderControl.FindTorrents()
        #Assert
        self.assertTrue(len(self.__torrentFinderControl.GetHDTorrentList()) > 0)
        self.assertTrue(len(self.__torrentFinderControl.GetSDTorrentList()) > 0)
        
    def test_ProcessTorrentDef_addHDDefinition(self):
        #Arrange
         torrentDef =  TorrentDefStub(True, self.__movie)
         #Act
         self.__torrentFinderControl.ProcessTorrentDef(torrentDef, 0.5)
         #Assert
         self.assertTrue(len(self.__torrentFinderControl.GetHDTorrentList()) > 0)
         self.assertEqual(0, len(self.__torrentFinderControl.GetSDTorrentList()))
         
    def test_ProcessTorrentDef_addSDDefinition(self):
        #Arrange
         torrentDef =  TorrentDefStub(False, self.__movie)
         #Act
         self.__torrentFinderControl.ProcessTorrentDef(torrentDef, 0.5)
         #Assert
         self.assertTrue(len(self.__torrentFinderControl.GetSDTorrentList()) > 0)
         self.assertEqual(0, len(self.__torrentFinderControl.GetHDTorrentList()))
    
if __name__ == '__main__':
    unittest.main()
    