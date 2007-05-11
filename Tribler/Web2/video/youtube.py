

import re
import urllib
import traceback

import video
from Tribler.Web2.util import codec
from Tribler.Web2.util import db
from Tribler.Web2.util.log import log
from Tribler.Web2.util import download


ENCODING = "utf-8"

site = "youtube.com"


RE_SEARCHITEM = r"<a href=\"/watch\?v=(.*?)\".*?><img src=\"(.*?)\".*?></a>.*?<span class=\"runtime\">(.*?)</span>"
RE_TAG  = r'<meta name="keywords" content="(.*?)">'
RE_TAG2 = r'([^ ,]+)'
RE_CAT  = r'<a href="/browse\?s=.*?Video\+Category\+Link.*?>(.*?)</a>' 
RE_NAME = r'<title>YouTube - (.*?)</title>'
RE_DESC = r'<meta name="description" content="(.*?)">'
RE_VIEWS = r'Views: <span class="statVal">(.*?)</span>'
RE_DATE = r'<div id="userInfoDiv">.*?<span class="smallLabel">Added</span>.*?<b class="smallText">(.*?)</b><br>'

URL_WATCH = "http://www.youtube.com/watch?v=%s"
URL_DL_VIDEO = 'http://www.youtube.com/get_video?video_id=%s&t=%s'
RE_VIDEOURL = r'player2\.swf\?video_id=([^&]+?)&.*?&t=([^&"]+?)(?:&|")'

URL_SEARCH =  "http://www.youtube.com/results?search_type=videos&search_query=%s&search_sort=relevance&search_category=0&page=%d"

RE_RESULTS_HASNEXT = r'class="pagerNotCurrent">Next</a>'


class YoutubeSearch(db.ThreadedDBSearch):

    def __init__(self, query):
        db.ThreadedDBSearch.__init__(self)

        self.query = codec.encodehttpget(query)
        self.hasnext = True
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

        st = re.findall(RE_VIDEOURL, itempage)
        #util.log.log("Youtube: " + str(st))
        if len(st) != 1:
            #util.log.log("Youtube: Downloadability check failed")
            #f = file("youtubepage", "w+")
            #print >> f, itempage
            return None

        name = re.findall(RE_NAME, itempage)
        if len(name) == 0:
            return None
        #print name[0]
        name = unicode(name[0], ENCODING)
        name = codec.decodehtml(name)
        #print name

        item['content_name'] = name

        category = re.findall(RE_CAT, itempage)
        if len(category) == 0:
            return None
        category = unicode(category[0], ENCODING)
        category = codec.decodehtml(category)
        
        item['category'] = category

        tags = re.findall(RE_TAG, itempage)
        if len(tags) == 1:
            tags = re.findall(RE_TAG2, tags[0])
        else:
            tags = []
        
        unicodetags = []
        for tag in tags:
            unicodetags.append(unicode(tag, ENCODING))

        item['tags'] = tags
        #item = video.VideoItem((site, id), name, YoutubeDownload, unicodetags, category)

        conn = urllib.urlopen(workitem[1])
        item['preview'] = conn.read()

        if item == None:
            log("Youtube: returning None")
        else:
            log("Youtube: returning " + item['content_name'])


        desc = re.findall(RE_DESC, itempage)
        item['description'] = codec.decodehtml(unicode("from youtube.com:\n" + desc[0], ENCODING))
        item['web2'] = True
        st = re.findall(RE_VIDEOURL, itempage)[0]
        src = URL_DL_VIDEO % st
        item['url'] = src
        views = re.findall(RE_VIEWS, itempage)
        item['views'] = int(filter(lambda x: x.isdigit(), views[0]))

        date = re.findall(RE_DATE, itempage, re.S)
        item['info'] = { 'creation date' : YoutubeDateParser(date[0]) }

        item['status'] = 'good'
        item['seeder'] = 1
        item['leecher'] = 1
        item['length'] = workitem[2]

        if item == None:
            log("Youtube: returning None")
        else:
            log("Youtube: returning " + item['content_name'])

        return item

    def parseItempage(self):

        if not self.hasnext:
            log("Youtube: no more items")
            return []
        
        #print "Self.newpage = true"
        url = URL_SEARCH % (self.query, self.pagecount)
        #print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read()
        pageconn.close()
        #print self.page
        items = re.findall(RE_SEARCHITEM, page, re.S)

        self.pagecount += 1

        if len(re.findall(RE_RESULTS_HASNEXT, page)) == 0:
            self.hasnext = False

        return items


class YoutubeDownload(download.Download):

    def __init__(self, item):
        self.item = item
        download.Download.__init__(self, None, item.getPath(), video.VideoTranscode)

    def run(self):
        try:
            conn = urllib.urlopen(URL_WATCH % self.item.getId()[1])
            page = conn.read()
            conn.close()
            st = re.findall(RE_VIDEOURL, page)[0]

            self.src = URL_DL_VIDEO % st
            
            download.Download.run(self)
        except:
            traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))


import datetime
import time

months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december" ]

def YoutubeDateParser(strdate):
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

