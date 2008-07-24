# Written by Fabian van der Werf
# see LICENSE.txt for license information

import threading
import util.observer
import urllib
import settings
import re
import util.codec
import util.db

from util import download


site = "flickr.com"


class FlickrSearch(util.db.ThreadedDBSearch):

    def __init__(self, query, db):

        nth = util.config.getOption("Flickr", "threads")
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
            url = settings.URL_ITEM % id
            print "getting URL", url
            conn = urllib.urlopen(url)
            itempage = conn.read()
            conn.close()

            title = re.findall(settings.RE_ITEMTITLE, itempage)[0]
            title = unicode(title, settings.ENCODING)
            title = util.codec.decodehtml(title)
            #print "title", title

            tags = re.findall(settings.RE_ITEMTAGS, itempage)
            unicodetags = []
            for tag in tags:
                unicodetags.append(util.codec.decodehtml(unicode(tag, settings.ENCODING)))
            
            by = re.findall(settings.RE_ITEMBY, itempage, re.S)[0]
            by = unicode(by, settings.ENCODING)
            by = util.codec.decodehtml(by)
   
            item = self.db.newItem((site, id), title, FlickrDownload, unicodetags, by)

        if not item.hasPreview():
            preview = workitem[1]
            item.setPreview(preview)

        print "returning:", item
        return item

    def parseItempage(self):
        
        #print "Self.newpage = true"
        url = settings.URL_SEARCH % (self.query, self.pagecount)
        print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read()
        pageconn.close()
        #print self.page

        items = re.findall(settings.RE_SEARCHITEM, page, re.DOTALL)
        self.pagecount += 1

        return items


class FlickrDownload(download.Download):

    def __init__(self, item):
        self.item = item
        download.Download.__init__(self, None, item.getPath())
        

    def run(self):
        try:
            num = re.findall(settings.RE_NUMID, self.item.getId()[1])
            url = settings.URL_DLPHOTO % num[0]

            conn = urllib.urlopen(url)
            page = conn.read()
            conn.close()

            self.src = re.findall(settings.RE_ORGSIZE, page)[0]
            
            download.Download.run(self)
        except:
            traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))

        
        

class OldFlickrSearch(threading.Thread, util.observer.Subject):

    def __init__(self, query, db):
        threading.Thread.__init__(self)
        self.setName( "OldFlickrSearch"+self.getName() )
        self.setDaemon(True)
        util.observer.Subject.__init__(self)
        self.__count = 0
        self.__quit = threading.Event()
        self.__cond = threading.Condition()
        self.query = util.codec.encodehttpget(query)
        self.db = db
        self.newpage = True
        self.pagecount = 1

    def run(self):

        while True:

            self.__cond.acquire()
            if self.__quit.isSet():
                self.__cond.release()
                return

            if self.__count == 0:
                self.__cond.wait()

            # I may be woken up to quit
            if self.__quit.isSet():
                self.__cond.release()
                return

            self.__cond.release()

            item = self.getResultItem()

            self.__cond.acquire()
            self.__count -= 1
            self.__cond.release()

            self.notify(item)
            if item == None:
                return


    def getResultItem(self):
        #print "getResultItem"

        if self.newpage:
            #print "Self.newpage = true"
            url = settings.URL_SEARCH % (self.query, self.pagecount)
            print "Retrieving url", url
            pageconn = urllib.urlopen(url)
            self.page = pageconn.read()
            pageconn.close()
            #print self.page
            self.getItems(self.page)
            self.itemnum = len(self.items)
            if self.itemnum == 0:
                return None

            self.itemindex = 0
            self.newpage = False
            #print "num", self.itemnum

        item = self.getItem()

        self.itemindex += 1
        if self.itemindex == self.itemnum:
            # last item on page
            self.newpage = True
            self.pagecount += 1

        print "getResultItem", item
        return item

    def getItems(self, page):
        self.items = re.findall(settings.RE_SEARCHITEM, page, re.DOTALL)

    def getItem(self):

        id = self.items[self.itemindex][0]
        if self.db.exists(id):
            item =  self.db.get(id)
        else:
            url = settings.URL_ITEM % id
            print "getting URL", url
            conn = urllib.urlopen(url)
            itempage = conn.read()
            conn.close()

            title = re.findall(settings.RE_ITEMTITLE, itempage)[0]
            title = unicode(title, settings.ENCODING)
            title = util.codec.decodehtml(title)
            #print "title", title

            tags = re.findall(settings.RE_ITEMTAGS, itempage)
            unicodetags = []
            for tag in tags:
                unicodetags.append(util.codec.decodehtml(unicode(tag, settings.ENCODING)))
            
            by = re.findall(settings.RE_ITEMBY, itempage, re.S)[0]
            by = unicode(by, settings.ENCODING)
            by = util.codec.decodehtml(by)
   
            #print by

            item = flickr.FlickrItem((site, id), title, unicodetags, by)
            #print item
            self.db.update(item)

        if not item.hasPreview():
            preview = self.items[self.itemindex][1]
            item.setPreview(preview)

        return item

    def getMore(self, num):
        self.__cond.acquire()
        self.__count += num
        self.__cond.notify()
        self.__cond.release()


    def quit(self):
        self.__cond.acquire()
        self.__quit.set()
        self.__cond.notify()
        self.__cond.release()

