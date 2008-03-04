import wx, os
import StringIO

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
        self.defaults['filesMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumb.png'))
        self.defaults['filesMode']['BIG_DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbL.png'))
        self.defaults['filesMode']['MASK_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'fileItemMask_clean.png'))
        self.defaults['filesMode']['MASK_BITMAP_BOTTOM'] = wx.Bitmap(os.path.join(self.guiImagePath, 'itemMask.png'))
        #self.defaults['filesMode']['HEART_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'heart1.png'))
        self.defaults['libraryMode'] = {}
        self.defaults['libraryMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbLibrary.png'))
        self.defaults['personsMode'] = {}
        self.defaults['personsMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbPeer.png'))
        self.defaults['personsMode']['DEFAULT_THUMB_SMALL'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbPeerS.png'))
        self.defaults['personsMode']['MASK_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'itemMask.png'))
        self.defaults['personsMode']['MASK_BITMAP_CLEAN'] = wx.Bitmap(os.path.join(self.guiImagePath, 'itemMask_clean.png'))
        self.defaults['personsMode']['HEART_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'heart1.png'))
        self.defaults['personsMode']['FRIEND_ONLINE_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'friend.png'))
        self.defaults['personsMode']['FRIEND_OFFLINE_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'friend_offline.png'))
        self.defaults['personsMode']['ISFRIEND_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'isFriend.png'))
        self.defaults['personsMode']['ISFRIEND_CLICKED_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'isFriend_clicked.png'))
        self.defaults['personsMode']['SUPERPEER_BITMAP'] = wx.Bitmap(os.path.join(self.guiImagePath, 'superpeer.png'))
        self.defaults['subscriptionsMode'] = {}
        self.defaults['subscriptionsMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'favicon.png'))
        self.defaults['subscriptionsMode']['BUDDYCAST_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'bcicon.png'))
        self.defaults['friendsMode'] = {}
        self.defaults['friendsMode']['DEFAULT_THUMB'] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbPeerS.png'))
        self.defaults['friendsMode']['MASK_BITMAP_OVERLAY'] = wx.Bitmap(os.path.join(self.guiImagePath, 'itemMask_clean.png'))
    
        self.DOWNLOAD_BUTTON_LIBRARY = wx.Bitmap(os.path.join(self.guiImagePath, 'inLibrary.png'))
        self.DOWNLOAD_BUTTON_LIBRARY_S = wx.Bitmap(os.path.join(self.guiImagePath, 'inLibrary_clicked.png'))
        self.DOWNLOAD_BUTTON_DOWNLOAD = wx.Bitmap(os.path.join(self.guiImagePath, 'download.png'))
        self.DOWNLOAD_BUTTON_DOWNLOAD_S = wx.Bitmap(os.path.join(self.guiImagePath, 'download_clicked.png'))
        self.DOWNLOAD_BUTTON_PLAY = wx.Bitmap(os.path.join(self.guiImagePath, 'play.png'))
        self.DOWNLOAD_BUTTON_PLAY_S = wx.Bitmap(os.path.join(self.guiImagePath, 'play_clicked.png'))
            
        self.SOURCE_ICON_TRIBLER = wx.Bitmap(os.path.join(self.guiImagePath, 'icon_tribler.png'))
        self.SOURCE_ICON_YOUTUBE = wx.Bitmap(os.path.join(self.guiImagePath, 'icon_youtube.png'))
        self.SOURCE_ICON_LIVELEAK = wx.Bitmap(os.path.join(self.guiImagePath, 'icon_liveleak.png'))
        self.SOURCE_ICON_REMOTE = wx.Bitmap(os.path.join(self.guiImagePath, 'icon_remote.png'))
        self.categoryThumbs = {}
        
        
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
        if mode == 'play':
            return self.DOWNLOAD_BUTTON_PLAY, self.DOWNLOAD_BUTTON_PLAY_S
        elif mode == 'download':
            return self.DOWNLOAD_BUTTON_DOWNLOAD, self.DOWNLOAD_BUTTON_DOWNLOAD_S
        elif mode == 'library':
            return self.DOWNLOAD_BUTTON_LIBRARY, self.DOWNLOAD_BUTTON_LIBRARY_S
        else:
            raise Exception('No such mode')
        
    def getSourceIcon(self, source):
        if source == 'tribler':
            return self.SOURCE_ICON_TRIBLER
        elif source == 'youtube':
            return self.SOURCE_ICON_YOUTUBE
        elif source == 'liveleak':
            return self.SOURCE_ICON_LIVELEAK
        elif source == 'remote':
            return self.SOURCE_ICON_REMOTE
        elif not source:
            return None
        else:
            raise Exception('No such source')

        
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
            bm = self.load_wxBitmap(peer['permid'])
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


    def create_from_file(self,permid,srcfilename):
        """ srcfilename must point to an image file processable by wx.Image """
        try:
            sim = wx.Image(srcfilename).Scale(ICON_MAX_DIM,ICON_MAX_DIM)
            sim.SaveFile(dstfilename,wx.BITMAP_TYPE_JPEG)
            f = StringIO()
            sim.SaveStream(f,wx.BITMAP_TYPE_JPEG)
            self.peer_db.updatePeerIcon('image/jpeg',f.getvalue())
            f.close()
        except:
            if DEBUG:
                print_exc()
            pass

    def load_wxBitmap(self,permid):
        [mimetype,data] = self.peer_db.getPeerIcon(permid)
        return data2wxBitmap(type,data)


def data2wxBitmap(type,data,dim=ICON_MAX_DIM):
    try:
        mi = StringIO.StringIO(data)
        # St*pid wx says "No handler for image/bmp defined" while this
        # is the image handler that is guaranteed to always be there,
        # according to the docs :-(
        if type == 'image/bmp':
            im = wx.ImageFromStream(mi,wx.BITMAP_TYPE_BMP)
        else:
            im = wx.ImageFromStreamMime(mi,type)
        
        bm = wx.BitmapFromImage(im.Scale(dim,dim),-1)
        return bm
    except:
        print_exc()
        return None
        