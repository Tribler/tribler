import unittest
import os

from Tribler.PluginManager.PluginManager import PluginManager
from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin
from Tribler.TUPT.Movie import Movie

class TestTheMovieDBMatcherPlugin(unittest.TestCase):
    '''Test class to test TheMovieDBMatcherPlugin'''

    def getTMDBPlugin(self, plugins):
        for plugin in plugins:
            if plugin.__class__.__name__ == "TheMovieDBMatcherPlugin":
                return plugin

    def test_ImportPlugin(self):
        '''Test if the plugin can be correctly imported using Yapsy.'''
        #Act
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        pluginmanager.LoadPlugins()
        plugins = pluginmanager.GetPluginsForCategory("Matcher")
        #Assert
        assert len(plugins) > 0

    def test_FindResults(self):
        '''Test if the plugin can find a movie result set.'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix'}
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        pluginmanager.LoadPlugins()
        plugins = pluginmanager.GetPluginsForCategory("Matcher")
        plugin = self.getTMDBPlugin(plugins)
        #Parse a page
        plugin.MatchMovie(movie)
        attributes = plugin.GetMovieAttributes()
        #Assert minimum movie requirements
        assert len(attributes) > 0
        assert 'title' in attributes
        assert 'releaseYear' in attributes
        assert 'director' in attributes
        
    def test_ParseMovie(self):
        '''Test if the plugin can correcly retrieve movie attributes'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix'}
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        pluginmanager.LoadPlugins()
        plugins = pluginmanager.GetPluginsForCategory("Matcher")
        plugin = self.getTMDBPlugin(plugins)
        #Parse a page
        plugin.MatchMovie(movie)
        attributes = plugin.GetMovieAttributes()
        #Assert correct movie attributes
        assert plugin.GetAttribute('title') == "The Matrix"
        assert plugin.GetAttribute('releaseYear') == 1999
        assert plugin.GetAttribute('director') == "Andy Wachowski"

        
if __name__ == '__main__':
    unittest.main()