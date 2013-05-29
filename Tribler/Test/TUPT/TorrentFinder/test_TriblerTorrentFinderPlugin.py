import unittest
import os

from Tribler.PluginManager.PluginManager import PluginManager
from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.Movie import Movie

class TestTriblerTorrentFinderPlugin(unittest.TestCase):
    '''Test class to test TriblerTorrentFinderPlugin'''

    def getTriblerPlugin(self, plugins):
        for plugin in plugins:
            if plugin.__class__.__name__ == "TriblerTorrentFinderPlugin":
                return plugin

    def test_ImportPlugin(self):
        '''Test if the plugin can be correctly imported using Yapsy.'''
        #Act
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("TorrentFinder", ITorrentFinderPlugin)
        pluginmanager.LoadPlugins()
        plugins = pluginmanager.GetPluginsForCategory("TorrentFinder")
        #Assert
        assert len(plugins) > 0

    def test_LoadTorrentList(self):
        '''Test if a list of torrent definitions can be retrieved.'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix', 'releaseYear':'1999'}
        #Act
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("TorrentFinder", ITorrentFinderPlugin)
        pluginmanager.LoadPlugins()
        plugin = self.getTriblerPlugin(pluginmanager.GetPluginsForCategory("TorrentFinder"))
        #Load a torrent
        torrentDefs = plugin.GetTorrentDefsForMovie(movie)
        
        assert len(torrentDefs) > 0
        
    def test_LoadTorrent(self):
        '''Test if a list of torrent definitions can be retrieved.'''
        #Arrange
        movie = Movie()
        movie.dictionary = {'title':'The Matrix', 'releaseYear':'1999'}
        #Act
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("TorrentFinder", ITorrentFinderPlugin)
        pluginmanager.LoadPlugins()
        plugin = self.getTriblerPlugin(pluginmanager.GetPluginsForCategory("TorrentFinder"))
        #Load a torrent
        torrentDefs = plugin.GetTorrentDefsForMovie(movie)
        torrentDef = torrentDefs[0]
        
        assert torrentDef.GetSeeders() is not None
        assert torrentDef.GetLeechers() is not None
        assert torrentDef.IsHighDef() is not None
        assert torrentDef.GetMovieDescriptor() == movie
        assert torrentDef.GetTorrentName() is not None
        assert torrentDef.GetTorrentURL() is not None
        assert torrentDef.GetTorrentProviderName() is not None
        
if __name__ == '__main__':
    unittest.main()