# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Just manage peer icons. No wx stuff here. See Tribler.Main.vwxGUI.IconsManager
# for that.

import os, os.path
import sys
from cStringIO import StringIO
from sha import sha
from shutil import copy2
from traceback import print_exc

from Tribler.Core.Utilities.utilities import show_permid_short

ICON_MAX_SIZE = 10*1024
NETW_EXT = '.jpg'
NETW_MIME_TYPE = 'image/jpeg'

DEBUG = False

class MugshotManager:

    __single = None
    
    def __init__(self):
        if MugshotManager.__single:
            raise RuntimeError, "MugshotManager is singleton"
        MugshotManager.__single = self
        self.usericonpath = '' # for test suite
        

    def getInstance(*args, **kw):
        if MugshotManager.__single is None:
            MugshotManager(*args, **kw)
        return MugshotManager.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,config):
        self.usericonpath = os.path.join(config['state_dir'],config['peer_icon_path'])
        if not os.path.isdir(self.usericonpath):
            os.mkdir(self.usericonpath)
	
    def load_data(self,permid,name=None):

        if DEBUG:
            print >>sys.stderr,"mugmgr: load_data permid",show_permid_short(permid),"name",`name`

        filename = self.find_filename(permid,name)
        if filename is None:
            
            if DEBUG:
                print >>sys.stderr,"mugmgr: load_data: filename is None"
            
            return [None,None]
        try:
            f = open(filename,"rb")
            data = f.read(-1)
            f.close()
        except:
            if DEBUG:
                print >>sys.stderr,"mugmgr: load_data: Error reading"

            
            return [None,None]
        if data == '' or len(data) > ICON_MAX_SIZE:
            
            if DEBUG:
                print >>sys.stderr,"mugmgr: load_data: data 0 or too big",len(data)
 
            return [None,None]
        else:
            return [NETW_MIME_TYPE,data]


    def save_data(self,permid,type,data):
        filename = self._permid2iconfilename(permid)
        
        if DEBUG:
            print >>sys.stderr,"mugmgr: save_data: filename is",filename,type
        try:
            # Arno: no longer wx conversion
            f = open(filename,"wb")
            f.write(data)
            f.close()
            return True
        except:
            if DEBUG:
                print_exc()
            return False


    def find_filename(self,permid,name):
        # See if we can find it using PermID or name (old style):
        filename = self._permid2iconfilename(permid)
        if not os.access(filename,os.R_OK):
            if name is not None:
                # Old style, < 3.5.0
                try:
                    filename = os.path.join(self.usericonpath,name+NETW_EXT)
                    if not os.access(filename,os.R_OK):
                        return None
                except:
                    return None
            else:
                return None
        return filename

    def _permid2iconfilename(self,permid):
        safename = sha(permid).hexdigest()
        return os.path.join(self.usericonpath, safename+NETW_EXT)

