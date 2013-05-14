#!/usr/bin/python2.7

import urllib
from xdg.Menu import __getFileName

class WebPage:
    """Webpage:
        Allows you to download a web page from a URL and then
        modify its contents.
    """
    
    __url = ""          # URL we represent
    __content = ""      # Raw web page content
    ext = ""          # Extension of the webpage
    
    def __init__(self, url='', content=''):
        self.__url = url
        self.__content = content
        
    def download(self):
        """Downloads the web page pointed to by our url to memory
        """
        webPage = None

        webPage = urllib.urlopen(self.__url)
        self.__content = webPage.read()
        webPage.close()
        
    def getContent(self):
        """Returns the web page content as it exists in memory
        """
        return self.__content
    
    def writeContent(self, content):
        """Writes new web page content to our memory
        """
        self.__content = content

    def getUrl(self):
        """Returns the URL we are pointing to
        """
        return self.__url
    
    def setUrl(self, url):
        """Sets the URL we are pointing to
            Note that this member does not download the actual page
        """
        self.__url = url
        
    def saveToFile(self):
        """Saves the web page in memory to disk
        """
        filename = self.getFileName()
        file = open(filename,'wb')
        file.write(self.__content)
        file.close()
    
    def createFromFile(self, filename):
        '''Create a web page from disk'''
        file = open(filename, 'rb')
        self.__content = file.read()
        self.__url = WebPage.getURLName(filename)
        self.__ext = '.html'
        
    def getFileName(self):
        '''Get the appropiate filename by using the given url
        Args:
            url (str): The url to be used  to creat the filename.'''
        #Remove http://www.
        result = self.__url
        if result.startswith("http://"):
            result = result[7:]
        if result.startswith('www.'):
            result = result[4:]
        #Replace all / with -
        result = ['_' if x=='/' else x for x in result]
        #Return
        return ''.join(result) + self.ext

    @staticmethod
    def getURLName(filename):
        '''Get the appropiate url by using the given filename
        Args:
            filename (str): The filename to be used  to create the url.'''
        result = filename
        #Remove the extension
        result = result[:(result.rindex('.'))]
        #Replace all _ with /
        result = ['/' if x=='_' else x for x in result]
        #Add http://www.
        result = 'http://' + 'www.'+''.join(result)
        #return
        return result
        