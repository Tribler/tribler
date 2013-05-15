import Tribler.SiteRipper.ResourceSeeder as ResourceSeeder

from Tribler.SiteRipper.TarFolderManager import TarFolderManager

class ResourceSniffer:
    '''ResourceSniffer
    Class for constructing a local copy of a webpage.
    '''

    __listenforfiles = False    #Determines wether we are sensitive to incoming resources
    __dictionary = None         #Our dictionary for url to file path mapping

    def __init__(self):
        self.__dictionary = None # TODO

    def AddFileToDictionary(self, uri):
        '''Call the dictionary to add a mapping for a resource uri
        '''
        #self.__dictionary.AddMapping(uri)

    def GetFile(self, uri):
        '''Callback for when an uri is requested on a page
            Note that we may not be sensitive to these requests
            (This is to avoid javascript chucking images at us while
            we are compressing a page and breaking us)
        '''
    	if self.__listenforfiles:
            self.AddFileToDictionary(uri)
    	
    def StartLoading(self, url):
        '''Callback for when a page starts to get loaded
            (Resources meant to be sniffed are going to pour into
            our GetFile() member)
        '''
        self.__listenforfiles = True
        #self.__dictionary.Initialize(url)
    	
    def Seed(self):
        '''Callback for when a user requests a page to be seeded.
            This will block any new resources from coming in (through
            javascript for example).
            This member is responsible for:
            1. Finalizing the dictionary (download all resources)
            2. Compressing the dictionary (tar)
            3. Sharing dictionary (torrent)
        '''
        #Shut down listening for files
        self.__listenforfiles = False
        #Gather all the files referenced on the page
        self.__dictionary.DownloadFiles()
        #Get local file details from the dictionary
        folder = self.__dictionary.GetFolder()
        archivename = self.__dictionary.GetFolderName()
        #Compress files
        foldermngr = TarFolderManager(archivename)
        tarfile = foldermngr.tarFromFolder(folder)
        #Share tarfile
        ResourceSeeder.seedFile(tarfile)
        print "STUB"