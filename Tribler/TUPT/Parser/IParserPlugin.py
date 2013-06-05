class IParserPlugin(object):
    
    def ParseWebSite(self,url, html):
        '''Parse a website and return a list of movies.
        '''
        pass
    
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return []