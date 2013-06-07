from Tribler.Test.TUPT.TUPTStubs import PluginManagerStub
from Tribler.Test.TUPT.TUPTStubs import PluginStub

from Tribler.TUPT.Movie import Movie

class ParserPluginManagerStub(PluginManagerStub):
    
    def __init__(self, parseResult = True):
        self.parserPlugins = [ParserPluginStub(parseResult), ParserPluginStubIllegalResult(None)]
            
    def GetPluginDescriptorsForCategory(self, category):
        if category == 'Parser':
            return self.parserPlugins
        return []
    
    def GetPluginFolder(self):
        return "NaN"
   
class ParserPluginStub(PluginStub):
    
    def __init__(self, result):
        #This will create a plugin following Yapsi standards.
        PluginStub.__init__(self)
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
