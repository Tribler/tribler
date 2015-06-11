#
#
# This GuiImsageBuffer loads and buffers the pictures used by GUI in
# the type of wx.Bitmap.
#
import wx
from wx.lib.embeddedimage import PyEmbeddedImage

import os
import os.path
import sys
import logging
import cStringIO

from Tribler.Main.vwxGUI import warnWxThread

ICON_MAX_DIM = 80
SMALL_ICON_MAX_DIM = 32

logger = logging.getLogger(__name__)


class GuiImageManager(object):

    __single = None

    def __init__(self, tribler_path):
        if GuiImageManager.__single:
            raise RuntimeError("GuiImageManager is singleton")

        object.__init__(self)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.IMAGE_SUBDIR = os.path.join(tribler_path, u"Tribler", u"Main", u"vwxGUI", u"images")
        self.DEFAULT_SUBDIR = os.path.join(self.IMAGE_SUBDIR, u"default")
        self.FLAG_SUBDIR = os.path.join(self.IMAGE_SUBDIR, u"flags")

        # load all images
        self._default_dict = {}
        self._flag_dict = {}
        self._other_dict = {}

        self._load_all_images()

        self._icons = {}

    @staticmethod
    def getInstance(*args, **kw):
        if GuiImageManager.__single is None:
            GuiImageManager.__single = GuiImageManager(*args, **kw)
        return GuiImageManager.__single

    @staticmethod
    def delInstance(*args, **kw):
        GuiImageManager.__single = None

    @warnWxThread
    def _load_all_images(self):
        """
        Loads and initiailizes all images, including:
        (1) default images (don't know why they are called default),
            they need to be rescaled to both large and small sizes.
        (2) country flags.
        (3) other images.
        """
        self._logger.debug(u"Loading images.")

        self._init_default_images()
        self._init_flag_images()

    def _init_default_images(self):
        """
        Loads the default images from files.
        """
        self._logger.debug(u"Start loading default images.")

        DEFAULT_IMAGE_INFO_LIST = [
            ("PEER_THUMB",            u'defaultThumbPeer.png'),
            ("TORRENT",               u'file_extension_tor.png'),
            ("TORRENT_NEW",           u'file_extension_tornew.png'),
            ("MODIFICATION",          u'edit_diff.png'),
            ("REVERTED_MODIFICATION", u'edit_reverted.png'),
            ("COMMENT",               u'comments.png'),
            ("MARKING",               u'marking.png'),
        ]
        self._default_dict = {
            "PEER_THUMB": {},
            "TORRENT": {},
            "TORRENT_NEW": {},
            "MODIFICATION": {},
            "REVERTED_MODIFICATION": {},
            "COMMENT": {},
            "MARKING": {}
        }
        for default_image_info in DEFAULT_IMAGE_INFO_LIST:
            name = default_image_info[0]
            filename = default_image_info[1]

            image_path = os.path.join(self.DEFAULT_SUBDIR, filename)
            if not os.path.exists(image_path):
                msg = u"Default image is not a file %s", image_path
                self._logger.error(msg)
                raise Exception(msg)
            if not os.path.isfile(image_path):
                msg = u"Default image is not a file %s", image_path
                self._logger.error(msg)
                raise Exception(msg)

            bitmap = wx.Bitmap(image_path)
            big_image = bitmap.ConvertToImage()
            small_image = big_image.Copy()
            big_image = big_image.Rescale(ICON_MAX_DIM, ICON_MAX_DIM)
            small_image = small_image.Rescale(SMALL_ICON_MAX_DIM, SMALL_ICON_MAX_DIM)

            self._default_dict[name][ICON_MAX_DIM] = wx.BitmapFromImage(big_image)
            self._default_dict[name][SMALL_ICON_MAX_DIM] = wx.BitmapFromImage(small_image)

    def _init_flag_images(self):
        """
        Loads the country flags from files.
        """
        self._logger.debug(u"Start loading country flag images.")

        if not os.path.exists(self.FLAG_SUBDIR):
            msg = u"Flags dir doesn't exist %s" % self.FLAG_SUBDIR
            self._logger.error(msg)
            raise Exception(msg)
        if not os.path.isdir(self.FLAG_SUBDIR):
            msg = u"Not a dir %s" % self.FLAG_SUBDIR
            self._logger.error(msg)
            raise Exception(msg)

        # For OS X, we do not use the country flags due to a wx bug
        if sys.platform != "darwin":
            for flag in os.listdir(self.FLAG_SUBDIR):
                flag_path = os.path.join(self.FLAG_SUBDIR, flag)

                if not os.path.isfile(flag_path):
                    msg = u"Not a file %s" % flag_path
                    self._logger.error(msg)
                    continue
                
                if not flag.endswith(u".png"):
                    msg = u"Not a PNG file %s" % flag_path
                    self._logger.error(msg)
                    continue

                bitmap = wx.Bitmap(flag_path, wx.BITMAP_TYPE_ANY)

                # Size check for flag images.
                if bitmap.GetWidth() != 16 or bitmap.GetHeight() != 11:
                    msg = u"Country flag[%s] is of size [%dx%d], NOT [%dx%d]." %\
                          (flag, bitmap.GetWidth(), bitmap.GetHeight(), 16, 11)
                    self._logger.error(msg)
                    raise Exception(msg)

                self._flag_dict[os.path.splitext(flag)[0].lower()] = bitmap

    @warnWxThread
    def getImage(self, name, dimension=None):
        """
        All other modules should use this method to get an image.
        """
        image = None

        # default image
        if name in self._default_dict:
            dimension = dimension or ICON_MAX_DIM
            image = self._default_dict[name].get(dimension, None)
            if image is None:
                msg = u"Default image is not loaded [%s]." % name
                self._logger.error(msg)
                raise Exception(msg)

        # other image
        else:
            image = self._other_dict.get(name, None)
            if image is None:
                self._logger.debug(u"Trying to load image [%s].", name)
                # lazy load
                image_path = os.path.join(self.IMAGE_SUBDIR, name)
                if not os.path.exists(image_path):
                    msg = u"Image[%s] doesn't exist." % image_path
                    self._logger.error(msg)
                    raise Exception(msg)
                elif not os.path.isfile(image_path):
                    msg = u"Image[%s] is not a file." % image_path
                    self._logger.error(msg)
                    raise Exception(msg)
                else:
                    image = wx.Bitmap(image_path, wx.BITMAP_TYPE_ANY)
                    self._other_dict[name] = image

        return image

    @warnWxThread
    def getCountryFlagDict(self):
        """
        Gets the country flag dictionary.
        """
        return self._flag_dict

    @warnWxThread
    def getPeerThumbnail(self, raw_data, dim=ICON_MAX_DIM):
        """
        Gets the peer thumbnail.
        """
        if raw_data is None:
            return None

        return data2wxBitmap("image/jpeg", cStringIO.StringIO(raw_data), dim)

    @warnWxThread
    def getBitmap(self, parent, type, background, state):
        assert isinstance(background, wx.Colour), u"we require a wx.colour object here, got %s" % type(background)
        if isinstance(background, wx.Colour):
            background = background.Get()
        else:
            background = wx.Brush(background).GetColour().Get()

        icons = self._icons.setdefault(type, {})
        if background not in icons:
            icons.setdefault(background, {})

            def fixSize(bitmap, width, height):
                if width != bitmap.GetWidth() or height != bitmap.GetHeight():

                    bmp = wx.EmptyBitmap(width, height)
                    dc = wx.MemoryDC(bmp)
                    dc.SetBackground(wx.Brush(background))
                    dc.Clear()

                    offset_x = (width - bitmap.GetWidth()) / 2
                    offset_y = (height - bitmap.GetHeight()) / 2

                    dc.DrawBitmap(bitmap, offset_x, offset_y)
                    dc.SelectObject(wx.NullBitmap)
                    del dc

                    return bmp
                return bitmap

            # create both icons
            icons[background][0] = self.__createBitmap(parent, background, type, 0)
            icons[background][1] = self.__createBitmap(parent, background, type, 1)

            width = max(icons[background][0].GetWidth(), icons[background][1].GetWidth())
            height = max(icons[background][0].GetHeight(), icons[background][1].GetHeight())

            icons[background][0] = fixSize(icons[background][0], width, height)
            icons[background][1] = fixSize(icons[background][1], width, height)

        if state not in icons[background]:
            icons[background][state] = self.__createBitmap(parent, background, type, state)
        return icons[background][state]

    def drawBitmap(self, name, size, font):
        bitmap = None
        if name == "no-thumbnail":
            bitmap = wx.EmptyBitmap(*size)
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.Brush(wx.Colour(230, 230, 230)))
            dc.Clear()

            font.SetPointSize(font.GetPointSize() + 4)
            dc.SetFont(font)
            dc.SetTextForeground(wx.Colour(100, 100, 100))
            dc.DrawLabel('No thumbnail\navailable', (0, 0) + size,
                         alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)
            dc.SelectObject(wx.NullBitmap)
            del dc
        return bitmap

    def __createBitmap(self, parent, background, type, state):
        if state == 1:
            if type == 'tree':
                state = wx.CONTROL_EXPANDED
            elif type == 'checkbox':
                state = wx.CONTROL_CHECKED
            else:
                state = wx.CONTROL_PRESSED

        # There are some strange bugs in RendererNative, the alignment is incorrect of the drawn images
        # Thus we create a larger bmp, allowing for borders
        bmp = wx.EmptyBitmap(24, 24)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()

        # max size is 16x16, using 4px as a border
        if type == 'checkbox':
            wx.RendererNative.Get().DrawCheckBox(parent, dc, (4, 4, 16, 16), state)

        elif type == 'tree':
            wx.RendererNative.Get().DrawTreeItemButton(parent, dc, (4, 4, 16, 16), state)

        elif type == 'arrow':
            arrow = PyEmbeddedImage(
                "iVBORw0KGgoAAAANSUhEUgAAAAcAAAAECAYAAABCxiV9AAAAAXNSR0IArs4c6QAAAARnQU1B"
                "AACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAadEVYdFNvZnR3YXJlAFBhaW50Lk5F"
                "VCB2My41LjEwMPRyoQAAADFJREFUGFdjYGBg+I8Tf/jwQRSbJFCckQFIcIEZSCYA+RxAzAyS"
                "BGFGmAIgzQTlMwAAOBAx4jYP9TUAAAAASUVORK5CYII=")
            return arrow.GetBitmap()

        elif type == 'slider':
            slider = PyEmbeddedImage(
                "iVBORw0KGgoAAAANSUhEUgAAAAkAAAAICAYAAAArzdW1AAAAAXNSR0IArs4c6QAAAARnQU1B"
                "AACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAadEVYdFNvZnR3YXJlAFBhaW50Lk5F"
                "VCB2My41LjEwMPRyoQAAAOZJREFUKFM9j71rg1AUxd9LIUuX/gvZRAcRdfBjqp+jIoKYoZBQ"
                "UdEO+pysa6f+mZ0ayJCWri/nhcYLP7icc+6BS3Rd/3Jdl6dpyrMsW0mShNu2zU3T/CaKovC2"
                "bV+naXoGOTiAPRihN8Inqqryuq6Nvu83gALyD4W+Ez6RJOmnKIrPYRieGGMbNBCwxU7Lspxk"
                "Wf4jvu83mqadUP0xz/MDoIKu65hhGGf4jIgJw/CABy7jOPbLslC07BG4BEHwcguIyfN8G8dx"
                "4zjOb1VVR3x7jqKoFvoaui+4fLcs6+R53ttdQ/vjFXw5XtzmpGeLAAAAAElFTkSuQmCC")
            return slider.GetBitmap()

        dc.SelectObject(wx.NullBitmap)
        del dc

        # determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        return bmp.GetSubBitmap(bb)


@warnWxThread
def data2wxBitmap(type, data, dimension=ICON_MAX_DIM):
    """
    Creates a wx.Bitmap from a given raw data.
    """
    bitmap = None
    try:
        string_io = cStringIO.StringIO(data)

        if type == "image/bmp":
            image = wx.ImageFromStream(string_io, wx.BITMAP_TYPE_BMP)
        else:
            image = wx.ImageFromStreamMime(string_io, type)

        image.Rescale(dimension, dimension)
        bitmap = wx.BitmapFromImage(image)
    except:
        logger.exception('data2wxBitmap() failed (%s, %s)', repr(type), repr(dimension))

    return bitmap
