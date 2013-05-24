from yapsy.IPlugin import IPlugin

class IParserPlugin(IPlugin):
    
    def ParseWebSite(self, html):
        '''Parse a website and return a list of movies.'''
        pass
    