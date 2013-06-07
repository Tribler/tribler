import unittest
import os

from Tribler.PluginManager.PluginManager import PluginManager
from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin
from Tribler.TUPT.Movie import Movie

class TestTheMovieDBMatcherPlugin(unittest.TestCase):
    '''Test class to test TheMovieDBMatcherPlugin'''
    
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
        plugins = self.__pluginmanager.GetPluginsForCategory("Matcher")
        self.__plugin = self.__GetTMDBPlugin(plugins)        

    def __GetTMDBPlugin(self, plugins):
        for plugin in plugins:
            if plugin.__class__.__name__ == "TheMovieDBMatcherPlugin":
                return plugin

    def test_ImportPlugin(self):
        '''Test if the plugin can be correctly imported using Yapsy.'''
        #Act is done in setUp.
        plugins = self.__pluginmanager.GetPluginsForCategory("Matcher")
        #Assert
        self.assertTrue(len(plugins) > 0)

    def test_FindResults(self):
        '''Test if the plugin can find a movie result set.'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix'}
        #Act
        self.__plugin.MatchMovie(movie)
        attributes = self.__plugin.GetMovieAttributes()
        #Assert minimum movie requirements
        self.assertTrue(len(attributes) > 0)
        self.assertTrue('title' in attributes)
        self.assertTrue('releaseYear' in attributes)
        self.assertTrue('director' in attributes)
        
    def test_ParseMovie(self):
        '''Test if the plugin can correcly retrieve movie attributes'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix'}
        #Parse a page
        self.__plugin.MatchMovie(movie)
        attributes = self.__plugin.GetMovieAttributes()
        #Assert correct movie attributes
        self.assertEqual("The Matrix", self.__plugin.GetAttribute('title'))
        self.assertEqual(1999, self.__plugin.GetAttribute('releaseYear'))
        self.assertEqual("Andy Wachowski", self.__plugin.GetAttribute('director'))

        
if __name__ == '__main__':
    unittest.main()