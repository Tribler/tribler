class IMovieTorrentDef():
    
    def GetSeeders(self):
        """Return the amount of seeders for the torrent
        """
        pass
    
    def GetLeechers(self):
        """Return the amount of leechers for the torrent
        """
        pass
    
    def IsHighDef(self):
        """Return True if a movie is High Definition
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
    