# Written by Fabian van der Werf
# see LICENSE.txt for license information

from bsddb import dbshelve
import os
from util import observer
from util import download
from util import db
import base64
import re
import settings
import urllib
import wx


import flickr
import zooomr



class PhotoDB(db.DB):

    def __init__(self, dir, name):
        db.DB.__init__(self, dir, name)

    def onlineSearch(self, query):
        searches = []
        searches.append(flickr.FlickrSearch(query, self))
        searches.append(zooomr.ZooomrSearch(query, self))

        return db.CompoundDBSearch(searches)

    def newItem(self, id, *args, **kws):
        return db.DB.newItem(self, PhotoItem, id, *args, **kws)


class PhotoItem(db.Item):

    def __init__(self, id, dbname, path, name, dl, tags=[], by=""):

        db.Item.__init__(self, id, dbname, path, name, tags, dl)
        self.by = by

        self.content = os.path.join(self.path, "photo.jpg")
        self.preview = os.path.join(self.path, "preview.jpg")


    def setPreview(self, url):
        try:
            urllib.urlretrieve(url, self.preview)
        except:
            pass

    def getPreview(self):
        # Be sure to call this from the gui thread!
        # otherwise this may crash Xlib with
        # Xlib: unexpected async reply
        if not os.path.exists(self.preview):
            return None

        img = wx.Bitmap(self.preview, wx.BITMAP_TYPE_JPEG).ConvertToImage()

        return img

    def hasPreview(self):
        if not os.path.exists(self.preview):
            return False
        else:
            return True


    def getPreviewPath(self):
        return self.preview

    def getBy(self):
        return self.by


    def isStored(self):
        return os.path.exists(self.content)

    def getType(self):
        return "image"

    def getPath(self):
        return self.content

