#!/usr/bin/python2.7

import urllib

class Webpage:
    """Webpage:
        Allows you to download a webpage from a URL and then
        modify its contents.
    """
    
    __url = ""          # URL we represent
    __content = ""      # Raw webpage content
    
    def __init__(self, url="http://www.google.com/"):
        self.__url = url
        
    def download(self):
        """Downloads the webpage pointed to by our url to memory
        """
        webpage = None

        webpage = urllib.urlopen(self.__url)
        self.__content = webpage.read()
        webpage.close()
        
    def getContent(self):
        """Returns the webpage content as it exists in memory
        """
        return self.__content
    
    def writeContent(self, content):
        """Writes new webpage content to our memory
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
        """Saves the webpage in memory to disk
        """
        file = open(filename,'wb')
        file.write(self.__content)
        file.close()