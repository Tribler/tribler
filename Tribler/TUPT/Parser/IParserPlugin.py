class IParserPlugin(object):
    
    def ParseWebSite(self, html):
        '''Parse a website and return a list of movies.
        Throws:
            NoResultFound : if no result was found.
        '''
        pass
    
    def GetParseableSites(self):
        '''Returns a list of parsable urls'''
        return []