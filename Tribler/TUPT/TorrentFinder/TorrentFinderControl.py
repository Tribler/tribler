
class TorrentFinderControl:
    """TorrentFinderControl
        Queries installed plugins for torrents with a specific
        movie title. These torrents are then sorted in 3 categories:
        
         - 360p or less Category (Crap quality)
         - 720p Category (Normal quality)
         - 1080p or more Category (High quality)
    """
    
    def __init__(self):
        pass
    
    def LoadLists(self, query):
        """Query plug-ins for a title 
        """
        pass
    
    def __ProcessTorrentDef(self):
        """Inspect a returned torrent definition and place in
            proper list.
        """
        pass
    
    def GetCrapQualityList(self):
        """Returns the list of found torrents with crap quality.
            Also known as the 360p or less list.
        """
        pass
    
    def GetNormalQualityList(self):
        """Returns the list of found torrents with normal quality.
            Also known as the 720p list.
        """
        pass
    
    def GetHighQualityList(self):
        """Returns the list of found torrents with high quality.
            Also known as the 1080p or more list.
        """
        pass