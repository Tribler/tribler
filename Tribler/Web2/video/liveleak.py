
import httplib
import re
import urllib
import traceback

import video
from Tribler.Web2.util import codec
from Tribler.Web2.util import db
from Tribler.Web2.util import download
from Tribler.Web2.util.log import log

DEBUG = False

ENCODING = "iso-8859-1"

site = "liveleak.com"

URL_SEARCH = "http://www.liveleak.com/browse?all&q=%s&page=%d"
RE_SEARCHITEM = r'<a href="view\?i=([^"]*?)" *><img src="([^"]*?)".*?Type:(.*?)\|'

RE_NAME_OLD = r'<title>LiveLeak.com - (.*?)</title>'
RE_NAME = r'<span class="mediatitle_big">(.*?)</span>'
RE_CAT = r'<strong>In:</strong>.*?<a href=".*?>(.*?)</a>'
RE_TAG  = r'<td align="left"><strong>Tags:</strong>(.*?)</td>'
RE_TAG2 = r'<a href=".*?>(.*?)</a>'
RE_VIEWS = r'<td align="left"><strong>Views:</strong>(.*?)</td>'
RE_DATE = r'<strong>Added</strong>:(.*?)</td>'
RE_DESC = r'<tr valign="top">.*?<td colspan="2">(.*?)<' 
RE_TIME = r'Video \((.*?) Secs'

URL_WATCH = "http://www.liveleak.com/view?i=%s&o=1"
VIEW_URL = "http://www.liveleak.com/view?i=%s"
RE_DL_VIDEO = r'<embed[^>]*?src="([^"]*?)"'
RE_DL_VIDEO2 = r'<object id="MediaPlayer1".*?>.*?<param name="FileName" value="(.*?)".*?</object>'


class LiveLeakSearch(db.ThreadedDBSearch):

    def __init__(self, query):
        db.ThreadedDBSearch.__init__(self)

        self.query = codec.encodehttpget(query)
        self.db = db
        self.pagecount = 1

    def parseItem(self, workitem):

        item = {}

        id = workitem[0]
        item['infohash'] = id

        url = URL_WATCH % id 
        #print "getting URL", url
        conn = urllib.urlopen(url)
        itempage = conn.read()
        conn.close()

        #downloadability check
        src = re.findall(RE_DL_VIDEO, itempage, re.S | re.I)
        if  len(src) != 1:
            src = re.findall(RE_DL_VIDEO2, itempage, re.S | re.I)
            if len(src) != 1:
                #util.log.log("Liveleak: downloadability check failed")
                return None

        #if viddl[0].endswith("mpg"):
            #We don't do mpg movies, ffmpeg hangs on those
            #return None

        name = re.findall(RE_NAME, itempage)
        if len(name) == 0:
            return None
        #print name[0]
        name = unicode(name[0], ENCODING)
        name = codec.decodehtml(name)
        #print name
        item['content_name'] = name

        category = re.findall(RE_CAT, itempage, re.S)
        if len(category) == 0:
            category = unicode("Misc")
        else:
            category = unicode(category[0], ENCODING)
            category = codec.decodehtml(category)
            category = category.strip()
        item['category'] = category

        tags = re.findall(RE_TAG, itempage)
        if len(tags) > 0:
            tags = re.findall(RE_TAG2, tags[0])
        unicodetags = []
        for tag in tags:
            unicodetags.append(unicode(tag, ENCODING))
        item['tags'] = tags

        conn = urllib.urlopen(workitem[1])
        item['preview'] = conn.read()

        try:
            desc = re.findall(RE_DESC, itempage, re.S)[0]
            if desc.strip() == '':
                raise RuntimeError()
            item['description'] = "from liveleak.com: " + desc
        except:
            item['description'] = "from liveleak.com"
            
        item['web2'] = True
        item['url'] = src[0]
        views = int(re.findall(RE_VIEWS, itempage)[0].strip())
        item['views'] = views
        date = re.findall(RE_DATE, itempage, re.S)
        item['info'] = { 'creation date' : LiveLeakDateParser(date[0]) }
        item['status'] = 'good'
        item['seeder'] = 1
        item['leecher'] = 1

        try:   
            time = divmod(int(re.findall(RE_TIME, workitem[2])[0].strip()), 60)
            item['length'] = ("%02d" % time[0]) + ":" + ("%02d" % time[1])
        except:
            item['length'] = "--:--"
    

        if item != None:
            log("Liveleak: returning " + item['content_name'])
        else:
            log("Liveleak: returning None")

        return item
        

    def parseItempage(self):
        
        #import pdb
        #pdb.set_trace()
        #print "Self.newpage = true"
        url = URL_SEARCH % (self.query, self.pagecount)
        #print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read()
        pageconn.close()
        #print self.page
        items = re.findall(RE_SEARCHITEM, page, re.S)
        if len(items) == 0:
            log("Liveleak: no more items")

        self.pagecount += 1

        return items


class LiveLeakDownload(download.Download):

    def __init__(self, item):
        self.item = item
        download.Download.__init__(self, None, item.getPath(), video.VideoTranscode)

    def run(self):
        try:
            conn = urllib.urlopen(URL_WATCH % self.item.getId()[1])
            page = conn.read()
            conn.close()

            self.src = re.findall(RE_DL_VIDEO, page, re.S | re.I)[0]

            #Try to use the flash video version
            #Because original versions may be wmv2 videos
            #which are not fully supported by FFmpeg
            host = re.findall("http://([^/]*)/.*", self.src)
            host = host[0]
            conn = httplib.HTTPConnection(host)
            conn.request("HEAD", self.src + ".flv")
            response = conn.getresponse()

            if response.status >= 200 and response.status < 300 and int(response.getheader("content-length")) > 0:
                log("Liveleak: using flash video version: " + self.src + ".flv")
                self.src += ".flv"
            else:
                log("Liveleak: using original version: " + self.src)

            
            download.Download.run(self)
        except:
            if DEBUG:
                traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))
            

import datetime
import time

months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec" ]

def LiveLeakDateParser(strdate):
    try:
        _strdate = strdate.strip()

        [smonth, day, year] = _strdate.split()

        month = months.index(smonth.lower()) + 1
        if month < 1:
            raise RuntimeError()
        day = int(filter(str.isdigit, day))
        year = int(year)

        return time.mktime(datetime.date(year, month, day).timetuple())
        
    except:
        return None

