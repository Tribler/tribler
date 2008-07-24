# Written by Fabian van der Werf
# see LICENSE.txt for license information

from bsddb import dbshelve

import copy
import os
import os.path
import re
import shutil
import subprocess
import traceback
import urllib

import settings
from Tribler.Web2.util import db
from Tribler.Web2.util.log import log



mux = "avi"

class VideoDB(db.DB):
    def __init__(self, dir, name):
        db.DB.__init__(self, dir, name)

    def onlineSearch(self, query):
        searches = [
                revver.RevverSearch(query, self),
                youtube.YoutubeSearch(query, self),
                liveleak.LiveLeakSearch(query, self)
                ]


        return db.CompoundDBSearch(searches)


    def newItem(self, id, *args, **kws):
        return db.DB.newItem(self, VideoItem, id, *args, **kws)
       

class VideoItem(db.Item):

    def __init__(self, id, name, dl, tags=[], category=[]):
        db.Item.__init__(self, id, name, tags, dl)
        self.category = category

    def getCategory(self):
        return self.category


    def setPreview(self, url):
        try:
            conn = urllib.urlopen(url)
            self.preview = conn.read()

            if len(self.preview) == 0:
                raise RuntimeException()
        except:
            try:
                del self.preview
            except:
                pass


    def hasPreview(self):
        try:
            self.preview
            return True
        except:
            return False


    def isStored(self):
        #print "is stored ", os.path.exists(self.item)
        return os.path.exists(self.content)


    def getType(self):
        return "video"


    def getPath(self):
        return self.content


    def getPreview(self):
        return self.preview


def VideoTranscode(input, output):
    tmpout = os.path.join(os.path.dirname(output), "." + os.path.basename(output))

    cmd = copy.deepcopy(settings.VIDDECODE_CMD)
    cmd[settings.VIDDECODE_CMD_IO[0]] = input
    cmd[settings.VIDDECODE_CMD_IO[1]] = tmpout
    log("Video transcoder: doing: " + str(cmd))
    proc = subprocess.Popen(cmd)
    rcode = proc.wait()

    if rcode == 0 and os.path.exists(tmpout):
        shutil.move(tmpout, output)
    else:
        os.remove(tmpout)
        raise RuntimeError("Transcoding failed")
        





