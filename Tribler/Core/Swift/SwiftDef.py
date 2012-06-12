# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import urlparse
import binascii
from traceback import print_exc,print_stack
import tempfile
import subprocess
import random
import time

from Tribler.Core.Base import *
from Tribler.Core.simpledefs import *
from Tribler.Core.Swift.util import *

class SwiftDef(ContentDefinition):
    """ Definition of a swift swarm, that is, the root hash (video-on-demand) 
    and any optional peer-address sources. """
    
    def __init__(self,roothash=None,tracker=None,chunksize=None,duration=None):
        self.readonly = False
        self.roothash = roothash
        self.tracker = tracker
        self.chunksize = chunksize
        self.duration = duration
        self.files = []
        self.multifilespec = None 
    
    #
    # Class methods for creating a SwiftDef from an URL or .spec file (multi-file swarm)
    #
    def load_from_url(url):
        """
        If the URL starts with the swift URL scheme, we convert the URL to a 
        SwiftDef.
        
        Scheme: tswift://tracker/roothash-as-hex
                tswift://tracker/roothash-as-hex$chunk-size-in-bytes
                tswift://tracker/roothash-as-hex@duration-in-secs
                tswift://tracker/roothash-as-hex$chunk-size-in-bytes@duration-in-secs
        
        Note: swift URLs pointing a file in a multi-file content asset
        cannot be loaded by this method. Load the base URL via this method and 
        specify the file you want to download via 
        DownloadConfig.set_selected_files(). 
        
        @param url URL
        @return SwiftDef.
        """
        # Class method, no locking required
        (roothash,tracker,chunksize,duration) = parse_url(url)
        s = SwiftDef(roothash,tracker,chunksize,duration)
        s.readonly = True
        return s
    load_from_url = staticmethod(load_from_url)


    def is_swift_url(url):
        return isinstance(url, str) and url.startswith(SWIFT_URL_SCHEME)
    is_swift_url = staticmethod(is_swift_url)


    #
    # ContentDefinition interface
    #
    def get_def_type(self):
        """ Returns the type of this Definition
        @return string
        """
        return "swift"

    def get_name(self):
        """ Returns the user-friendly name of this Definition
        @return string
        """
        return self.get_roothash_as_hex()
    
    def get_id(self):
        """ Returns a identifier for this Definition
        @return string
        """
        return self.get_roothash()

    def get_live(self):
        """ Whether swift swarm is a live stream 
        @return Boolean
        """
        return False

    #
    # Swift specific
    #
    def get_roothash(self):
        """ Returns the roothash of the swift swarm.
        @return A string of length 20. """
        return self.roothash

    def get_roothash_as_hex(self):
        """ Returns the roothash of the swift swarm.
        @return A string of length 40, of 20 concatenated 2-char hex bytes. """

        return binascii.hexlify(self.roothash)
    
    def set_tracker(self,url):
        """ Sets the tracker  
        @param url The tracker URL.
        """
        self.tracker = url
        
    def get_tracker(self):
        """ Returns the tracker URL.
        @return URL """
        return self.tracker

    def get_url(self):
        """ Return the basic URL representation of this SwiftDef.
        @return URL
        """
        url = SWIFT_URL_SCHEME+':'
        if self.tracker is not None:
            url += '//'+self.tracker
        url += '/'+binascii.hexlify(self.roothash)
        return url
      
    def get_url_with_meta(self):
        """ Return the URL representation of this SwiftDef with extra 
        metadata, e.g. duration.
        @return URL
        """
        url = self.get_url()
        if self.duration is not None:
            url += '@'+str(self.duration)
        return url
            
    def get_duration(self):
        """ Return the (optional) duration of this SwiftDef or None
        @return a number of seconds
        """  
        return self.duration
    
    
    def get_chunksize(self):
        """ Return the (optional) chunksize of this SwiftDef or None
        @return a number of bytes
        """  
        return self.chunksize
    

    def get_multifilespec(self):
        """ Return the multi-file spec of this SwiftDef (only when creating
        a new swift def)
        @return a string in multi-file spec format.
        """  
        return self.multifilespec

    
    # SWIFTSEED/MULTIFILE
    def add_content(self,inpath,outpath=None):
        """
        Add a file or directory to this Swift definition. When adding a
        directory, all files in that directory will be added to the torrent.
        
        One can add multiple files and directories to a Swift definition.
        In that case the "outpath" parameter must be used to indicate how
        the files/dirs should be named in the multi-file specification. 

        To seed the content via the core you will need to start the download 
        with the dest_dir set to the top-level directory containing the files 
        and directories to seed. 
        
        @param inpath Absolute name of file or directory on local filesystem, 
        as Unicode string.
        @param outpath (optional) Name of the content to use in the torrent def
        as Unicode string.
        """
        if self.readonly:
            raise OperationNotEnabledByConfigurationException()
        
        s = os.stat(inpath)
        d = {'inpath':inpath,'outpath':outpath,'length':s.st_size}
        self.files.append(d)


    def create_multifilespec(self):
        specfn = None
        if len(self.files) > 1:
            filelist = []
            for d in self.files:
                specpath = d['outpath'].encode("UTF-8")
                if sys.platform == "win32":
                    specpath.replace("\\","/")
                filelist.append((specpath,d['length'])) 
                
            self.multifilespec = filelist2swiftspec(filelist)

            print >>sys.stderr,"SwiftDef: multifile",self.multifilespec

            return self.multifilespec
        else:
            return None 


    def finalize(self,binpath,userprogresscallback=None,destdir='.',removetemp=False):
        """
        Calculate root hash (time consuming).
         
        The also userprogresscallback will be called by the calling thread 
        periodically, with a progress percentage as argument.
        
        The userprogresscallback function will be called by the calling thread. 
        
        @param binpath  OS path of swift binary.
        @param userprogresscallback Function accepting a fraction as first
        argument.
        @param destdir OS path of where to store temporary files.
        @param removetemp Boolean, remove temporary files or not
        @return filename of multi-spec definition or None (single-file)
        """
        if userprogresscallback is not None:
            userprogresscallback(0.0)
                
        specpn = None    
        if len(self.files) > 1:
            if self.multifilespec is None:
                self.create_multifilespec()
                
            if userprogresscallback is not None:
                userprogresscallback(0.2)

            specfn = "multifilespec-p"+str(os.getpid())+"-r"+str(random.random())+".txt"
            specpn = os.path.join(destdir,specfn)
            
            f = open(specpn,"wb")
            f.write(self.multifilespec)
            f.close()
        
            filename = specpn
        else:
            filename = self.files[0]['inpath']

        urlfn = "swifturl-p"+str(os.getpid())+"-r"+str(random.random())+".txt"
        urlpn = os.path.join(destdir,urlfn)

        args=[]
        args.append(str(binpath))
        
        # Arno, 2012-05-29: Hack. Win32 getopt code eats first arg when Windows app
        # instead of CONSOLE app.
        args.append("-j")
        if self.tracker is not None:
            args.append("-t")
            args.append(self.tracker)
        args.append("--printurl")
        args.append("-r")
        args.append(urlpn)
        args.append("-f")
        args.append(filename)
        #args.append("-B") # DEBUG Hack
        
        if sys.platform == "win32":
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            creationflags=0
        pobj = subprocess.Popen(args,stdout=subprocess.PIPE,cwd='.',creationflags=creationflags)
        
        if userprogresscallback is not None:
            userprogresscallback(0.6)

        # Arno, 2012-05-25: When running in binary on windows, swift is a 
        # windows app, so no console output. Hence, write swift URL to disk.
        count = 0.0
        while count < 600.0: # 10 minutes
            pobj.poll()
            if pobj.returncode is not None:
                break
            time.sleep(1)
            count += 1.0
            if userprogresscallback is not None:
                userprogresscallback(0.6 + count/1000.0)
            
        f = open(urlpn,"rb")
        url = f.read()
        f.close()
        
        try:
            os.remove(urlpn)
        except:
            pass

        if url is None or len(url) == 0:
             self.roothash = '0' * 20
             print >>sys.stderr,"swift: finalize: Error calculating roothash"
             return None 

        if userprogresscallback is not None:
            userprogresscallback(0.9)

        (self.roothash,self.tracker,self.chunksize,self.duration) = parse_url(url)
        self.readonly = True
        
        if removetemp and specpn is not None:
            try:
                os.remove(specpn)
            except:
                pass

            try:
                mbinmapfn = specpn+".mbinmap"
                os.remove(mbinmapfn)
            except:
                pass

            try:
                mhashfn = specpn+".mhash"
                os.remove(mhashfn)
            except:
                pass
            
        if userprogresscallback is not None:
            userprogresscallback(1.0)
            
        return specpn

    def save_multifilespec(self,filename):
        """
        Store the multi-file spec generated by finalize() if multiple
        files were added with add_content() to filename.
        @param filename An absolute Unicode path name.
        """
        if not self.readonly:
            raise OperationNotEnabledByConfigurationException()

        f = open(filename,"wb")
        f.write(self.multifilespec)
        f.close()



def parse_url(url):
    p = urlparse.urlparse(url)
    roothash = binascii.unhexlify(p.path[1:41])
    if p.netloc == "":
        tracker = None
    else:
        tracker = p.netloc
        
    cidx = p.path.find('$')
    didx = p.path.find('@')
        
    if cidx != -1:
        if didx == -1:
            chunksize = int(p.path[cidx+1:])
        else:
            chunksize = int(p.path[cidx+1:didx])
    else:
        chunksize = None
        
    if didx != -1:
        duration = int(p.path[didx+1:])
    else:
        duration = None

    return (roothash,tracker,chunksize,duration)
