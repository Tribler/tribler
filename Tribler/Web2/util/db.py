# Written by Fabian van der Werf
# see LICENSE.txt for license information

import sys
import Queue

import bsddb.dbshelve
import base64
import md5
import os
import os.path
import pickle
import re
import shutil
import thread
import threading
import time
import traceback
import urllib

import utilsettings
from Tribler.Web2.util import observer
from Tribler.Web2.util.log import log 

DEBUG = False
databases = {}


def GetDatabase(database):
    try:
        return databases[database]
    except:
        return None

def GetItem(itemid, database):
    try:
        return databases[database].get(itemid)
    except:
        return None


dbfile = "db"
itemdir = "items"


#template database
class DB:

    def __init__(self, dir, name):
        databases[name] = self

        self.name = name

        self.dbdir = dir
        if not os.path.exists(self.dbdir):
            os.mkdir(self.dbdir)

        self.itemdir = os.path.join(dir, itemdir)
        if not os.path.exists(self.itemdir):
            os.mkdir(self.itemdir)

        env = bsddb.db.DBEnv()
        env.open(dir, bsddb.db.DB_PRIVATE | bsddb.db.DB_CREATE | 
                bsddb.db.DB_THREAD | bsddb.db.DB_INIT_LOCK | 
                bsddb.db.DB_INIT_MPOOL)
        self.db = bsddb.dbshelve.open(os.path.join(self.dbdir, dbfile), dbenv=env)

    def close(self):
        self.db.close()
                
    def exists(self, id):
        return self.db.has_key(pickle.dumps(id))

    def getName(self):
        return self.name

    def get(self, id):
        return self.db.get(pickle.dumps(id))

    def items(self):
        return self.db.items()


    def newItem(self, itemclass, id, *args, **kw):
        if pickle.dumps(id) in self.db.keys():
            raise AttributeError

        pathitem = os.path.join(self.itemdir, 
                base64.b32encode(pickle.dumps(id)))

        item = itemclass(id, self.name, pathitem, *args, **kw)
        self.db.update({pickle.dumps(id) : item})
        self.db.sync()
        
        return item
        

    def remove(self, id):
        item = self.db.pop(pickle.dumps(id))
        return item


    def search(self, tags):
        results = []

        for item in self.db:
            match = self.db[item].tagIntersection(tags)

            if match > 0:
                results.append((match, self.db[item], self))

        return results

    def update(self, item):
        results = self.db.update({pickle.dumps(item.getId()):item})
        self.db.sync()
        return results


#template item
class Item(observer.Observer):

    RatingUpdateTime = 600 #seconds

    def __init__(self, id, name, tags, dl = None):
        self.id = id
        self.name = name
        self.tags = tags
        self.dl = dl
        self.myrate = -1
        self.globalrate = (-1, -1)
        self.globalratetime = None

    def getId(self):
        return self.id

    def getName(self):
        return self.name

    def __eq__(self, item):
        try:
            if item.id == self.id:
                return True
            else:
                return False
        except:
            return False


    def __ne__(self, item):
        return not self.__eq__(item)


    def __hash__(self):

        # take first 4 bytes of md5
        h = md5.new(pickle.dumps(self.id) + self.db).hexdigest()
        h = h[:8] 
        h = int(h, 16)
        h -= 2147483648 #translate h into [-(2^31),2^31-1]
       
        # if h was outside the range [-(2^31),2^31-1] 
        # it was converted to a long -> make it an int now
        h = int(h) 

        return h
        

    def getTags(self):
        return self.tags


    def tagIntersection(self, tags):

        intersection = 0 

        for tag1 in tags:
            for tag2 in self.tags:
                if tag1.lower() == tag2.lower():
                    intersection += 1

        return intersection / float(len(self.tags) + len(tags) - intersection)


    def hasTag(self, tag):
        for tag2 in self.tags:
            if tag2 == tag:
                return True

        return False


    def rate(self, rating):
        self.myrate = rating
        RatingPoster(self.getId(), rating)

        self.sync()


    def getMyRate(self):
        return self.myrate


    def getGlobalRate(self):

        if self.globalratetime == None or \
                self.globalratetime + Item.RatingUpdateTime < time.time():
            getter = RatingGetter(self.getId())
            getter.attach(self)
        else:
            getter = RatingGetter(self.getId(), self.globalrate)

        return getter


    def getDownloader(self):
        return self.dl(self)


    def saveAsExt(self):
        ext = re.findall("^.*\.(.*)$", self.getPath())

        if len(ext) == 0:
            return ""
        else:
            return ext[0]
        

    def update(self, subject, m):

        # a bit of a race condition, nothing to worry about...
        self.globalrate = m
        self.globalratetime = time.time()

        self.sync()


