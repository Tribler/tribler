import sys

from Tribler.PluginManager.PluginManager import PluginManager
from Tribler.TUPT.SortedTorrentList import SortedTorrentList

class TorrentFinderControl:
    """TorrentFinderControl
        Queries installed plugins for torrents with a specific
        movie title and then sorts them.
    """
    
    __torrentDefList = None
    
    def __init__(self):
        self.__torrentDefList = SortedTorrentList()
    
    def FindTorrents(self, movie):
        """Query plug-ins for a title using a Movie object. The results will be stored in the lists.
        """
        manager = PluginManager.GetInstance()
        plugins = manager.GetPluginsForCategory('TorrentFinder')
        for plugin in plugins:
            list = plugin.GetTorrentDefsForMovie(movie)
            for item in list:
                self.__ProcessTorrentDef(item)    
    
    def __ProcessTorrentDef(self, definition):
        """Inspect a returned torrent definition and place it in our list if appropriate
        """
        if not isinstance(definition, IMovieTorrentDef):
            print sys.stderr, "TorrentFinderControl error: returned torrent definition is not of type IMovieTorrentDef"
            return
        if definition.IsHighDef():
            self.__torrentDefList.Insert(definition)

    def GetTorrentList(self):
        """Returns the list of found torrents
        """
        return self.__torrentDefList.GetList()
