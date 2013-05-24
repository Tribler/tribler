MovieQuality = {'CRAP':'-360p','NORMAL':'+-720p','HIGH':'+1080p'}

class IMovieTorrentDef():
    
    def GetMovieQuality(self):
        """Returns a MovieQuality enum value that corresponds to the
            torrent's movie quality.
        """
        pass
    
    def GetMovieDescriptor(self):
        """Returns a Movie object that describes the movie (the search
            query)
        """
        pass
    
    def GetTorrentName(self):
        """Returns the name of the torrent.
            For example: '[BBC-FANSUB]birddocumentar.yv2.05Xbittorent.comX.torrent'
        """
        pass
    
    def GetTorrentURL(self):
        """Returns the torrent URL location, if we wish to download it
        """
        pass
    
    def GetTorrentProviderName(self):
        """Returns the name of the torrent's provider
            For example: Official BitTorrent Site or Torrentz.eu
        """
        pass
    