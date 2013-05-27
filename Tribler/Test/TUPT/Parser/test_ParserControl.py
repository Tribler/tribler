import unittest

from Tribler.TUPT.Parser.ParserControl import ParserControl
from Tribler.TUPT.Parser.ParserControl import NoParserFoundException
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie

class TestParserControl(unittest.TestCase):
    '''Test class to test the ParserControl.'''
    
    def test_HasParser_NoPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.HasParser("url.com")
        #Assert
        self.assertFalse(result)
        
    def test_HasParser_HasPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.HasParser("something.com")
        #Assert
        self.assertTrue(result)       
        
    def test_ParseWebsite_NoResult(self):
        '''Test ParseWebsite and no result is found'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(False))
        #Act
        result = parserControl.ParseWebsite("something.com", 'NaN')
        #Assert
        self.assertEqual(None, result)
    
    def test_ParseWebsite_Result(self):
        '''Test ParseWebsite and a result is found'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(True))
        #Act
        result = parserControl.ParseWebsite("something.com", 'NaN')
        #Assert
        self.assertEqual('TestMovie', result.dictionary['title'])
    
    def test_ParseWebsite_NoParserFoundException(self):
        '''Test ParseWebsite to throw an exception when no parser is available'''
        #Arrange
        parserControl = ParserControl(PluginManagerStub(True))
        #Act and Assert
        with self.assertRaises(NoParserFoundException):
            result = parserControl.ParseWebsite("url.com", 'NaN')
        
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
    
    