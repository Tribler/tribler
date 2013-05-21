import Tribler.SiteRipper.ResourceSeeder as ResourceSeeder

from Tribler.SiteRipper.TarFolderManager import TarFolderManager
from Tribler.SiteRipper.WebPage import WebPage

import os
import Tribler

class ResourceSniffer:
    """ResourceSniffer
    Class for constructing a local copy of a webpage.
    """

    __listenforfiles = False    #Determines wether we are sensitive to incoming resources
    __webPage = None            #WebPage that contains all data of the webPage.

    def __AddResourceToWebPage(self, uri):
        """Add a mapping for a resource uri
        """
        self.__webPage.AddResource(uri)

    def GetFile(self, uri):
        """Callback for when an uri is requested on a page
            Note that we may not be sensitive to these requests
            (This is to avoid javascript chucking images at us while
            we are compressing a page and breaking us)
        """
    	if self.__listenforfiles:
            self.__AddResourceToWebPage(uri)
    	
    def StartLoading(self, url, source):
        """Callback for when a page starts to get loaded
            (Resources meant to be sniffed are going to pour into
            our GetFile() member)
        """
        self.__webPage = WebPage(url, source)
        self.__listenforfiles = True  
    	
    def Seed(self):
        """Callback for when a user requests a page to be seeded.
            This will block any new resources from coming in (through
            javascript for example).
            This member is responsible for:
            1. Finalizing the dictionary (download all resources)
            2. Compressing the dictionary (tar)
            3. Sharing dictionary (torrent)
        """
        #Shut down listening for files
        self.__listenforfiles = False
        #Gather all the files referenced on the page
        tarpath, tarfile = self.__webPage.CreateTar()
        #Share tarfile
        ResourceSeeder.SeedWebpage(tarpath, self.__webPage.GetUrl())
