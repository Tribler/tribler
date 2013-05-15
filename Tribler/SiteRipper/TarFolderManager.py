import os
import shutil

import Tribler
import Tribler.Core.Utilities.tar as tar_lib

class TarFolderManager:
    '''TarFolderManager
        Class for managing tar archives and their respective
        sources.
        Note that this class does not provide methods to remove
        the resulting .tar files, because this should be done
        through the accompanying Torrent file.
    '''    
    
    # The folder (with path separator suffix) we will be placing our tar files in
    TARFOLDER = os.path.dirname(os.path.realpath(os.path.realpath(Tribler.__file__) + os.sep + "..")) + os.sep + "tar-files" + os.sep
    
    __folder = ""               # TARFOLDER/archivename
    __archivename = ""          # archivename
    
    def __init__(self, archivename):
        '''Initialize a Tar-file with a certain identifying name
        For example 'http___www_google_com_'
        '''
        self.__folder = TarFolderManager.TARFOLDER + archivename
        self.__archivename = archivename
        
    def tarFromFolder(self, path):
        '''Create a tar file in our standard tar file folder for a certain folder
            Returns the path to the created tar file
        '''
        if not os.path.exists(TarFolderManager.TARFOLDER):
            os.mkdir(TarFolderManager.TARFOLDER)
        if not os.path.exists(self.__folder):
            os.mkdir(self.__folder)
        return tar_lib.tarFolder(path, TarFolderManager.TARFOLDER, self.__archivename)
        
    def untarArchive(self):
        '''Unpack the tar file we are associated with.
            Returns the folder with the unpacked files
        '''
        if not os.path.exists(TarFolderManager.TARFOLDER):
            os.mkdir(TarFolderManager.TARFOLDER)
        tar_lib.untarFolder(self.__folder + ".tar.gz", TarFolderManager.TARFOLDER, self.__archivename)
        return self.__folder
        
    def removeUnpackedFiles(self):
        '''Remove all the files we unpacked earlier with untarArchive()
        '''
        if os.path.exists(self.__folder):
            return
        shutil.rmtree(self.__folder + os.sep)
        
        