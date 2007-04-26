# Written by Arno Bakker
# see LICENSE.txt for license information

import wx
import os
from cStringIO import StringIO
from sha import sha
from shutil import copy2
from traceback import print_exc

from Tribler.utilities import show_permid_short

ICON_MAX_SIZE = 10*1024
BMP_EXT = '.bmp'
BMP_MIME_TYPE = 'image/bmp'

DEBUG = True

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
        

    def register(self,userpath,syspath):
        self.usericonpath = os.path.join(userpath,'icons')
        self.sysiconpath = os.path.join(syspath,'icons')
        
        self.defaults = {}
        self.defaults['filesMode'] = {}        
        self.defaults['filesMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'defaultThumb.png'))
        self.defaults['filesMode']['MASK_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'itemMask.png'))
        self.defaults['filesMode']['HEART_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'heart1.png'))
        self.defaults['personsMode'] = {}
        self.defaults['personsMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'defaultThumbPeer.png'))
        self.defaults['personsMode']['MASK_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'itemMask.png'))
        self.defaults['personsMode']['HEART_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'heart1.png'))
        self.defaults['personsMode']['FRIEND_ONLINE_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'friend.png'))
        self.defaults['personsMode']['FRIEND_OFFLINE_BITMAP'] = wx.Bitmap(os.path.join(syspath,'Tribler', 'vwxGUI', 'images', 'friend_offline.png'))
 

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

        if DEBUG:
            print "mm: load_data permid",show_permid_short(permid),"name",name

        filename = self.find_filename(permid,name)
        if filename is None:
            
            if DEBUG:
                print "mm: load_data: filename is None"
            
            return [None,None]
        try:
            f = open(filename,"r")
            data = f.read(-1)
            f.close()
        except:
            if DEBUG:
                print "mm: load_data: Error reading"

            
            return [None,None]
        if data == '' or len(data) > ICON_MAX_SIZE:
            
            if DEBUG:
                print "mm: load_data: data 0 or too big",len(data)
 
            return [None,None]
        else:
            return [BMP_MIME_TYPE,data]


    def save_data(self,permid,type,data):
        filename = self._permid2iconfilename(permid)
        try:
            mi = StringIO(data)
            #im = wx.ImageFromStreamMime(mi,type)
            im.SaveMimeFile(filename,BMP_MIME_TYPE)
            f = open(filename,"w")
            f.write(data)
            f.close()
            return True
        except:
            if DEBUG:
                print_exc()
            return False

    def copy_file(self,permid,srcfilename):
        """ srcfilename must point to a .BMP file """
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
            im = wx.Image(filename)
            bm = wx.BitmapFromImage(im.Scale(64,64),-1)
            return bm
        except:
            if DEBUG:
                print_exc()
            pass
        return None

    def _permid2iconfilename(self,permid):
        safename = sha(permid).hexdigest()
        return os.path.join(self.usericonpath, safename+BMP_EXT)
 

    def data2wxBitmap(self,type,data):
        try:
            mi = StringIO(data)
            # St*pid wx says "No handler for image/bmp defined" while this
            # is the image handler that is guaranteed to always be there,
            # according to the docs :-(
            if type == 'image/bmp':
                im = wx.ImageFromStream(mi,wx.BITMAP_TYPE_BMP)
            else:
                im = wx.ImageFromStreamMime(mi,type)
            
            bm = wx.BitmapFromImage(im.Scale(64,64),-1)
            return bm
        except:
            if DEBUG:
                print_exc()
            return None

    def get_default(self,mode,name):
        return self.defaults[mode][name]
    