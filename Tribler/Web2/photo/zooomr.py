

import util.observer
import urllib
import re
import util.codec
import util.db

from util import download


ENCODING = "utf-8"

URL_SEARCH = "http://beta.zooomr.com/photos/tags/%s?page=%d"
RE_SEARCHITEM = r'<a href="/photos/([^/]*?/[^"]*?)"><img src="(http://static\.zooomr\.com.*?)"'

URL_ITEM="http://beta.zooomr.com/photos/%s"
RE_ITEMTITLE = r'<h1 id="phototitle.*?>(.*?)</h1>'
RE_ITEMBY = r'Uploaded on .*? by <a href=.*?>(.*?)</a>'
RE_TAGS = r'<div id="photos_tags"(.*?)</div>'
RE_TAGS2 = r'<a href=.*?>([^<>]*?)</a>[\n\t ]*</li>'

RE_NUMID = "[^/]*/(.*)"
RE_PHOTO = r'<li class="Stats"><a href="([^"]*?)">View all sizes</a></li>'
URL_DLPHOTO = "http://beta.zooomr.com%s"
RE_IMAGE = r"<p>Go ahead and take-down the photo's URL:</p>.*?<input.*?value=\"(.*?)\"" 

site = "zooomr.com"

class ZooomrSearch(util.db.ThreadedDBSearch):

    def __init__(self, query, db):
        nth = util.config.getOption("Zooomr", "threads")
        if nth is not None:
            nth = int(nth)
            util.db.ThreadedDBSearch.__init__(self, nth)
        else:
            util.db.ThreadedDBSearch.__init__(self)

        self.query = util.codec.encodehttpget(query)
        self.db = db
        self.pagecount = 1


    def parseItem(self, workitem):
        print "parseItem"
        id = workitem[0]

        if self.db.exists((site, id)):
            item = self.db.get((site, id))
        else:
            url = URL_ITEM % id
            print "getting URL", url
            conn = urllib.urlopen(url)
            itempage = conn.read()
            conn.close()

            title = re.findall(RE_ITEMTITLE, itempage)[0]
            title = unicode(title, ENCODING)
            title = util.codec.decodehtml(title)

            tags = re.findall(RE_TAGS, itempage, re.S)
            if len(tags) > 0:
                tags = re.findall(RE_TAGS2, tags[0], re.S)

            unicodetags = []
            for tag in tags:
                unicodetags.append(util.codec.decodehtml(unicode(tag, ENCODING)))
            
            by = re.findall(RE_ITEMBY, itempage, re.S)[0]
            by = unicode(by, ENCODING)
            by = util.codec.decodehtml(by)
   
            item = self.db.newItem((site, id), title, ZooomrDownload, unicodetags, by)

        if not item.hasPreview():
            preview = workitem[1]
            item.setPreview(preview)

        print "returning:", item
        return item

    def parseItempage(self):
        
        #print "Self.newpage = true"
        url = URL_SEARCH % (self.query, self.pagecount)
        print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read()
        pageconn.close()
        #print self.page

        items = re.findall(RE_SEARCHITEM, page, re.DOTALL)
        self.pagecount += 1

        return items


class ZooomrDownload(download.Download):

    def __init__(self, item):
        self.item = item
        download.Download.__init__(self, None, item.getPath())
        

    def run(self):
        try:
            url = URL_ITEM % self.item.getId()[1]
            conn = urllib.urlopen(url)
            page = conn.read()
            conn.close()

            photo = re.findall(RE_PHOTO, page)[0]
            url = URL_DLPHOTO % photo
            conn = urllib.urlopen(url)
            page = conn.read()
            conn.close()

            self.src = re.findall(RE_IMAGE, page, re.S)[0]
            
            download.Download.run(self)
        except:
            traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))

