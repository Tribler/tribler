import threading

from binascii import hexlify 

from Tribler.Core.Search.SearchManager import SearchManager
from Tribler.Core.Session import Session
from Tribler.Core.Session import NTFY_TORRENTS

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.TorrentFinder.IMovieTorrentDef import IMovieTorrentDef
from Tribler.TUPT.Movie import Movie

class TriblerMovieTorrentDef(IMovieTorrentDef):

    seeders = None          # Set in init
    leechers = None         # Set in init
    highdef = None          # Set in init
    moviedescriptor = None  # Set externally
    torrentname = None      # Set in init
    torrenturl = None       # Set externally

    def __init__(self, torrent):
        self.seeders = torrent['num_seeders'] or 0
        self.leechers = torrent['num_leechers'] or 0
        self.highdef = str(torrent['name']).find('HD') != -1 or str(torrent['name']).find('1080p') != -1
        self.torrentname = torrent['name']

    def GetSeeders(self):
        return self.seeders

    def GetLeechers(self):
        return self.leechers

    def IsHighDef(self):
        return self.highdef

    def GetMovieDescriptor(self):
        return self.moviedescriptor

    def GetTorrentName(self):
        return self.torrentname

    def GetTorrentURL(self):
        return self.torrenturl

    def GetTorrentProviderName(self):
        return 'Tribler'

class TriblerTorrentFinderPlugin(ITorrentFinderPlugin):
    
    def __GetQueryForMovie(self, dict):
        """Return a search query given a movie dictionary
            Note that a Tribler search query is a list of keywords
        """
        return [dict['title'], str(dict['releaseYear'])]
    
    def GetTorrentDefsForMovie(self, movie):
        """Receive a Movie object and return a list of matching IMovieTorrentDefs
        """
        #Perform search
        session = Session.get_instance()
        torrentdb = session.open_dbhandler(NTFY_TORRENTS)
        hits = torrentdb.searchNames(self.__GetQueryForMovie(movie.dictionary), keys = ['infohash', 'torrent_file_name', 'category_id', 'num_seeders', 'num_leechers'], doSort = False)
        #Add torrents 
        torrents = []
        for hit in hits:
            torrent = torrentdb.getTorrent(hit[0])
            torrentDef = TriblerMovieTorrentDef(torrent)
            torrentDef.moviedescriptor = movie
            #Construct a magnetlink from the returned infohash
            magnetlink = "magnet:?xt=urn:btih:"+hexlify(hit[0])
            torrentDef.torrenturl = magnetlink
            #Finally add the torrentDef as a result
            torrents.append(torrentDef)
            if len(torrents) == 10:
                break 
        session.close_dbhandler(torrentdb)
        return torrents