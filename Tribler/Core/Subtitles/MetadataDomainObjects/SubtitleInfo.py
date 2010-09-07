# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import \
    LanguagesProvider
import base64
import codecs
import hashlib
import os.path
import sys

DEBUG = False

class SubtitleInfo(object):
    '''
    Represents a subtitles in a given language.
    
    It contains three fields, namely lang (an ISO 693-2 code), path that is
    the path into the filesystem to the subtitles file, and checksum that is
    a base64 representation of the sha1 checksum for that file.
    It also manages the computation and verification of a sha1 checksum for 
    a the subtitle.
        
    Notice that the path property can be None. This means that tha actual
    subtitle hasn't been collected and is not available on the local
    filesystem, In that case the checksum field will be none as well.
    
    Also notice that this object is meant to be used as a DTO. Simply changing
    property in this object won't by themself affect values contained in the
    Database
    
    SYNCHRONIZATION: This objects act only as copies of the data in the DB.
    If the instance is nevere passed by between different threads
    no synchronization is needed. 
    '''

    

    def __init__(self, lang, path=None, checksum=None):
        """
        Create a subtitle instance.
        
        @param lang: an ISO 639-2 language code. Notice that not every language
                     code described by the standard is supported, but only
                     a small subset. See the Languages module
        @param path: a file system path to the subtitles file
        @param checksum: a sha1 checksum of the contents 
                         of the subitles file
        """
        self._languages = LanguagesProvider.getLanguagesInstance()
        if lang not in self._languages.supportedLanguages.keys():
            raise ValueError("Language" + lang + " not supported")
        
        
        #ISO 639-2 code. See Languages for supported languages
        self._lang = lang #final property
        #A string representing the path in the filesystme for this subtitle
        self._path = path
        #sha1 checksum
        self._checksum = checksum
        
            
    def getLang(self):
        '''
        Returns the language of the subtitle as a three characters code

        @rtype: str
        @return: a three characters ISO 639-2 code
        '''
        return self._lang

    lang = property(getLang) # "final" property
        
    def setPath(self, path):
        '''
        Sets the local path for the subtitle. 

        Calling this method does not change what is stored in the DB. You will
        have to update that data separately (see L{MetadataDBHandler})

        @type path: str
        @param path: the local path were the subtitle is stored
        '''
        self._path = path

            
    def getPath(self):
        '''
        Get the path on the local host for the subtitle file, if available.

        @rtype: str
        @return: the local path if the subtitle is locally available. Otherwise
            None.
        '''
        return self._path

    
    path = property(getPath, setPath)
            
    def setChecksum(self, checksum):
        '''
        Set the checksum for this subtitle instance. 

        ATTENTION: This method should be never called, but instead a the
        L{computeChecksum} method should be called instead.

        @type checksum: str
        @param checksum: a 160bit sha1 checksum of the subtitle
        '''
        self._checksum = checksum

            
    def getChecksum(self):
        '''
        Returns the SHA-1 checksum of the subtitle.

        @rtype: str
        @return: a 20byte string representing the SHA-1 checksum of the
            subtitle
        '''
        return self._checksum

        
    checksum = property(getChecksum, setChecksum)
        
    def subtitleExists(self):
        """
        Checks wheter a subtitle exist in its specified path.
        
        @return: True if self.path is pointing to a local existing file.
            Otherwise false
        """

        if self.path is None:
            return False
        return os.path.isfile(self.path)

    
    def computeChecksum(self):
        """
        Computes the checksum of the file containing the subtitles
        and sets its corresponding property.

        @precondition: self.subtitleExists()
        @postcondition: self.checksum is not None
        """
 
        assert self.subtitleExists()

        self.checksum = self._doComputeChecksum()
 
        
    def _doComputeChecksum(self):
        """
        Computes the checksum of the file containing the subtitles
        
        @precondition: self.subtitleExists()
        """
        try:
            with codecs.open(self.path, "rb", "utf-8", "replace") as subFile:
                content = subFile.read()
      
            hasher = hashlib.sha1()
            hasher.update(content.encode('utf-8','replace'))
            
            return hasher.digest()
        
        except IOError:
            print >> sys.stderr, "Warning: Unable to open " + self.path + " for reading"
 
        
    
    def verifyChecksum(self):
        """
        Verifies the checksum of the file containing the subtitles.
        
        Computes the checksum of the file pointed by self.path
        and checks whether it is equal to the one in self.checksum
        
        @precondition: self.subtitleExists()
        @precondition: self.checksum is not None

        @rtype: boolean
        @return: True if the verification is ok.

        @raises AssertionError: if one of the preconditions does not hold
        """

        assert self.subtitleExists(), "Cannot compute checksum: subtitle file not found"
        assert self.checksum is not None, "Cannot verify checksum: no checksum to compare with"
        
        computed = self._doComputeChecksum()
        return computed == self.checksum

    
    def __str__(self):

        if self.path is not None:
            path = self.path
        else:
            path = "None"
        return "subtitle: [lang=" + self.lang +"; path=" + path \
                + "; sha1=" + base64.encodestring(self.checksum).rstrip() + "]"

            
    def __eq__(self,other):
        '''
        Test instances of SubtitleInfo for equality.
        
        Two subtitle instances are considered equal if they have the same
        language and the same file checksum
        '''

        if self is other:
            return True
        return self.lang == other.lang and self.checksum == other.checksum
                #and self.path == other.path

                
        
    def __ne__(self,other):
        return not self.__eq__(other)
        
        
    
