

import os
import shutil
import tempfile
import threading
import traceback
import urllib

import observer
from Tribler.Web2.util import log

class DLMessage:

    PROGRESS = 0
    FINISHED = 1
    FAILURE  = 2
    CANCELED = 3
    POSTPROC = 4

    def __init__(self, subject, type, current = -1, total = -1, msg = ""):
        self.subject = subject
        self.type = type
        self.current = current
        self.total = total
        self.msg = msg


class Download(observer.Subject, threading.Thread):

    def __init__(self, src, dst, mod=None, blocksize=8192, urlopen=urllib.urlopen):
        threading.Thread.__init__(self)
        observer.Subject.__init__(self)
        self.src = src
        self.dst = dst
        self.mod = mod
        self.blocksize = blocksize
        self.cancelevt = threading.Event()
        self.urlopen = urlopen

    def run(self):
        log("Starting download")
        try:
            eof = False
            tmp1fd, tmp1fn = tempfile.mkstemp()
            tmp1 = os.fdopen(tmp1fd, "w+")

            #print "Temp file: ", tmp1

            #print "Opening ", self.src
            conn = self.urlopen(self.src)
            #print "Opened ", self.src
            try:
                totalsize = int(conn.info()["Content-Length"])
                if totalsize <= 0:
                    totalsize = -1
            except:
                totalsize = -1

            #print "Totalsize = ", totalsize

            current = 0

            while not eof and not self.cancelevt.isSet():

                data = conn.read(self.blocksize)
                if len(data) < self.blocksize:
                    eof = True

                tmp1.write(data)

                current += len(data)
                self.notify(DLMessage(self, DLMessage.PROGRESS, current, totalsize))

            tmp1.close()

            if self.cancelevt.isSet():
                os.remove(tmp1fn)
                self.notify(DLMessage(self, DLMessage.CANCELED))
                return

            if self.mod != None:
                self.notify(DLMessage(self, DLMessage.POSTPROC))
                log("Post-processing download")
                self.mod(tmp1fn, self.dst)
                os.remove(tmp1fn)
            else:
                shutil.move(tmp1fn, self.dst)


            log("Finished download")
            self.notify(DLMessage(self, DLMessage.FINISHED))

        except:
            traceback.print_exc()
            log("Download failed")
            self.notify(DLMessage(self, DLMessage.FAILURE))
    

    def cancel(self):
        self.cancelevt.set()


class CompoundDownload(observer.Subject, observer.Observer, threading.Thread):

    def __init__(self, srcs, dsts, mod=None, blocksize=8192, urlopen=urllib.urlopen):
        observer.Observer.__init__(self)
        observer.Subject.__init__(self)
        threading.Thread.__init__(self)
        self.srcs = srcs
        self.dsts = dsts
        self.mod = mod
        self.blocksize = blocksize
        self.urlopen = urlopen

    def run(self):
        print "Starting compound download"

        self.dls = []
        self.progress = {}
        self.finished = 0

        try:
            for i in range(len(self.srcs)):
                dl = Download(self.srcs[i], self.dsts[i], blocksize=self.blocksize, urlopen=self.urlopen)
                self.dls.append(dl)
                dl.attach(self)
                self.progress[dl] = (0, -1)
                

            for i in range(len(self.srcs)):
                self.dls[i].start()

        except:
            print "Compound download failed"
            traceback.print_exc()
            self.notify(DLMessage(self, DLMessage.FAILURE, msg = str()))

    def update(self, subject, m):

        if m.type == DLMessage.PROGRESS:
            self.progress[subject] = (m.current, m.total)

            total = 0
            current = 0
            it = self.progress.itervalues()

            while True:
                try: 
                    (c, t) = it.next()
                except StopIteration, ex:
                    break

                current += c
                total += t
                    

            self.notify(DLMessage(self, DLMessage.PROGRESS, current, total))
            
        elif m.type == DLMessage.FINISHED:
            self.finished += 1
            subject.detach(self)

            if self.finished == len(self.dls):
                self.notify(DLMessage(self, DLMessage.FINISHED))

        elif m.type == DLMessage.FAILURE:

            for i in range(len(self.dls)):
                self.dls[i].detach(self)
                self.dls[i].cancel()

            self.notify(DLMessage(self, DLMessage.FAILURE))

        def cancel(self):
            for i in len(self.dls):
                self.dls[i].cancel()

            self.notify(DLMessage(self, DLMessage.CANCELED))

            


class DlMgrMsg:

    NEWDL = 0
    DELDL = 1

    def __init__(self, type, dl, item):
        self.type = type
        self.dl = dl
        self.item = item


class DownloadManager(observer.Observer, observer.Subject):

    instance = None
    
    def __init__(self):
        if DownloadManager.instance != None:
            raise AttributeError("DownloadManager is a singleton, use getInstance() instead")
            
        observer.Subject.__init__(self)
        observer.Observer.__init__(self)
        self.downloads = {}
        self.failncancel = []
        self.lock = threading.RLock()
        DownloadManager.instance = self
        

    @staticmethod
    def getInstance():
        if DownloadManager.instance == None:
            DownloadManager()

        return DownloadManager.instance
            

    def add(self, item):

        self.lock.acquire()

        if item in self.downloads.keys():
            dl = self.downloads[item]
            if dl in self.failncancel:
                self.failncancel.remove(dl)
                self.downloads.pop(item)
            else:
                self.lock.release()
                raise AttributeError

        dl = item.getDownloader()
        self.downloads[item] = dl

        self.notify(DlMgrMsg(DlMgrMsg.NEWDL, dl, item))
        dl.attach(self)

        dl.start()

        self.lock.release()


#    def remove(self, item):
#
        #self.lock.acquire()
#
        #if item  not in self.downloads.keys():
            #raise AttributeError
##
        #dl = self.downloads.pop(item)

        #self.lock.release()

        #self.notify(DlMgrMsg(DlMgrMsg.DELDL, dl, item))

        #if dl in self.finished:
            #self.finished.pop(dl)
            #del dl
        #else:
            #dl.cancel()


    def update(self, subject, m):


        if m.type == DLMessage.FINISHED or \
                m.type == DLMessage.CANCELED or \
                m.type == DLMessage.FAILURE:

            self.lock.acquire()
            subject.detach(self)

            if m.type == DLMessage.CANCELED or \
                    m.type == DLMessage.FAILURE:

                self.failncancel.append(subject)

            self.lock.release()


    def attachtodl(self, item, observer):
        self.lock.acquire()

        if item not in self.downloads.keys():
            self.lock.release()
            raise AttributeError

        dl = self.downloads.get(item)
        dl.attach(observer)

        self.lock.release()

        return dl

    #def cancel(self, item, clear = False):

        #self.lock.acquire()
        #if item  not in self.downloads.keys():
            #self.lock.release()
            #raise AttributeError

        #dl = self.downloads.get(item)

        #dl.cancel()

        #if clear:
            #self.remove(item)

        #self.lock.release()

    def cancelAll(self):
        for dl in self.downloads.values():
            if dl not in self.failncancel:
                dl.detach(self)
                try:
                    dl.cancel()
                except:
                    pass
                self.failncancel.append(dl)
    

    def __del__(self):
        observer.Subject.__del__(self)
        
                    
