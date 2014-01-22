# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker
# see LICENSE.txt for license information

import wx
import os
import cStringIO
import logging

from Tribler.Core.API import *

ICON_MAX_DIM = 80
SMALL_ICON_MAX_DIM = 32

logger = logging.getLogger(__name__)

class IconsManager:

    __single = None

    def __init__(self):

        if IconsManager.__single:
            raise RuntimeError("IconsManager is singleton")

        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

        self.guiUtility = GUIUtility.getInstance()
        self.guiImagePath = os.path.join(self.guiUtility.utility.getPath(), 'Tribler', 'Main', 'vwxGUI', 'images')

        self.defaults = {'PEER_THUMB': {}, 'TORRENT': {}, 'TORRENT_NEW': {}, 'MODIFICATION': {}, 'REVERTED_MODIFICATION': {}, 'COMMENT':{}, 'MARKING':{}}
        self.defaults['PEER_THUMB'][ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'defaultThumbPeer.png'))
        self.defaults['TORRENT'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'file_extension_tor.png'))
        self.defaults['TORRENT_NEW'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'file_extension_tornew.png'))
        self.defaults['MODIFICATION'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'edit_diff.png'))
        self.defaults['REVERTED_MODIFICATION'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'edit_reverted.png'))
        self.defaults['COMMENT'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'comments.png'))
        self.defaults['MARKING'][SMALL_ICON_MAX_DIM] = wx.Bitmap(os.path.join(self.guiImagePath, 'marking.png'))

        # Load country flags used by list_details
        self.country_flags = {}
        # For OS X, we do not use the country flags due to a wx bug
        if sys.platform != "darwin":
            flags_path = os.path.join(self.guiImagePath, 'flags')
            if os.path.isdir(flags_path):
                self.country_flags = dict([(flag.split(".")[0].lower(), wx.Bitmap(os.path.join(flags_path, flag), wx.BITMAP_TYPE_ANY)) for flag in os.listdir(flags_path) if flag.endswith('.png')])

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

    def get_default(self, name, dim=ICON_MAX_DIM):
        if dim not in self.defaults[name]:
            img = self.defaults[name][ICON_MAX_DIM].ConvertToImage()
            img.Rescale(dim, dim)

            self.defaults[name][dim] = wx.BitmapFromImage(img, -1)
        return self.defaults[name][dim]

    def load_wxBitmapByPeerId(self, peerid, dim=ICON_MAX_DIM):
        data = self.peer_db.getPeerById(peerid, keys=u'thumbnail')
        if data is None:
            return None
        else:
            return data2wxBitmap('image/jpeg', data, dim)


def data2wxImage(type, data, dim=ICON_MAX_DIM):
    try:
        if data is None:
            return None

        mi = cStringIO.StringIO(data)
        # St*pid wx says "No handler for image/bmp defined" while this
        # is the image handler that is guaranteed to always be there,
        # according to the docs :-(
        if type == 'image/bmp':
            im = wx.ImageFromStream(mi, wx.BITMAP_TYPE_BMP)
        else:
            im = wx.ImageFromStreamMime(mi, type)

        im.Rescale(dim, dim)
        return im
    except:
        logger.error('data2wxImage called (%s, %s)', repr(type), repr(dim))
        print_exc()
        return None


def data2wxBitmap(type, data, dim=ICON_MAX_DIM):
    try:
        im = data2wxImage(type, data, dim=dim)
        if im is None:
            bm = None
        else:
            bm = wx.BitmapFromImage(im, -1)

        return bm
    except:
        logger.error('data2wxBitmap called (%s, %s)', repr(type), repr(dim))
        print_exc()
        return None
