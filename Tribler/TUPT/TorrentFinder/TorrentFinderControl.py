import sys
import os
import ConfigParser

from threading import Thread

from Tribler.PluginManager.PluginManager import PluginManager

from Tribler.TUPT.TorrentFinder.SortedTorrentList import SortedTorrentList
from Tribler.TUPT.TorrentFinder.IMovieTorrentDef import IMovieTorrentDef

class TorrentFinderControl:
    """TorrentFinderControl
        Queries installed plugins for torrents with a specific
        movie title and then sorts them.
    """
    
    __hdTorrentDefList = None
    __sdTorrentDefList = None
    
    def __init__(self, pluginManager):
        self.__hdTorrentDefList = SortedTorrentList()
        self.__sdTorrentDefList = SortedTorrentList()
        self.__pluginManager = pluginManager
        userDict = self.__LoadUserDict(pluginManager)
        self.__hdTorrentDefList.SetUserDict(userDict)
        self.__sdTorrentDefList.SetUserDict(userDict)
    
    def FindTorrents(self, movie):
        """Query plug-ins for a title using a Movie object. The results will be stored in the lists.
        """
        plugins = self.__pluginManager.GetPluginDescriptorsForCategory('TorrentFinder')
        threads = []
        for plugin_info in plugins:
            thread = TorrentFinderControl.PluginThread(self, plugin_info, movie)
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
    
    def ProcessTorrentDef(self, definition, trust):
        """Inspect a returned torrent definition and place it in our list if appropriate
        """
        if definition.IsHighDef():
            self.__hdTorrentDefList.Insert(definition, trust)
        else:
            self.__sdTorrentDefList.Insert(definition, trust)

    def GetTorrentList(self):
        """Returns the list of found torrents (hdList, sdList)
        """
        return (self.__hdTorrentDefList.GetList(), self.__sdTorrentDefList.GetList())
    
    def GetHDTorrentList(self):
        return self.__hdTorrentDefList.GetList()
    
    def GetSDTorrentList(self):
        return self.__sdTorrentDefList.GetList()
    
    def HasTorrent(self):
        return self.HasHDTorrent() or self.HasSDTorrent()
    
    def HasHDTorrent(self):
        """Return if a HD torrent was found."""
        return len(self.__hdTorrentDefList.GetList())
    
    def HasSDTorrent(self):
        """Return if a HD torrent was found."""
        return len(self.__sdTorrentDefList.GetList())
    
    def __LoadUserDict(self, pluginManager):
        """Loads quality terms from the user config file.
            If the file %APPDATA%/.Tribler/plug-ins
        """
        termFile = pluginManager.GetPluginFolder() + os.sep + 'settings.config'
        out = {}
        #If the file is unreadable, for any reason, return an empty dictionary
        parser = ConfigParser.SafeConfigParser(allow_no_value=True)
        try:
            parser.read(termFile)
        except:
            return out
        if not parser.has_section('TorrentFinderTerms'):
            return out
        #Return a dictionary of all the terms specified in the file
        i = 0
        for term in parser.options('TorrentFinderTerms'):
            out[str(i)] = term
            i += 1
        return out
    
    class PluginThread(Thread):
        """A private class for threading all the raw calls the plugins
            have to do, to get all their data.
        """
        
        parent = None   #TorrentFinderControl that made us
        trust = 0.5     #Trust level
        plugin = None   #Actual plugin
        name = ""       #Plugin name
        movie = None    #Movie object we are searching for
        
        def __init__(self, parent, plugin_info, movie):
            Thread.__init__(self)
            self.parent = parent
            self.trust = 0.5
            try:
                self.trust = plugin_info.details.getfloat("Core","Trust")
            except:
                self.trust = 0.5 #Not a valid float
            self.plugin = plugin_info.plugin_object
            self.name = plugin_info.name
            self.movie = movie
                
        def run(self):
            """Collect all the torrents returned by the plugins and feed them
                to our parent.
            """
            try:
                list = self.plugin.GetTorrentDefsForMovie(self.movie)
            except Exception:
                print "Unexpected error in plugin "+ self.name +".\n"+ sys.exc_info()[0]
            print "Plugin " + self.name + " returned " + str(len(list)) + " results."
            for item in list:                
                if not isinstance(item, IMovieTorrentDef):
                    raise IllegalTorrentResultException("TorrentFinder plugin should return results of IMovieTorrentDef.")
                self.parent.ProcessTorrentDef(item, self.trust)

class IllegalTorrentResultException(Exception):
    '''Exception that should be thrown when a illegal torrentresult was found on for a movie.'''
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
    