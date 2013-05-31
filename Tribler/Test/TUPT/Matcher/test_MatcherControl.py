import unittest
import os

from Tribler.PluginManager.PluginManager import PluginManager

from Tribler.TUPT.Matcher.MatcherControl import MatcherControl
from Tribler.TUPT.Matcher.IMatcherPlugin import IMatcherPlugin
from Tribler.TUPT.Movie import Movie

class TestMatcherControl(unittest.TestCase):
    '''Test class to test MatcherControl'''

    def test_MatchMovie1(self):
        '''Test if we can fill in movie details'''
        #Arrange
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        pluginmanager.LoadPlugins()
        #Create the controller
        control = MatcherControl(pluginmanager)
        partialMovie = Movie()
        partialMovie.dictionary = {'title':'Matrix'}
        #Act
        goodMovie = control.CorrectMovie(partialMovie)
        #Assert
        assert goodMovie.dictionary['title'] == "The Matrix"
        assert goodMovie.dictionary['releaseYear'] == 1999
        assert goodMovie.dictionary['director'] == "Andy Wachowski"
        
    def test_MatchMovie2(self):
        '''Test if we can fill in movie details'''
        #Arrange
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        pluginmanager.RegisterCategory("Matcher", IMatcherPlugin)
        pluginmanager.LoadPlugins()
        #Create the controller
        control = MatcherControl(pluginmanager)
        partialMovie = Movie()
        partialMovie.dictionary = {'title':'The Wolverine'}
        #Act
        goodMovie = control.CorrectMovie(partialMovie)
        #Assert
        assert goodMovie.dictionary['title'] == "The Wolverine"
        assert goodMovie.dictionary['releaseYear'] == 2013
        assert goodMovie.dictionary['director'] == "James Mangold"


 
if __name__ == '__main__':
    unittest.main()