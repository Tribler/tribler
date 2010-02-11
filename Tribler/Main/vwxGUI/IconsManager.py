# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information

import wx, os
import cStringIO

from Tribler.Core.API import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

ICON_MAX_DIM = 80
SMALL_ICON_MAX_DIM = 32


class IconsManager:
    
    __single = None
    
    def __init__(self):
        
        if IconsManager.__single:
            raise RuntimeError, "IconsManager is singleton"
        
        self.guiUtility = GUIUtility.getInstance()
        self.guiImagePath = os.path.join(self.guiUtility.utility.getPath(), 'Tribler', 'Main', 'vwxGUI', 'images')
        self.defaults = {}
        self.defaults['filesMode'] = {}        
        self.defaults['personsMode'] = {}
        self.defaults['personsMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbPeer.png'))

    
        self.DOWNLOAD_BUTTON_DOWNLOAD = wx.Bitmap(os.path.join(self.guiImagePath, 'download.png'))
        self.DOWNLOAD_BUTTON_DOWNLOAD_S = wx.Bitmap(os.path.join(self.guiImagePath, 'download_clicked.png'))
            
        self.categoryThumbs = {}

        # Added from mugshot manager to show items in left menu
        #######################################################

        
        self.peer_db = self.guiUtility.utility.session.open_dbhandler(NTFY_PEERS)
        
        IconsManager.__single = self
        
        
        
    def getInstance(*args, **kw):
        """ Returns the IconsManager singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor 
            params. 
            @return IconsManager."""
        if IconsManager.__single is None:
            IconsManager(*args, **kw)
        return IconsManager.__single
    getInstance = staticmethod(getInstance)
    
    def get_default(self,mode,name):
        return self.defaults[mode][name]
    
    def getCategoryIcon(self, mode, cat, thumbtype = 'normal', web2 = False):
        #print "**** getCategoryIcon", mode, cat, thumbtype, web2
        
        categoryConverter = {'picture':'other', 
                             'videoclips':'video',
                             'document':'other'}
        thumbType = {'normal':'defaultThumb_%s.png',
                     'large':'defaultThumbL_%s.png',
                     'small':'defaultThumbS_%s.png',
                     'icon':'icon_%s.png'
                     }
        if type(cat) == list:
            cat = cat[0]
        if web2:
            cat = 'video'
        elif cat == None:
            return None
        
        cat = cat.lower()
        
        if cat in categoryConverter:
            cat = categoryConverter[cat]
        
                
        if self.categoryThumbs.get((cat, thumbtype)):
            return self.categoryThumbs[(cat, thumbtype)]
        else:
            filename = thumbType[thumbtype] % cat
            pathname = os.path.join(self.guiImagePath, filename)
            
            #print >> sys.stderr, 'iconm: Looking for category image:',pathname
            if os.path.isfile(pathname):
                bm = wx.Bitmap(pathname)
            else:
                bm = None
                print >> sys.stderr, 'iconm: No thumb found for category: %s' % cat
            self.categoryThumbs[(cat, thumbtype)] = bm
            return bm
    
            
    def getDownloadButton(self, mode):
        if mode == 'download':
            return self.DOWNLOAD_BUTTON_DOWNLOAD, self.DOWNLOAD_BUTTON_DOWNLOAD_S
        raise Exception('No such mode')
        
    def create_wxImageList(self,peerswpermid,setindex=False):
        """ peerswpermid is a list of dictionaries that contain the
            name and permid of a peer
        """
        if len(peerswpermid) == 0:
            return None

        # scale default to proper size
        defaultThumb = self.get_default('personsMode','DEFAULT_THUMB')
        defaultThumb = wx.BitmapFromImage(defaultThumb.ConvertToImage().Scale(SMALL_ICON_MAX_DIM,SMALL_ICON_MAX_DIM))

        list = []
        for peer in peerswpermid:
            bm = self.load_wxBitmap(peer['permid'], SMALL_ICON_MAX_DIM)
            if bm is None:
                bm = defaultThumb
            list.append(bm)
        imgList = wx.ImageList(SMALL_ICON_MAX_DIM,SMALL_ICON_MAX_DIM)
        if imgList is None:
            return None
        for peer in peerswpermid:
            bm = list.pop(0)
            index = imgList.Add(bm)
            if setindex:
                peer['tempiconindex'] = index
        return imgList

    def load_wxBitmap(self,permid, dim = ICON_MAX_DIM):
        [_mimetype,data] = self.peer_db.getPeerIcon(permid)
        if data is None:
            return None
        else:
            return data2wxBitmap('image/jpeg',data, dim)


def data2wxImage(type,data,dim=ICON_MAX_DIM):
    try:
        if data is None:
            return None
        
        mi = cStringIO.StringIO(data)
        # St*pid wx says "No handler for image/bmp defined" while this
        # is the image handler that is guaranteed to always be there,
        # according to the docs :-(
        if type == 'image/bmp':
            im = wx.ImageFromStream(mi,wx.BITMAP_TYPE_BMP)
        else:
            im = wx.ImageFromStreamMime(mi,type)
        
        return im.Scale(dim,dim)
    except:
        print >> sys.stderr, 'data2wxImage called (%s, %s)' % (`type`,`dim`)
        print_exc()
        return None
        

def data2wxBitmap(type,data,dim=ICON_MAX_DIM):
    try:
        im = data2wxImage(type,data,dim=dim)
        if im is None:
            bm = None
        else:
            bm = wx.BitmapFromImage(im,-1)
            
        return bm
    except:
        print >> sys.stderr, 'data2wxBitmap called (%s, %s)' % (`type`,`dim`)
        print_exc()
        return None
        
