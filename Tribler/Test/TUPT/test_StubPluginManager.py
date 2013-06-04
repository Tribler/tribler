from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie

class PluginManagerStub():
    
    def __init__(self, parseResult):
        self.parserPlugins = [ParserPluginStub(parseResult), ParserPluginStubIllegalResult()]
            
    def GetPluginDescriptorsForCategory(self, category):
        if category == 'Parser':
            return self.parserPlugins
        return []
    
class ParserPluginStub(IParserPlugin):
    
    def __init__(self, result):
        #This will create a plugin following Yapsi standards.
        self.plugin_object = self
        self.details = PluginDetailsStub()
        self.result = result
    
    def ParseWebSite(self, html):
        '''Parse a website and return a list of movies.'''
        if self.result:
            movie = Movie()
            movie.dictionary['title'] = 'TestMovie'
            return movie
        else:
            return None
    
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return ['something.com']

class ParserPluginStubIllegalResult(IParserPlugin):
    
    def __init__(self):
        #This will create a plugin following Yapsi standards.
        self.plugin_object = self
        self.details = PluginDetailsStub()
        
    def ParseWebSite(self, html):
        '''Parse a website and return a list of movies.'''
        return 'IllegalType'
        
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return ['illegalparseresultException.com']

class PluginDetailsStub():

    def getfloat(self, section, option):
        return 1.0