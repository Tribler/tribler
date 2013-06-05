import unittest
from Tribler.TUPT.Parser.IMDbParserPlugin import IMDbParserPlugin
from Tribler.TUPT.Parser.IParserPlugin import IParserPlugin
from Tribler.PluginManager.PluginManager import PluginManager
import os
import urllib2

class TestIMDbParserPlugin(unittest.TestCase):
    '''Test class to test the IMDbParserPlugin.'''
    
    __result = {'title' : 'The Matrix', 'releaseYear' : 1999, 'director' : ['Andy Wachowski', 'Lana Wachowski']}

    def download_webpage(self, url, filename):
        """Download a webpage pointed to by 'url' to the file 'filename' using
            the Mozilla 5.0 header.
        """
        if not os.path.exists(filename):
            req = urllib2.Request(url, headers={'User-Agent':"Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"})
            file = open(filename, 'w')
            html  = urllib2.urlopen(req).read()
            file.write(html)
            file.close()
            return html

    def test_ParseWebsiteCombinedDetails(self):
        '''Test parsing the combined details page'''
        #Arrange
        url = 'http://www.imdb.com/title/tt0133093/fullcredits?ref_=tt_cl_sm#cast'
        html = self.download_webpage(url, 'test_ParseWebsiteCombinedDetails.html')
        if not html:
            file = open('test_ParseWebsiteCombinedDetails.html','r')
            html = file.read()
        parser = IMDbParserPlugin()
        #Act
        result = parser.ParseWebSite(url,html)[0]
        #Assert        
        self.__AssertResult(result)
        
    def test_ParseEmptyWebsite(self):
        '''Parse a page that has the correct netloc, but no movie.
        This should result in no movies being returned'''
        #Arrange
        url = 'http://www.imdb.com/'
        html = self.download_webpage(url, 'test_ParseEmptyWebsite.html')
        if not html:
            file = open('test_ParseEmptyWebsite.html','r')        
            html = file.read()
        parser = IMDbParserPlugin()
        #Act
        result = parser.ParseWebSite(url,html)
        #Assert
        assert len(result)==0
    
    def test_ParseWebsiteMainPage(self):
        '''Test parsing the main details page'''
        #Arrange
        url = 'http://www.imdb.com/title/tt0133093/'
        html = self.download_webpage(url, 'test_ParseWebsiteMainPage.html')
        if not html:
            file = open('test_ParseWebsiteMainPage.html','r')        
            html = file.read()
        parser = IMDbParserPlugin()
        #Act
        result = parser.ParseWebSite(url, html)[0]
        #Assert
        self.__AssertResult(result)
        
    def test_ImportPlugin(self):
        '''Test if the plugin can be correctly imported using Yapsy.'''
        #Act
        pluginmanager = PluginManager()
        #Overwrite the path to the sourcefolder of the plugin.        
        path = os.path.realpath(os.getcwd() + os.sep + '..' + os.sep + '..' + os.sep + 'TUPT')
        pluginmanager.OverwritePluginsFolder(path)
        #Load the plugin
        pluginmanager.RegisterCategory("Parser", IParserPlugin)
        pluginmanager.LoadPlugins()
        #Assert
        plugins =  pluginmanager.GetPluginsForCategory('Parser')
        result = False
        for plugin in plugins:
            if plugin.__class__.__name__ == 'IMDbParserPlugin':
                result = True
        self.assertTrue(result)

    def __AssertResult(self, result):
       '''Asserts the result for the parser'''
       for key in self.__result:
           self.assertEqual(self.__result[key], result.dictionary[key])

    
    