import sys

from Tribler.PluginManager.PluginManager import PluginManager

class TorrentFinderControl:
    """TorrentFinderControl
        Queries installed plugins for torrents with a specific
        movie title. These torrents are then sorted in 3 categories:
        
         - 360p or less Category (Crap quality)
         - 720p Category (Normal quality)
         - 1080p or more Category (High quality)
    """
    
    __crapQList = []
    __normalQList = []
    __highQList = []
    
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
        """Inspect a returned torrent definition and place in
            proper list.
        """
        if not isinstance(definition, IMovieTorrentDef):
            print sys.stderr, "TorrentFinderControl error: returned torrent definition is not of type IMovieTorrentDef"
            return
        quality = definition.GetMovieQuality()
        if quality == IMovieTorrentDef.MovieQuality['HIGH']:
            self.__highQList.append(definition)
        elif quality == IMovieTorrentDef.MovieQuality['NORMAL']:
            self.__normalQList.append(definition)
        else:
            #Note that any implementation supplying an unknown quality also ends up here 
            self.__crapQList.append(definition)
    
    def GetCrapQualityList(self):
        """Returns the list of found torrents with crap quality.
            Also known as the 360p or less list.
        """
        return self.__crapQList
    
    def GetNormalQualityList(self):
        """Returns the list of found torrents with normal quality.
            Also known as the 720p list.
        """
        return self.__normalQList
    
    def GetHighQualityList(self):
        """Returns the list of found torrents with high quality.
            Also known as the 1080p or more list.
        """
        return self.__highQList