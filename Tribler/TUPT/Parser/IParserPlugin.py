from yapsy.IPlugin import IPlugin

class IParserPlugin(IPlugin):
    
    def ParseWebSite(self, html):
        '''Parse a website and return a list of movies.
        Throws:
            NoResultFound : if no result was found.
        '''
        pass
    
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return []

class NoResultFound(Exception):
    '''Exception that should be thrown when no result was found on a page.'''
    
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)