

import copy
import os
import subprocess
import re
import urllib
import video
import settings

import util.codec
import util.db

from util import download

site = "revver.com"

ENCODING = "utf-8"

URL_SEARCH = "http://one.revver.com/find/keywords/%s/page/%d"
RE_SEARCHITEM = r'<div class="video">.*?<a href="/watch/([0-9]*)".*?>.*?<img class="thumb" *src="(.*?)".*?</div>'

RE_TAG = r'<ul id="video_keywords".*?>(.*?)</ul>'
RE_TAG2 = r'<li><a href=.*?>(.*?)</a></li>'

RE_NAME = r'<title>Revver : (.*?)</title>'
URL_WATCH = "http://one.revver.com/watch/%s"
URL_DL_VIDEO = "http://media.revver.com/qt;download/%s.mov"
VIEW_URL = "http://revver.com/watch/%s"



class RevverSearch(util.db.ThreadedDBSearch):

    def __init__(self, query, db):
        nth = util.config.getOption("Revver", "threads")
        if nth is not None:
            nth = int(nth)
            util.db.ThreadedDBSearch.__init__(self, nth)
        else:
            util.db.ThreadedDBSearch.__init__(self)

        self.query = util.codec.encodehttpget(query)
        self.db = db
        self.pagecount = 1
    

    def parseItem(self, workitem):

        id = workitem[0]
        if self.db.exists((site, id)):
            item = self.db.get((site, id))
        else:
            url = URL_WATCH % id 
            #print "getting URL", url
            conn = urllib.urlopen(url)
            itempage = conn.read()
            conn.close()

            name = re.findall(RE_NAME, itempage)
            if len(name) == 0:
                return None
            #print name[0]
            name = unicode(name[0], ENCODING)
            name = util.codec.decodehtml(name)
            #print name

            category = unicode("Misc")

            tags = re.findall(RE_TAG, itempage, re.S)
            if len(tags) > 0:
                tags = re.findall(RE_TAG2, tags[0])
            
            #TODO: seperate tags
            unicodetags = []
            for tag in tags:
                if len(tags) == 0:
                    continue
                unicodetags.append(unicode(tag, ENCODING))

            item = self.db.newItem((site, id), name, RevverDownload, unicodetags, category)
            
        if not item.hasPreview():
            preview = workitem[1]
            item.setPreview(preview)

        util.log.log("Revver: returning " + item.getName())
        return item

    def parseItempage(self):

        #print "Self.newpage = true"
        url = URL_SEARCH % (self.query, self.pagecount)
        #print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read()
        pageconn.close()
        #print self.page
        items = re.findall(RE_SEARCHITEM, page, re.S)
        self.pagecount += 1
        
        if len(items) == 0:
            util.log.log("Revver: no more items")


        return items


class RevverDownload(download.Download):

    def __init__(self, item):
        self.item = item
        download.Download.__init__(self, None, item.getPath(), RevverTranscode)

    def run(self):
        try:
            self.src = URL_DL_VIDEO % self.item.getId()[1]
            download.Download.run(self)
        except:
            traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))
            

#Revver videos have multiple video tracks, we want track 6, audio is on track 7
VIDDECODE_CMD = [settings.FFMPEG_FILE, "-i", None, "-vcodec", "mpeg2video", "-r", "30", "-ar", "44100", "-y", "-sameq", None, "-map", "0:6", "-map", "0:7"]
VIDDECODE_CMD_IO = (2, 11)

def RevverTranscode(input, output):
    tmpout = os.path.join(os.path.dirname(output), "." + os.path.basename(output))

    cmd = copy.deepcopy(VIDDECODE_CMD)
    cmd[VIDDECODE_CMD_IO[0]] = input
    cmd[VIDDECODE_CMD_IO[1]] = tmpout
    print "Doing: ", cmd
    proc = subprocess.Popen(cmd)
    if proc.wait() != 0:
        # maybe ffmpeg failed because there is no audio track
        # remove last stream map and retry
        cmd.pop(len(cmd) - 1)
        cmd.pop(len(cmd) - 1)
        print "Doing: ", cmd
        proc = subprocess.Popen(cmd)
        proc.wait()


    os.rename(tmpout, output)

