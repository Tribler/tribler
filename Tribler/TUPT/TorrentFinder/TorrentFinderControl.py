import sys

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
    
    def HasTorrent(self):
        return self.HasHDTorrent() or self.HasSDTorrent()
    
    def HasHDTorrent(self):
        """Return if a HD torrent was found."""
        return len(self.__hdTorrentDefList.GetList())
    
    def HasSDTorrent(self):
        """Return if a HD torrent was found."""
        return len(self.__sdTorrentDefList.GetList())