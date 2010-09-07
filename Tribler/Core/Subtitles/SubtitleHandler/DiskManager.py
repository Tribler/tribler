# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import \
    DiskManagerException
from Tribler.Core.osutils import getfreespace
from random import random
from traceback import print_exc
import codecs
import os
import sys

DISK_FULL_REJECT_WRITES = 0x0
DISK_FULL_DELETE_SOME = 0x1

DELETE_RANDOM = 0x02
DELETE_OLDEST_FIRST = 0x0
DELETE_NEWEST_FIRST = 0x4

MINIMUM_FILE_SIZE = 4 #KBs. most common.


DEFAULT_CONFIG = { "maxDiskUsage" :-1 , #infinity
                   "diskPolicy" : DISK_FULL_REJECT_WRITES,
                   "encoding" : "utf-8"}

DEBUG = False

class DiskManager(object):
    """
    Manages disk policies.
    
    Used for subtitle disk space handling it could be adapted
    for any space management. The current implementation is
    NOT THREAD-SAFE
    
    The disk manager is a central resource manager for disk space. 
    A client object who wants to use the disk manager has to register to
    it using the registerDir method. After that that client will be
    associated to a directory where the disk manager will try to store
    files for it.
    
    A DiskManager has a _minFreeSpace attribute that determines how much
    space has to be always left free on the disk. It will perform no writes
    if that write will make free space go under the _minFreeSpace threshold.
    
    When a client registers it must provided some configuration parameters.
    This parameters comprehend maxDiskUsage that is the maximum disk quota
    that can be used by that client, diskPolicy that is a bitmask specifying
    the actions to do when the disk quota has been reached and a write
    operation is asked, adn encoding that is the default encoding for every
    file read or write.
    
    THIS CLASS IS NOT THREAD-SAFE!!!!
    """
    
    def __init__(self, minFreeSpace=0, baseDir="."):
        """
        Create a new instance of DiskManager.
        
        @type minFreeSpace: int
        @param minFreeSpace: the minimum amount of free space in KBs that
            needs to be always available on disk after any
            write operation
        @type baseDir: str
        @param baseDir: a path. It will be used by the manager to determine
            which disk he has to use to calculate free space and
            so.
        """
        assert os.path.isdir(baseDir)
        self._minFreeSpace = minFreeSpace
        self._registeredDirs = dict()
        self._baseDir = baseDir
        
    def registerDir(self, directory, config=None):
        """
        Register a client object to use the services of the disk manager.
        
        When a client object wants to use a DiskManager instance it has to
        provide a directory path, under which to store its files. This path
        should corrispond to the same disk as the diskmanager _baseDir 
        attribute. All subsequente write and read operations performed by the
        disk manager will refer to files in the provided directory.
        
        @param directory: a directory path for which to register. This
                          directory will be used as the base path for all
                          subsequent file read and writes by the client that
                          registered for it.
        @param config: a dictionary containing configurations parameters
            for the registrations. The keys of that dictionary
            are:
                - 'maxDiskUsage': maximum disk page that the client is
                  allowed to use (in KBs) [-1 for infinity]
                - 'diskPolicy': a 3 bit bitmask that is a combination of
                  one of (DISK_FULL_REJECT_WRITES, 
                  DISK_FULL_DELETE_SOME) and one of
                  (DELETE_RANDOM, DELETE_OLDEST,
                  ELETE_NEWEST)
                - 'fileEncoding": encoding that will be used to read and
                  write every file under the registered
                  Dir
                                    
        """
        assert directory is not None
        assert os.path.isdir(directory), "%s is not a dir" % directory
        
        if config is None:
            config = DEFAULT_CONFIG
            
        if "maxDiskUsage" not in config.keys() \
            or "diskPolicy" not in config.keys() \
            or "encoding" not in config.keys():
            if DEBUG:
                print >> sys.stderr, "Invalid config. Using default"
            config = DEFAULT_CONFIG
            
        dedicatedDiskManager = BaseSingleDirDiskManager(directory, config, self)
        self._registeredDirs[directory] = dedicatedDiskManager
    
    #free space in KBs
    def getAvailableSpace(self):
        space = max(0, self._get_free_space() - self._minFreeSpace)
        return space
        
    
    def _get_free_space(self):
        """
        Retrieves current free disk space.
        """
        try:
            freespace = getfreespace(self._baseDir) / 1024.0
            return freespace 
        except:
            print >> sys.stderr, "cannot get free space of", self._baseDir
            print_exc()
            return 0
        
    def writeContent(self, directory, filename, content):
        """
        Write a string into a file.
        
        @return: The path of the written file, if everythin is right
        
        @precondition: directory is registered
        @precondition: content is a string
        @postcondition: minimum free space, and maximum disk usage constraints
                        are ok
        """
        if directory not in self._registeredDirs.keys():
            msg = "Directory %s not registered" % directory
            if DEBUG:
                print >> sys.stderr, msg
            raise DiskManagerException(msg)
        
        return self._registeredDirs[directory].writeContent(filename, content)
    
    def readContent(self, directory, filename):
        """
        Read the contents of a file.
        
        @return: a string containing the contents of the file
        """
        if directory not in self._registeredDirs.keys():
            msg = "Directory %s not registered" % directory
            if DEBUG:
                print >> sys.stderr, msg
                
            raise DiskManagerException(msg)
        
        return self._registeredDirs[directory].readContent(filename)

    def deleteContent(self, directory, filename):
        if directory not in self._registeredDirs.keys():
            msg = "Directory %s not registered" % directory
            if DEBUG:
                print >> sys.stderr, msg
            raise DiskManagerException(msg)
        
        return self._registeredDirs[directory].deleteContent(filename)
    
    def tryReserveSpace(self, directory, amount):
        """
        Check if there a given amount of available space. (in KBs)
        
        If there is, it does nothing :)
        (aslo if there isn't) 
        """
        if directory not in self._registeredDirs.keys():
            msg = "Directory %s not registered" % directory
            if DEBUG:
                print >> sys.stderr, msg
            raise DiskManagerException(msg)
        
        return self._registeredDirs[directory].tryReserveSpace(amount)
    
    def isFilenOnDisk(self, directory, filename):
        if directory not in self._registeredDirs.keys():
            msg = "Directory %s not registered" % directory
            if DEBUG:
                print >> sys.stderr, msg
            raise DiskManagerException(msg)
        
        return self._registeredDirs[directory].isFileOnDisk(filename)
        
        
    