class RatingPoster(threading.Thread):

    def __init__(self, itemid, rating):

        threading.Thread.__init__(self)
        self.setName( "RatingPoster"+self.getName() )
        self.setDaemon(True)

        self.itemid = itemid
        self.rating = rating

        self.start()

    def run(self):
        
        data = {}
        data["rating"] = str(self.rating)
        data["itemid"] = base64.b32encode(pickle.dumps(self.itemid))
        data["installid"] = str(settings.INSTALL_ID)

        try:
            conn = urllib.urlopen(utilsettings.RATINGPOST,
                urllib.urlencode(data))
        except:
            #fail silently
            pass

        #print conn.read()




class RatingGetter(threading.Thread, observer.Subject):

    def __init__(self, itemid, rate = None):
        threading.Thread.__init__(self)
        observer.Subject.__init__(self)

        self.setName( "RatingGetter"+self.getName() )
        self.setDaemon(True)

        itemid
        self.flatid = base64.b32encode(pickle.dumps(itemid))
        self.rate = rate

    def run(self):

        if self.rate != None:
            self.notify(self.rate)
            return

        try:
            url = utilsettings.RATINGGET % (self.flatid, settings.INSTALL_ID)
            log(url)
            conn = urllib.urlopen(url)
            response = conn.read()

            log(response)
            rating = re.findall("([^ ]*) ([^ ]*)", response)[0]
            log(str(rating))
            self.notify((int(rating[0]), int(rating[1])))
        except:
            pass

    



# template for an online search
class DBSearch(threading.Thread, observer.Subject):

    def __init__(self):
        threading.Thread.__init__(self)
        observer.Subject.__init__(self)
        
        self.setName( "DBSearch"+self.getName() )
        self.setDaemon(True)

        self.__count = 0
        self.__quit = threading.Event()
        self.__pause = threading.Event()
        self.__cpause = threading.Condition()
        self.__cond = threading.Condition()


    def run(self):
        
        while True:

            self.__cond.acquire()
            if self.__quit.isSet():
                self.__cond.release()
                return

            if self.__count == 0:
                self.__cond.wait()
                self.__cond.release()
                continue

            self.__cond.release()

            item = self.getItem()
            
            self.__cond.acquire()
            self.__count -= 1
            self.__cond.release()

            if self.__quit.isSet():
                return

            self.notify(item)
            if item == None:
                return

    def enough(self):
        self.__cond.acquire()
        self.__count = 0
        self.__cond.release()


    def getMore(self, num):
        self.__cond.acquire()
        self.__count += num
        self.__cond.notify()
        self.__cond.release()

    def isQuit(self):
        return self.__quit.isSet()

    def quit(self):
        self.__cond.acquire()
        self.__quit.set()
        self.__cond.notify()
        self.__cond.release()


