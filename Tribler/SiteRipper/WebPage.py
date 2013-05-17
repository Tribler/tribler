#!/usr/bin/python2.7

import urllib
import os
import shutil
import Tribler.Core.Utilities.tar as tar_lib
from Tribler.Main.globals import DefaultDownloadStartupConfig
import hashlib

import Tribler


class WebPage:
    """Webpage:
        Allows you to download a web page from a URL and then
        modify its contents. It stores the URL,HTML source and resources.
    """
    
    __url = ''          # URL we represent
    __content = ''      # Raw web page content
    ext = ''          # Extension of the webpage
    __resourceDictionary = []
    __folderName = ''
    
    def __init__(self, url='', content=''):
        self.SetUrl(url)
        self.__content = content
        
    def DownloadContent(self):
        """Downloads the web page pointed to by our url to memory
        """
        webPage = None

        webPage = urllib.urlopen(self.__url)
        self.__content = webPage.read()
        webPage.close()
        
    def AddResource(self, uri):
        self.__resourceDictionary.append(uri)
    
    def GetContent(self):
        """Returns the web page content as it exists in memory
        """
        return self.__content
    
    def SetContent(self, content):
        """Set new web page content to our memory
        """
        self.__content = content

    def GetUrl(self):
        """Returns the URL we are pointing to
        """
        return self.__url
    
    def SetUrl(self, url):
        """Sets the URL we are pointing to
            Note that this member does not download the actual page
        """
        self.__url = url
        self.__folderName = self.GetFileName(url) + os.sep
    
    def CreateFromFile(self, filename):
        """Create a web page from disk"""
        file = open(filename, 'rb')
        self.__content = file.read()
        self.__url = WebPage.GetURLName(filename)
        self.__ext = '.html'
        
    @staticmethod
    def GetFileName(url):
        """Get the appropiate filename by using the given url
        Args:
            url (str): The url to be used  to create the filename."""
        #Remove http://www.
        result = url
        if result.startswith("http://"):
            result = result[7:]
        if result.startswith('www.'):
            result = result[4:]
        #Replace all / with -
        result = ['_' if x=='/' else x for x in result]
        #Return
        return ''.join(result) 

    @staticmethod
    def GetResourceFileName(url):
        """Get the appropiate resourcename by hashing the given url.
        Args:
            url (str): The url to be used  to create the filename."""
        hasher = hashlib.md5()
        hasher.update(url)
        return hasher.hexdigest()
        
    @staticmethod
    def GetURLName(filename):
        """Get the appropiate url by using the given filename
        Args:
            filename (str): The filename to be used  to create the url."""
        result = filename
        #Remove the extension
        result = result[:(result.rindex('.'))]
        #Replace all _ with /
        result = ['/' if x=='_' else x for x in result]
        #Add http://www.
        result = 'http://' + 'www.'+''.join(result)
        #return
        return result   
    
    def GetTarName(self):
        return self.GetFileName(self.__url) + '.tar.gz'
    
    def CreateTar(self):
        """Create a tar file of the WebPage"""
        #Create folder
        folderPath = self.__GetDownloadsPath()
        if not os.path.exists(folderPath + os.sep + self.__folderName[:-1]):
            os.makedirs(folderPath + os.sep + self.__folderName[:-1])
        #Save content.
        self.__CreateHTMLFile()
        #Save Resources
        self.__DownloadResources()
        #Add tar to torrent
        sourcefolder = folderPath + os.sep + self.__folderName
        out = tar_lib.tarFolder(sourcefolder, folderPath, self.__folderName[:-1])
        #Cleanup sources
        self.__RemoveTarSourceFiles(sourcefolder + os.sep)
        #return torrent
        return out
    
    def __CreateHTMLFile(self):
        """Saves the web page HTML to disk"""
        fileName = self.__GetDownloadsPath() + os.sep + self.__folderName + self.GetFileName(self.__url)
        file = open(fileName,'wb')
        file.write(self.__content)
        file.close()
      
    def __DownloadResources(self):
        """Download all resources of this WebPage."""
        #Download resources
        for resource in self.__resourceDictionary:
            self.__DownloadResource(resource)
        
    def __DownloadResource(self, url):
        """Downloads the resource pointed to by the url
        Args:
            url (str): URL pointing to the resource that needs to be downloaded."""
        #Open the location
        location = urllib.urlopen(url)
        #Read the resource.
        resource = location.read()
        #Write to disk.
        file = open(self.__GetDownloadsPath() + os.sep + self.__folderName + self.GetResourceFileName(url),'wb')
        file.write(resource)
        file.close()
    
    def __GetDownloadsPath(self):
        """Get the path to the Downloads."""
        config = DefaultDownloadStartupConfig.getInstance()
        folderPath = config.get_dest_dir() + os.sep + "EternalWebpages"
        self.__AssertFolder(folderPath)
        return folderPath
    
    def __AssertFolder(self, folderpath):
        """Assert that the folder exists. If it does not, then the folder is created"""
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)
    
    def __RemoveTarSourceFiles(self, folderpath):
        """Remove all the files we packed earlier
        """
        if not os.path.exists(folderpath):
            return
        shutil.rmtree(folderpath)
        