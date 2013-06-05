from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie
from Tribler.TUPT.TorrentFinder.IMovieTorrentDef import IMovieTorrentDef
from Tribler.TUPT.TorrentFinder.ITorrentFinderPlugin import ITorrentFinderPlugin

class PluginManagerStub():
    
    def __init__(self, parseResult = True):
        self.parserPlugins = [ParserPluginStub(parseResult), ParserPluginStubIllegalResult(None)]
        self.torrentFinderPlugins = [TorrentFinderPluginStub()]
            
    def GetPluginDescriptorsForCategory(self, category):
        if category == 'Parser':
            return self.parserPlugins
        elif category == 'TorrentFinder':
            return self.torrentFinderPlugins
        return []
    
    def GetPluginFolder(self):
        return "NaN"
    
class ParserPluginStub(IParserPlugin):
    
    def __init__(self, result):
        #This will create a plugin following Yapsi standards.
        self.plugin_object = self
        self.details = PluginDetailsStub()
        self.result = result
        self.name = "ParserPluginStub"
    
    def ParseWebSite(self, url, html):
        '''Parse a website and return a list of movies.'''
        if self.result:
            movie = Movie()
            movie.dictionary['title'] = 'TestMovie'
            return [movie]
        else:
            return None
    
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return ['www.something.com']

class ParserPluginStubIllegalResult(ParserPluginStub):

    def ParseWebSite(self, url, html):
        '''Parse a website and return a list of movies.'''
        return ['IllegalType']
        
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return ['www.illegalparseresultException.com']

class PluginDetailsStub():

    def getfloat(self, section, option):
        return 1.0
    
class TorrentFinderPluginStub(ITorrentFinderPlugin):
    
    name = 'TestTorrentFinder'
    
    def __init__(self):
        #This will create a plugin following Yapsi standards.
        self.plugin_object = self
        self.details = PluginDetailsStub()
        
    def GetTorrentDefsForMovie(self, movie):
        return [TorrentDefStub(True, movie), TorrentDefStub(False, movie)]
        
class TorrentDefStub(IMovieTorrentDef):

    seeders = 5          # Set in init
    leechers = 5         # Set in init
    highdef = None          # Set in init
    torrentname = 'Test'      # Set in init
    torrenturl = 'Test'       # Set in init
    movieDescriptor = None
    
    def __init__(self, highdef, movieDescriptor):
        self.highdef = highdef   
        self.movieDescriptor = movieDescriptor
    
    def GetSeeders(self):
        return self.seeders
    
    def GetLeechers(self):
        return self.leechers
    
    def IsHighDef(self):
        return self.highdef
    
    def GetMovieDescriptor(self):
        return self.movieDescriptor
    def GetTorrentName(self):
        return self.torrentname
    
    def GetTorrentURL(self):
        return self.torrenturl
    
    def GetTorrentProviderName(self):
        return 'kat.ph'