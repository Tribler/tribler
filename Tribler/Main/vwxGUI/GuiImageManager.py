#
#
# This GuiImsageBuffer loads and buffers the pictures used by GUI in
# the type of wx.Bitmap.
#
import wx
import os
import os.path
import sys
import logging
import cStringIO

from Tribler.Core.simpledefs import NTFY_PEERS


ICON_MAX_DIM = 80
SMALL_ICON_MAX_DIM = 32


class GuiImageManager(object):

    __single = None

    def __init__(self, tribler_path):
        if GuiImageManager.__single:
            raise RuntimeError("GuiImageManager is singleton")

        object.__init__(self)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.IMAGE_SUBDIR = os.path.join(tribler_path, u"Tribler", u"Main", u"vwxGUI", u"images")
        self.DEFAULT_SUBDIR = os.path.join(self.IMAGE_SUBDIR, u"default")
        self.FLAG_SUBDIR    = os.path.join(self.IMAGE_SUBDIR, u"flags")

        # load all images
        self._default_dict = {}
        self._flag_dict    = {}
        self._other_dict   = {}
        self.__loadAllImages()

        #self._peer_db = gui_utility.utility.session.open_dbhandler(NTFY_PEERS)


    @staticmethod
    def getInstance(*args, **kw):
        if GuiImageManager.__single is None:
            GuiImageManager.__single = GuiImageManager(*args, **kw)
        return GuiImageManager.__single


    @staticmethod
    def delInstance(*args, **kw):
        GuiImageManager.__single = None


    def __loadAllImages(self):
        """
        Loads and initiailizes all images, including:
        (1) default images (don't know why they are called default),
            they need to be rescaled to both large and small sizes.
        (2) country flags.
        (3) other images.
        """
        self._logger.debug(u"Loading images.")

        self.__initDefaultImages()
        self.__initFlagImages()
        self.__initOtherImages()


    def __initDefaultImages(self):
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
            "COMMENT":{},
            "MARKING":{}
        }
        for default_image_info in DEFAULT_IMAGE_INFO_LIST:
            name     = default_image_info[0]
            filename = default_image_info[1]

            image_path = os.path.join(self.DEFAULT_SUBDIR, filename)
            if not os.path.exists(image_path):
                self._logger.warn(u"Default image doesn't exist %s", image_path)
                continue
            if not os.path.isfile(image_path):
                self._logger.warn(u"Default image is not a file %s", image_path)
                continue

            bitmap = wx.Bitmap(image_path)
            image = bitmap.ConvertToImage()
            big_image = image.Rescale(ICON_MAX_DIM, ICON_MAX_DIM)
            small_image = image.Rescale(SMALL_ICON_MAX_DIM, SMALL_ICON_MAX_DIM)

            self._default_dict[name][ICON_MAX_DIM] = wx.BitmapFromImage(big_image)
            self._default_dict[name][SMALL_ICON_MAX_DIM] = wx.BitmapFromImage(small_image)


    def __initFlagImages(self):
        """
        Loads the country flags from files.
        """
        self._logger.debug(u"Start loading country flag images.")

        if not os.path.exists(self.FLAG_SUBDIR):
            self._logger.warn(u"Flags dir doesn't exist %s", self.FLAG_SUBDIR)
            return
        if not os.path.isdir(self.FLAG_SUBDIR):
            self._logger.warn(u"Not a dir %s", self.FLAG_SUBDIR)
            return

        # For OS X, we do not use the country flags due to a wx bug
        if sys.platform != "darwin":
            for flag in os.listdir(self.FLAG_SUBDIR):
                flag_path = os.path.join(self.FLAG_SUBDIR, flag)

                if not os.path.isfile(flag_path):
                    continue
                if not flag.endswith(u".png"):
                    self._logger.warn(u"SKIP, Not a PNG file %s", flag_path)
                    continue

                bitmap = wx.Bitmap(flag_path, wx.BITMAP_TYPE_ANY)

                # Size check for flag images.
                if bitmap.GetWidth() != 16 or bitmap.GetHeight() != 11:
                    self._logger.warn(u"Country flag[%s] is of size [%dx%d], NOT [%dx%d].",
                        flag, bitmap.GetWidth(), bitmap.GetHeight(), 16, 11)
                self._flag_dict[os.path.splitext(flag)[0].lower()] = bitmap


    def __initOtherImages(self):
        """
        Loads other images.
        """
        self._logger.debug(u"Start loading other images.")

        if not os.path.exists(self.IMAGE_SUBDIR):
            self._logger.warn(u"Image dir doesn't exist %s", self.IMAGE_SUBDIR)
            return
        if not os.path.isdir(self.IMAGE_SUBDIR):
            self._logger.warn(u"Not a dir %s", self.IMAGE_SUBDIR)
            return

        for image_file in os.listdir(self.IMAGE_SUBDIR):
            image_path = os.path.join(self.IMAGE_SUBDIR, image_file)

            if not os.path.isfile(image_path):
                continue
            if not image_path.endswith(u".png"):
                self._logger.warn(u"SKIP, Not a PNG file %s", image_path)
                continue

            bitmap = wx.Bitmap(image_path, wx.BITMAP_TYPE_ANY)

            self._other_dict[image_file] = bitmap


    def getDefaultImage(self, name, dimension=ICON_MAX_DIM):
        """
        Gets a default image.
        """
        assert isinstance(name, str) or isinstance(name, unicode), \
            u"name is of type %s, value %s" % (type(name), name)

        image = None
        if name in self._default_dict:
            image = self._default_dict[name].get(dimension, None)

        if image is None:
            self._logger.warn(u"Default image is not loaded [%s].", name)

        return image


    def getCountryFlagDict(self):
        """
        Gets the country flag dictionary.
        """
        return self._flag_dict


    def getOtherImage(self, name):
        """
        Gets an other image.
        """
        image = self._other_dict.get(name, None)
        if image is None:
            self._logger.warn(u"Other image is not loaded [%s].", name)

        return image


    def getPeerThumbnail(self, peer_id, dim=ICON_MAX_DIM):
        """
        Gets the peer thumbnail.
        """
        data = self._peer_db.getPeerById(peerid, keys=u"thumbnail")
        if data is None:
            return None

        string_io = cStringIO.StringIO(data)


        return data2wxBitmap("image/jpeg", data, dim)


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