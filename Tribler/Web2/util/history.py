# Written by Fabian van der Werf
# see LICENSE.txt for license information

from bsddb import dbshelve
import bsddb

import os.path
import observer
import threading


class HistoryDB(observer.Subject):

    ADDITEM = 1
    DELITEM = 2
    CLEAR = 3

    def __init__(self, dbfile, len):
        observer.Subject.__init__(self)
        self.dbfile = dbfile

        env = bsddb.db.DBEnv()
        env.open(dbfile, bsddb.db.DB_PRIVATE | bsddb.db.DB_CREATE |
                bsddb.db.DB_THREAD | bsddb.db.DB_INIT_LOCK |
                bsddb.db.DB_INIT_MPOOL)
        self.db = dbshelve.open(dbfile, dbenv = env)

        self.lock = threading.RLock()

        self.len = len

        try:
            self.history = self.db["history"]
        except:
            self.history = []


    def getLength(self):
        self.lock.acquire()
        l = self.len
        self.lock.acquire()
        return l


    def getNum(self):
        self.lock.acquire()
        l = len(self.history)
        self.lock.release()
        return l


    def add(self, item):

        self.lock.acquire()

        if item in self.history:
            self.history.remove(item)
            self.history.insert(0, item)
        else:
            if self.len != -1 and len(self.history) >= self.len:
                self.history.pop()

            self.history.insert(0, item)

        self.notify((HistoryDB.ADDITEM, 0, item))
        self.sync()

        self.lock.release()

    def remove(self, item):
        self.lock.acquire()
        if item in self.history:
            i = self.history.index(item)
            self.history.pop(i)
            self.sync()
            self.lock.release()
            self.notify((HistoryDB.DELITEM, 0, item))
        else:
            self.lock.release()

    def getItem(self, i):
        self.lock.acquire()
        item = self.history[i]
        self.lock.release()
        return item

    def clear(self):
        self.lock.acquire()
        self.history = []
        self.sync()
        self.lock.release()
        self.notify((HistoryDB.CLEAR, None))

    def sync(self):
        self.db["history"] = self.history
        self.db.sync()


    def close(self):
        self.lock.acquire()
        self.db["history"] = self.history
        self.db.close()
        self.lock.release()


    def printHistory(self):
        self.lock.acquire()
        for entry in self.history:
            print entry
        self.lock.release()