class BaseSingleDirDiskManager(object):
    
    def __init__(self, workingDir, config, dm):
        self.workingDir = workingDir
        self.fileEncoding = config["encoding"]
        #select the last bit only
        self.diskFullPolicy = config["diskPolicy"] & 0x1
        #select the second and third bit from the right
        self.deletePolicy = config["diskPolicy"] & 0x6
        self.maxDiskUsage = config["maxDiskUsage"]
        if self.maxDiskUsage < 0: #infinte
            self.maxDiskUsage = (2 ** 80) #quite infinite
        self.dm = dm
        self.dirUsage = 0
        self._updateDirectoryUsage()
    
    def writeContent(self, filename, content):
        # assuming that a file system block is 4 KB
        # and therefore every file has a size that is a multiple of 4 kbs
        # if the assumption is violated nothing bad happens :)
        approxSize = max(MINIMUM_FILE_SIZE, (len(content) / 1024.0))
        sizeInKb = approxSize + (approxSize % MINIMUM_FILE_SIZE)
        if self.tryReserveSpace(sizeInKb):
            return self._doWrite(filename, content)
        else:
            if self.diskFullPolicy == DISK_FULL_REJECT_WRITES:
                raise DiskManagerException("Not enough space to write content. Rejecting")
            elif self.diskFullPolicy == DISK_FULL_DELETE_SOME:
                if self.makeFreeSpace(sizeInKb):
                    return self._doWrite(filename, content)
                else:
                    raise DiskManagerException("Unable to get enough space to write content.")
            
            
    def readContent(self, filename):
        path = os.path.join(self.workingDir, filename)
        if not os.path.isfile(path):
            raise IOError("Unable to read from %s" % path)
        with codecs.open(path, "rb", self.fileEncoding,"replace") as xfile:
            content = xfile.read()
        
        return content
    
    def deleteContent(self, filename):
        if DEBUG:
            print >> sys.stderr, "Deleting " + filename
        path = os.path.join(self.workingDir, filename)
        if not os.path.isfile(path):
            if DEBUG:
                print >> sys.stderr, "Noting to delete at %s" % path
            return False
        try:
            os.remove(path)
            self._updateDirectoryUsage()
            return True
        except OSError,e:
            print >> sys.stderr, "Warning: Error removing %s: %s" % (path, e)
            return False
    
    def makeFreeSpace(self, amount):
        if DEBUG:
            print >> sys.stderr, "Trying to retrieve %d KB of free space for %s" % (amount, self.workingDir)
        if amount >= self.maxDiskUsage:
            return False
        if amount >= (self.dm.getAvailableSpace() + self._currentDiskUsage()):
            return False
        
        maxTries = 100
        tries = 0
        while self._actualAvailableSpace() <= amount:
            if tries >= maxTries:
                print >> sys.stderr, "Unable to make up necessary free space for %s" % \
                         self.workingDir
                return False
            toDelete = self._selectOneToDelete()
            if toDelete is None:
                return False
            self.deleteContent(toDelete)
            tries = +1
            
            
        return True
    
    def isFileOnDisk(self, filename):
        path = os.path.join(self.workingDir, filename)
        if os.path.isfile(path):
            return path
        else:
            return None
    
    def _doWrite(self, filename, content):
        
        path = os.path.join(self.workingDir, filename)
        if os.path.exists(path):
            if DEBUG:
                print >> sys.stderr, "File %s exists. Overwriting it."
            os.remove(path)
        try:
            if not isinstance(content,unicode):
                content = content.decode(self.fileEncoding,'replace')
            with codecs.open(path, "wb", self.fileEncoding,'replace') as toWrite:
                toWrite.write(content)
        except Exception,e:
            #cleaning up stuff
            if os.path.exists(path):
                os.remove(path)
            raise e
        
        self._updateDirectoryUsage()
        return path
    
    def _selectOneToDelete(self):
        pathlist = map(lambda x : os.path.join(self.workingDir, x),
                            os.listdir(self.workingDir))
        candidateList = [xfile for xfile in pathlist
                         if os.path.isfile(os.path.join(self.workingDir, xfile))]
        
        if not len(candidateList) > 0:
            return None
            
        if self.deletePolicy == DELETE_RANDOM:
            return random.choice(candidateList)
        else:
            sortedByLastChange = sorted(candidateList, key=os.path.getmtime)
            if self.deletePolicy == DELETE_NEWEST_FIRST:
                return sortedByLastChange[-1]
            elif self.deletePolicy == DELETE_OLDEST_FIRST:
                return sortedByLastChange[0]


    def tryReserveSpace(self, amount):
        if amount >= self._actualAvailableSpace():
            return False
        else:
            return True
    
    def _currentDiskUsage(self):
        return self.dirUsage
    
    def _updateDirectoryUsage(self):
        listOfFiles = os.listdir(self.workingDir)
        listofPaths = \
            map(lambda name: os.path.join(self.workingDir, name), listOfFiles)
        
        #does not count subdirectories
        dirSize = sum([os.path.getsize(fpath) for fpath in listofPaths])
        
        self.dirUsage = dirSize / 1024.0 #Kilobytes
    
    def _actualAvailableSpace(self):
        space = min(self.dm.getAvailableSpace(),
                   self.maxDiskUsage - self._currentDiskUsage())
        return space
    
        
            
