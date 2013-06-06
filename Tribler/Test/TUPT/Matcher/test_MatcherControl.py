import unittest
import os

from Tribler.PluginManager.PluginManager import PluginManager

from Tribler.TUPT.Matcher.MatcherControl import MatcherControl
from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin
from Tribler.TUPT.Movie import Movie

class TestMatcherControl(unittest.TestCase):
    '''Test class to test MatcherControl'''
    
    def __GetPath(self):
        return os.path.realpath(os.getcwd()  + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
    
    def setUp(self):
        #Arrange
        self.__pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = self.__GetPath()
        self.__pluginmanager.OverwritePluginsFolder(path)
        self.__pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        self.__pluginmanager.LoadPlugins()        

    def test_MatchMovie1(self):
        '''Test if we can fill in movie details'''
        #Arrange
        control = MatcherControl(self.__pluginmanager)        
        partialMovie = Movie()
        partialMovie.dictionary = {'title':'Matrix'}
        #Act
        goodMovie = control.CorrectMovie(partialMovie)
        #Assert
        self.assertEqual("The Matrix", goodMovie.dictionary['title'])
        self.assertEqual(1999, goodMovie.dictionary['releaseYear'])
        self.assertEqual("Andy Wachowski", goodMovie.dictionary['director'])
        
    def test_MatchMovie2(self):
        '''Test if we can fill in movie details'''
        #Arrange
        control = MatcherControl(self.__pluginmanager)  
        partialMovie = Movie()
        partialMovie.dictionary = {'title':'The Wolverine'}
        #Act
        goodMovie = control.CorrectMovie(partialMovie)
        #Assert
        self.assertEqual("The Wolverine", goodMovie.dictionary['title'])
        self.assertEqual(2013, goodMovie.dictionary['releaseYear'])
        self.assertEqual("James Mangold", goodMovie.dictionary['director'] )


 
if __name__ == '__main__':
    unittest.main()