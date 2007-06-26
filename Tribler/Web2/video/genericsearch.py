

import re, sys
import urllib
import traceback

import video
from Tribler.Web2.util import codec
from Tribler.Web2.util import db
from Tribler.Web2.util.log import log
from Tribler.Web2.util import download

DEBUG = True


class GenericSearch(db.ThreadedDBSearch):

    def __init__(self, site, query, config):
        db.ThreadedDBSearch.__init__(self)
        self.site = site
        self.config = config
        self.query = codec.encodehttpget(query)
        self.hasnext = True
        self.pagecount = 1

    def get(self, item):
        return self.config.getParam(self.site, item)
    
    def parseItem(self, workitem):
        if DEBUG:
            print 'parseItem called with %s' % str(workitem)
            
        item = {}

        id = workitem[0]

        item['infohash'] = id

        url = self.get('URL_WATCH') % id
        if DEBUG:
            print "getting URL", url
        conn = urllib.urlopen(url)
        itempage = conn.read().replace('\n','')
        srcpage = itempage
        conn.close()
        
        # Liveleak needs a separate page to get video url
        url_for_src = self.get('URL_SRC')
        if url_for_src:
            url_for_src = url_for_src % id
            if DEBUG:
                print "getting URL", url_for_src
            conn = urllib.urlopen(url_for_src)
            srcpage = conn.read().replace('\n','')
            conn.close()

        
        trynum = 0
        success = False
        # Either get link by formatting id
        if self.get('VIDEO_URL'):
            src = self.get('VIDEO_URL') % id
        else:
            # Or with a regexp
            while(True):
                regexp = self.get('RE_VIDEO_URL%d' % trynum)
                if not regexp:
                    break;
                src = re.findall(regexp, srcpage, re.S | re.I)
                if len(src) == 1:
                    success = True
                    src = src[0]
                    break
                trynum += 1
            if not success:
                if DEBUG:
                    print 'Error, src=%s' % src
                return None
        
        

        # Youtube needs id parsed in url
        id2url = self.get('URL_DL_VIDEO')
        if id2url:
            src = self.get('URL_DL_VIDEO') % src
        
        unquote_url = self.get('UNQUOTE')
        if DEBUG:
            print 'unquote: %s' % unquote_url
        if unquote_url:
            src = urllib.unquote(src)
            
        if DEBUG:
            print 'Got video url: %s' % src
            
        name = re.findall(self.get('RE_NAME'), itempage)
        if len(name) == 0:
            if DEBUG:
                print 'Youtube: name error'
            return None
        #print name[0]
        ENCODING = self.get('ENCODING')
        name = unicode(name[0], ENCODING)
        name = codec.decodehtml(name)
        #print name

        item['content_name'] = name

#        category = re.findall(RE_CAT, itempage)
#        if len(category) == 0:
#            if DEBUG:
#                print 'Youtube: Category error'
#            return None
#        category = unicode(category[0], ENCODING)
#        category = codec.decodehtml(category)
#        
#        item['category'] = category

        tags = re.findall(self.get('RE_TAG'), itempage)
        if len(tags) == 1:
            tags = re.findall(self.get('RE_TAG2'), tags[0])
        else:
            tags = []
        
        unicodetags = []
        for tag in tags:
            unicodetags.append(unicode(tag, ENCODING))

        item['tags'] = tags
        #item = video.VideoItem((site, id), name, YoutubeDownload, unicodetags, category)

        if workitem[1].lower().startswith('http'):
            conn = urllib.urlopen(workitem[1])
            item['preview'] = conn.read()
        

        if item == None:
            log("Generic search: returning None")
        else:
            log("Generic search: returning " + item['content_name'])


        try:
            desc = re.findall(self.get('RE_DESC'), itempage, re.S)[0]
            if desc.strip() == '':
                raise RuntimeError()
            item['description'] = "from %s: %s" % (self.site, desc)
        except:
            item['description'] = "from %s" % self.site
            
        item['description'] = codec.decodehtml(unicode(item['description'], ENCODING))
        item['web2'] = True
        
        assert type(src) == str, "Url of video was not string, but %s (site:%s, name:%s)" % (repr(src), self.site, name)
        
        item['url'] = src
        if self.get('RE_VIEWS'):
            views = re.findall(self.get('RE_VIEWS'), itempage)
            item['views'] = int(filter(lambda x: x.isdigit(), views[0]))
        else:
            item['views'] = 'unknown'
        if self.get('RE_DATE'):
            date = re.findall(self.get('RE_DATE'), itempage, re.S)
            item['info'] = { 'creation date' : GenericDateParser(date[0], self) }

        item['status'] = 'good'
        item['seeder'] = 1
        item['leecher'] = 1
        try:
            item['length'] = workitem[2]
        except:
            item['length'] = 'unknown'

        
        
        return item

    def parseItempage(self):

        if not self.hasnext:
            log("%s: no more items" % self.site)
            return []
        
        #print "Self.newpage = true"
        url = self.get('URL_SEARCH') % (self.query, self.pagecount)
        if DEBUG:
            print "Retrieving url", url
        pageconn = urllib.urlopen(url)
        page = pageconn.read().replace('\n','')
        pageconn.close()
        if DEBUG:
            #print 'The page:\n%s' % page
            print 'Regexp: %s' % self.get('RE_SEARCHITEM')
        items = re.findall(self.get('RE_SEARCHITEM'), page, re.S)

        self.pagecount += 1

        RE_RESULTS_HASNEXT = self.get('RE_RESULTS_HASNEXT')
        if RE_RESULTS_HASNEXT:
            if len(re.findall(RE_RESULTS_HASNEXT, page)) == 0:
                self.hasnext = False

        if DEBUG:
            print 'Items found: %s' % str(items)
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
            if DEBUG:
                traceback.print_exc()
            self.notify(download.DLMessage(self, download.DLMessage.FAILURE))


import datetime
import time



def GenericDateParser(strdate, search):
    try:
        _strdate = strdate.strip()

        [smonth, day, year] = _strdate.split()

        months = search.get('MONTHS')
        month = months.index(smonth.lower()) + 1
        if month < 1:
            raise RuntimeError()
        day = int(filter(str.isdigit, day))
        year = int(year)

        return time.mktime(datetime.date(year, month, day).timetuple())

    except:
        if DEBUG:
            traceback.print_exc()
        return None

