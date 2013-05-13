#!/usr/bin/python2.7

import urllib

class WebPage:
    """Webpage:
        Allows you to download a web page from a URL and then
        modify its contents.
    """
    
    __url = ""          # URL we represent
    __content = ""      # Raw web page content
    
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
        
    def saveToFile(self, filename):
        """Saves the web page in memory to disk
        """
        file = open(filename,'wb')
        file.write(self.__content)
        file.close()