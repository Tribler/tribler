import threading

from binascii import hexlify

from Tribler.Main.vwxGUI.SearchGridManager import SearchGridManager

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
        self.seeders = torrent.num_seeders
        self.leechers = torrent.num_leechers
        self.highdef = str(torrent.channel.name).find('HD') != -1
        self.torrentname = torrent.torrent_file_name

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
        #Define torrent finding callback
        evt = threading.Event()
        callReturn = None
        def callback(infohash, content):
            callReturn = infohash
            evt.set()
        #Perform search
        searchMngr = SearchGridManager.getInstance()
        searchMngr.setSearchKeywords(self.__GetQueryForMovie(movie.dictionary))
        hits_info = searchMngr.getHitsInCategory()
        hits = hits_info[4]
        #Add torrents 
        torrents = []
        for torrent in hits:
            # torrent is a GuiDBTuples.Torrent
            torrentDef = TriblerMovieTorrentDef(torrent)
            searchMngr.downloadTorrentfileFromPeers(torrent, callback)
            torrentDef.moviedescriptor = movie
            #Wait for the callback to finish
            #if the eventcode is False, we didn't manage to get the torrent file 
            eventcode = callback.wait(5)
            if eventcode:
                #Construct a magnetlink from the returned infohash
                magnetlink = "magnet:?xt=urn:btih:"+hexlify(callReturn)
                torrentDef.torrenturl = magnetlink
                #Finally add the torrentDef as a result
                torrents.append(torrentDef)
        return torrents