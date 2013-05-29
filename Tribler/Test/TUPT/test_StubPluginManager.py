from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie

class PluginManagerStub():
    
    def __init__(self, parseResult):
        self.plugins = [PluginStub(parseResult)]
            
    def GetPluginsForCategory(self, category):
        return self.plugins
    
class PluginStub(IParserPlugin):
    
    def __init__(self, result):
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
        
if __name__ == '__main__':
    unittest.main()