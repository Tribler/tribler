import unittest

from Tribler.TUPT.Parser.ParserControl import ParserControl
from Tribler.TUPT.Parser.ParserControl import IllegalParseResultException
from Tribler.TUPT.Parser.ParserControl import NoParserFoundException
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.TUPT.Movie import Movie

from Tribler.Test.TUPT.Parser.ParserStubs import ParserPluginManagerStub

class TestParserControl(unittest.TestCase):
    '''Test class to test the ParserControl.'''
    
    def test_HasParser_NoPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = False))
        #Act
        result = parserControl.HasParser("http://www.url.com/blabla")
        #Assert
        self.assertFalse(result)
        
    def test_HasParser_HasPlugin(self):
        '''Test to HasParser when it has No Plugin. Should return false'''
        #Arrange        
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = False))
        #Act
        result = parserControl.HasParser("http://www.something.com/blabla/")
        #Assert
        self.assertTrue(result)       
        
    def test_ParseWebsite_NoResult(self):
        '''Test ParseWebsite and no result is found'''
        #Arrange
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = False))
        #Act
        result = parserControl.ParseWebsite("http://www.something.com", 'NaN')
        #Assert
        self.assertEqual(None, result[0])
    
    def test_ParseWebsite_Result(self):
        '''Test ParseWebsite and a result is found'''
        #Arrange
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = True))
        #Act
        result = parserControl.ParseWebsite("http://www.something.com", 'NaN')
        #Assert
        self.assertEqual('TestMovie', result[0][0].dictionary['title'])
        
    def test_ParseWebsite_IllegalParseResult(self):
        """Test ParseWebsite returning a result not of type movie."""
        #Arrange
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = True))
        #Act
        with self.assertRaises(IllegalParseResultException):
            result = parserControl.ParseWebsite("http://www.illegalparseresultException.com/blabla", 'NaN')
        #Assert        
    
    def test_ParseWebsite_NoParserFoundException(self):
        '''Test ParseWebsite to throw an exception when no parser is available'''
        #Arrange
        parserControl = ParserControl(ParserPluginManagerStub(parseResult = True))
        #Act and Assert
        with self.assertRaises(NoParserFoundException):
            parserControl.ParseWebsite("http://www.url.com/blabla", 'NaN')
    
if __name__ == '__main__':
    unittest.main()
    
    