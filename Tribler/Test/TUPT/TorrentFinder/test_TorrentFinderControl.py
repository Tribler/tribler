import unittest

from Tribler.Test.TUPT.test_StubPluginManager import PluginManagerStub
from Tribler.Test.TUPT.test_StubPluginManager import TorrentDefStub

from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl
from Tribler.TUPT.Movie import Movie

class TestTorrentFinderControl(unittest.TestCase):
    '''Test class to test TorrentFinderControl'''
    
    def setUp(self):
        #Arrange
        self.__torrentFinderControl = TorrentFinderControl(PluginManagerStub())
        self.__movie = Movie()
        self.__movie.dictionary['title'] = 'TestMovie'
     
    def test_FindTorrent_GetResults(self):      
        #Act
        self.__torrentFinderControl.FindTorrents(self.__movie)
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
    