class ThreadedDBSearch(observer.Subject):

    def __init__(self, nthreads=4):
        observer.Subject.__init__(self)

        self.__workqueue = Queue.Queue()
        self.__notyet = {}
        self.__current = 0
        self.__wanted = 0
        self.__total = 0
        self.__last = -1
        self.__nonew = False
        self.__texlock = threading.Condition()
        self.__returnlock = threading.RLock()
        self.__sleeplock = threading.Condition()
        self.__stop = threading.Event()
        self.__nthreads = nthreads

            
    def start(self):
        for i in range(self.__nthreads):
            t = threading.Thread(target=self.work)
            t.setName("Web2DBSearch"+t.getName())
            t.setDaemon(True)
            t.start()

    def work(self):

        try:
            while True:

                self.__texlock.acquire()
                self.__sleeplock.acquire()

                if self.__stop.isSet():
                    self.__sleeplock.release()
                    self.__texlock.release()
                    break
                
                if self.__wanted == 0:
                    self.__sleeplock.wait()
                    self.__sleeplock.release()
                    self.__texlock.release()
                    continue

                self.__sleeplock.release()

                if self.__workqueue.empty():

                    try:
                        newitems = self.parseItempage()
                    except:
                        if DEBUG:
                            traceback.print_exc()
                        newitems = []

                    if len(newitems) == 0:
                        self.__stop.set()
                        self.returnItem(-1, self.__total - 1)
                        self.__texlock.release()
                        break
                    else:
                        for i in range(len(newitems)):
                            self.__workqueue.put((self.__total, newitems[i]))
                            self.__total += 1

                (index, workitem) = self.__workqueue.get()


                self.__sleeplock.acquire()
                if self.__wanted > 0:
                    self.__wanted -= 1
                self.__sleeplock.release()

                self.__texlock.release()

                try:
                    dbitem = self.parseItem(workitem)
                except:
                    if DEBUG:
                        traceback.print_exc()
                    dbitem = None

                if dbitem == None:
                    if DEBUG:
                        print "web2.0: Item Failed: " + str(workitem)
                    self.getMore(1)

                self.returnItem(index, dbitem)

        except:
            if DEBUG:
                traceback.print_exc()


    def returnItem(self, i, item):

        self.__returnlock.acquire()

        if i < 0:
            self.__last = item
            self.__returnlock.release()
            return

        if self.__nonew:
            self.__returnlock.release()
            return

        if item != None:
            self.notify(item)
            self.__current += 1

        if self.__current == self.__last:
            self.notify(None)

        self.__returnlock.release()
        return

    def quit(self):
        self.__stop.set()
        self.__nonew = True
        self.__sleeplock.acquire()
        self.__sleeplock.notifyAll()
        self.__sleeplock.release()


    def getMore(self, num):
        self.__sleeplock.acquire()
        self.__wanted += num
        
        if DEBUG:
	        print >>sys.stderr,"web2: db: ThreadedDBSearch: getMore",num,"stop",self.__stop.isSet()
        
        self.__sleeplock.notifyAll()
        self.__sleeplock.release()


    def enough(self):
        self.__sleeplock.acquire()
        self.__wanted = 0
        self.__sleeplock.release()
                        

class CompoundDBSearch(observer.Subject, observer.Observer):
    instance = None
    
    def __init__(self, searches,standardOverview=None):
        if self.instance != None:
            self.instance.quit()
        self.instance = self
            
        observer.Subject.__init__(self)
        observer.Observer.__init__(self)
        self.lock = threading.RLock()
        self.searches = searches
        self.wanted = 0
        self.items = []
        self.total = 0
        self.standardOverview = standardOverview

    def start(self):

        for i in range(len(self.searches)):
            self.searches[i].attach(self)
            self.searches[i].start()


    def quit(self):
        self.lock.acquire()
        for i in range(len(self.searches)):
            self.searches[i].detach(self)
            self.searches[i].quit()
        
        self.items = []
        self.lock.release()

    def getMore(self, num):
        self.lock.acquire()

        self.wanted += num

        req = self.wanted - self.total - len(self.items)

        if req > 0:
            for i in range(len(self.searches)):
                self.searches[i].getMore(req)

        for i in range(min(len(self.items), num)):
            self.notify(self.items.pop(0))

        self.lock.release()
        

    def update(self, subject, item):
        self.lock.acquire()

        if item == None:
            log("CompoundSearch: update -> received None")
            subject.detach(self)
            subject.quit()
            self.searches.remove(subject)

            if len(self.searches) == 0:
                log("CompoundSearch: no more items")
                self.notify(None)

       
        else:
            self.total += 1
            log("CompoundSearch: update -> wanted:" + str(self.wanted)+ ", update -> new total:" + str(self.total))

            if self.total == self.wanted:
                log("CompoundSearch: update -> Enough")
                self.giveSearchFeedback(True, self.total)
                for i in range(len(self.searches)):
                    self.searches[i].enough()
                    
            if self.total < self.wanted:
                self.giveSearchFeedback(False, self.total)

            if self.total <= self.wanted:
                if DEBUG:
                    print >>sys.stderr,"web2: db: CompoundSearch: returning an item"
                self.notify(item)
            else:
                self.items.append(item)

        self.lock.release()

    def giveSearchFeedback(self, finished, num):
        if self.standardOverview:
            self.standardOverview.setSearchFeedback('web2', finished, num)
        

