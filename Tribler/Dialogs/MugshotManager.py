# Written by Arno Bakker
# see LICENSE.txt for license information

import wx
import os
from sha import sha
from shutil import copy2
from traceback import print_exc

from Tribler.utilities import show_permid_short

ICON_MAX_SIZE = 4*1024
BMP_EXT = '.bmp'
BMP_MIME_TYPE = 'image/bmp'
DEFAULT_ICON = 'joe32.bmp'

DEBUG = 0

class MugshotManager:

    __single = None
    
    def __init__(self):
        if MugshotManager.__single:
            raise RuntimeError, "MugshotManager is singleton"
        MugshotManager.__single = self

    def getInstance(*args, **kw):
        if MugshotManager.__single is None:
            MugshotManager(*args, **kw)
        return MugshotManager.__single
    getInstance = staticmethod(getInstance)
        

    def register(self,usericonpath,sysiconpath):
        self.usericonpath = usericonpath
        self.sysiconpath = sysiconpath

    def create_wxImageList(self,peerswpermid,setindex=False):
        """ peerswpermid is a list of dictionaries that contain the
            name and permid of a peer
        """
        if len(peerswpermid) == 0:
            return None
        height = 0
        width = 0
        list = []
        for peer in peerswpermid:
            filename = self.find_filename(peer['permid'],peer['name'])
            if filename is None:
                # Fallback icon
                filename = self.get_defaulticon_filename()
            bm = None
            try:
                bm = wx.Bitmap(filename,wx.BITMAP_TYPE_BMP)
            except:
                try:
                    filename = self.get_defaulticon_filename()
                    bm = wx.Bitmap(filename,wx.BITMAP_TYPE_BMP)
                except:
                    return None
            if bm.GetWidth() > width:
                width = bm.GetWidth()
            if bm.GetHeight() > height:
                height = bm.GetHeight()
            list.append(bm)
        imgList = wx.ImageList(width,height)
        if imgList is None:
            return None
        for peer in peerswpermid:
            bm = list.pop(0)
            index = imgList.Add(bm)
            if setindex:
                peer['tempiconindex'] = index
        return imgList

    def get_defaulticon_filename(self):
        return os.path.join(self.sysiconpath, DEFAULT_ICON)

    def get_defaulticon_wxBitmap(self):
        return wx.Bitmap(self.get_defaulticon_filename(),wx.BITMAP_TYPE_BMP)

    def find_filename(self,permid,name):
        # See if we can find it using PermID or name (old style):
        filename = self._permid2iconfilename(permid)
        if not os.access(filename,os.R_OK):
            if name is not None:
                # Old style, < 3.5.0
                filename = os.path.join(self.usericonpath,name+BMP_EXT)
                if not os.access(filename,os.R_OK):
                    return None
            else:
                return None
        return filename

    def load_data(self,permid,name=None):

        print "mm: load_data permid",show_permid_short(permid),"name",name

        filename = self.find_filename(permid,name)
        if filename is None:
            return [None,None]
        try:
            f = open(filename,"r")
            data = f.read(-1)
            f.close()
        except:
            return [None,None]
        if data == '' or len(data) > ICON_MAX_SIZE: 
            return [None,None]
        else:
            return [BMP_MIME_TYPE,data]


    def save_data(self,permid,type,data):
        if type != BMP_MIME_TYPE:
            return
        filename = self._permid2iconfilename(permid)
        try:
            f = open(filename,"w")
            f.write(data)
            f.close()
            return True
        except:
            if DEBUG:
                print_exc()
            return False

    def copy_file(self,permid,srcfilename):
        dstfilename = self._permid2iconfilename(permid)
        if DEBUG:
            print "mugmgr: copying icon",srcfilename,"to",dstfilename
        try:
            copy2(os.path.normpath(srcfilename),dstfilename)
        except:
            if DEBUG:
                print_exc()
            pass

    def load_wxBitmap(self,permid,name=None):
        filename = self.find_filename(permid,name)
        if filename is None:
            return None
        return self.load_wxBitmap_from_file(filename)

    def load_wxBitmap_from_file(self,filename):
        try:
            if filename.lower().endswith(BMP_EXT):
                bm = wx.Bitmap(filename,wx.BITMAP_TYPE_BMP)
                return bm
        except:
            if DEBUG:
                print_exc()
            pass
        return None

    def _permid2iconfilename(self,permid):
        safename = sha(permid).hexdigest()
        return os.path.join(self.usericonpath, safename+BMP_EXT)
 
