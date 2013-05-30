import sys
import os
import ConfigParser

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
        for plugin_info in plugins:
            trust = 0.5
            try:
                trust = plugin_info.getfloat("Core","Trust")
            except:
                trust = 0.5 #Not a valid float
            list = plugin_info.plugin_object.GetTorrentDefsForMovie(movie)
            print "Plugin " + plugin_info.name + " returned " + str(len(list)) + " results."
            for item in list:
                self.__ProcessTorrentDef(item, trust)    
    
    def __ProcessTorrentDef(self, definition, trust):
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
            