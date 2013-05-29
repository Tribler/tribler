import urllib
import urllib2
import gzip
import StringIO
import xml.dom.minidom as minidom

from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin
from Tribler.TUPT.TorrentFinder.IMovieTorrentDef import IMovieTorrentDef
from Tribler.TUPT.Movie import Movie

class KatPhMovieTorrentDef(IMovieTorrentDef):

    seeders = None          # Set in init
    leechers = None         # Set in init
    highdef = None          # Set in init
    moviedescriptor = None  # Set externally
    torrentname = None      # Set in init
    torrenturl = None       # Set in init

    def __init__(self, node):
        self.highdef = str(node.getElementsByTagName('category')[0].childNodes[0].nodeValue).find('Highres Movies') != -1
        self.seeders = int(node.getElementsByTagName('torrent:seeds')[0].childNodes[0].nodeValue)
        self.leechers = int(node.getElementsByTagName('torrent:peers')[0].childNodes[0].nodeValue)
        self.torrentname = str(node.getElementsByTagName('torrent:fileName')[0].childNodes[0].nodeValue)
        self.torrenturl = node.getElementsByTagName('enclosure')[0].getAttribute('url') 

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
        return 'kat.ph'
    

class KatPhTorrentFinderPlugin(ITorrentFinderPlugin):

    def __DecompressRss(self, content):
        f = StringIO.StringIO()
        f.write(content)
        f.seek(0)
        return gzip.GzipFile(fileobj=f).read()

    def __UrlToPageSrc(self, url):
        req = urllib2.Request(url, headers={'User-Agent':"Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"})
        opener = urllib2.build_opener()
        contents = opener.open(req)
        decoded = self.__DecompressRss(contents.read())
        return decoded

    def __ParseResultPage(self, url, movie, n=10):
        """Given a kat.ph rss result page, return the first 'n' results
            as IMovieTorrentDefs
        """
        page = self.__UrlToPageSrc(url)
        dom = minidom.parseString(page)
            
        out = []
        
        for item in dom.getElementsByTagName('item'):
            torrentDef = KatPhMovieTorrentDef(item)
            torrentDef.moviedescriptor = movie
            out.append(torrentDef)
            if len(out) == n:
                break
        return out

    def __GetQueryForMovie(self, dict):
        """Return a search query given a movie dictionary
        """
        return dict['title'] + " " + dict['releaseYear']

    def GetTorrentDefsForMovie(self, movie):
        """Receive a Movie object and return a list of matching IMovieTorrentDefs
        """
        resultUrl = 'http://kat.ph/usearch/' + self.__GetQueryForMovie(movie.dictionary) + '/?rss=1&field=seeders&sorder=desc'
        return self.__ParseResultPage(resultUrl, movie)