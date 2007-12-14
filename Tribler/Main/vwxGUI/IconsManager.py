import wx, os
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

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
        IconsManager.__single = self
        
    def get_instance(*args, **kw):
        """ Returns the IconsManager singleton if it exists or otherwise
            creates it first, in which case you need to pass the constructor 
            params. 
            @return IconsManager."""
        if IconsManager.__single is None:
            IconsManager(*args, **kw)
        return IconsManager.__single
    get_instance = staticmethod(get_instance)
    
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
            
            #print >> sys.stderr, 'mm: Looking for category image:',pathname
            if os.path.isfile(pathname):
                bm = wx.Bitmap(pathname)
            else:
                bm = None
                print >> sys.stderr, 'mm: No thumb found for category: %s' % cat
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
        