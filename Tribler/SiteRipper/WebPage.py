#!/usr/bin/python2.7

import urllib
import os
import shutil
import Tribler.Core.Utilities.tar as tar_lib
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
        self.setUrl(url)
        self.__content = content
        
    def DownloadContent(self):
        """Downloads the web page pointed to by our url to memory
        """
        webPage = None

        webPage = urllib.urlopen(self.__url)
        self.__content = webPage.read()
        webPage.close()
        
    def addResource(self, uri):
        self.__resourceDictionary.append(uri)
    
    def getContent(self):
        """Returns the web page content as it exists in memory
        """
        return self.__content
    
    def setContent(self, content):
        """Set new web page content to our memory
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
        self.__folderName = self.getFileName(url) + os.sep
    
    def createFromFile(self, filename):
        '''Create a web page from disk'''
        file = open(filename, 'rb')
        self.__content = file.read()
        self.__url = WebPage.getURLName(filename)
        self.__ext = '.html'
        
    def tarToFile(self):
        '''Create a tar of this webppage and its resources and save it to disk.'''
        #Create a Tar file
        tar = tarfile.open(name = ''.join([self.getFileName(),'.tar.gz']), mode = 'w:gz')
        #Create a HTML File
        self.__createHTMLFile()
        #Add HTML File.
        tar.add(self.getFileName(), arcname = '')
        #Add resources
        for resource in self.__resourceDictionary:
            tar.add(resource.filePath, arcname = '')
        #Close the tar.       
        tar.close()
        
    @staticmethod
    def getFileName(url):
        '''Get the appropiate filename by using the given url
        Args:
            url (str): The url to be used  to create the filename.'''
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
    
    def GetTarName(self):
        return self.getFileName(self.__url) + '.tar.gz'
    
    def createTar(self):
        '''Create a tar file of the WebPage'''
        #Create folder
        if not os.path.exists(self.__folderName[:-1]):
            os.makedirs(self.__folderName[:-1])
        #Save content.
        self.__createHTMLFile()
        #Save Resources
        self.__DownloadResources()
        #Tar folder
        folderPath = os.path.dirname(os.path.realpath(os.path.realpath(Tribler.__file__) + os.sep + ".."))
        #Add tar to torrent
        sourcefolder = folderPath + os.sep + self.__folderName
        out = tar_lib.tarFolder(sourcefolder, folderPath, self.__folderName[:-1])
        #Cleanup sources
        self.__removeTarSourceFiles(sourcefolder + os.sep)
        #return torrent
        return out
    
    def __createHTMLFile(self):
        """Saves the web page HTML to disk"""
        fileName = self.__folderName + self.getFileName(self.__url)
        file = open(fileName,'wb')
        file.write(self.__content)
        file.close()
      
    def __DownloadResources(self):
        '''Download all resources of this WebPage.'''
        #Download resources
        for resource in self.__resourceDictionary:
            self.__DownloadResource(resource)
        
    def __DownloadResource(self, url):
        '''Downloads the resource pointed to by the url
        Args:
            url (str): URL pointing to the resource that needs to be downloaded.'''
        #Open the location
        location = urllib.urlopen(url)
        #Read the resource.
        resource = location.read()
        #Write to disk.
        file = open(self.__folderName + self.GetResourceFileName(url),'wb')
        file.write(resource)
        file.close()
        
    def __removeTarSourceFiles(self, folderpath):
        '''Remove all the files we packed earlier
        '''
        if not os.path.exists(folderpath):
            return
        shutil.rmtree(folderpath)
        