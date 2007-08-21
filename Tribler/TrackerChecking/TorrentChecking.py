# written by Yuan Yuan
# see LICENSE.txt for license information
#
#  
# Tracker Checking Algortihm
# ==========================
# 
# the detail design is:
# 
# The reply of the tracker-checking:
# 
# tracker-checking 1: the tracker reply fully and there is at least one seeders for that torrent file.
# tracker-checking 2: the tracker reply fully and there is no seeders for that torrent file.
# tracker-checking 3: the tracker connecting time out. 
# tracker-checking 4: the tracker has password protection.
# tracker-checking 5: the tracker returned an error or other message
# 
# the status of a certain torrent file:
# 
# torrent-status 1: good. (tracker-checking 1)
# torrent-status 2: not available now. (tracker-checking 2 and 3) If the status continue several times,
#                   then the status will change to torrent-status 3.
# torrent-status 3: dead. (tracker-checking 4 and 5) The torrent file can be deleted 
# 
# two limitations:
# 1. "only check torrent files at a rate of 1 per minute."
# 2. "for every known torrent file the tracker is contacted no more than a certain rate". (I change the 
#    "once a day" to " a certain rate",later I will explain why)
# 
# design detail:
# there will be 3 list in the system: a list of "good" torrent files (list_good),a list of 
# "not available now" torrent files(list_unknown) and a list of  "dead" torrent files(list_dead).
# 
# Suppose:
# g = len(list_good)
# n = len(list_unknown)
# 
# the algorithm is like this:
# 
# r = rand(0,1)
# if (r <= fun(g,n)):                # judgeing to pop list_good or list_unknown
#    while (1):                # pop the first torrent file from list_good
#        torrent = list_good.getFirst()        
#        if torrent.ignoreNumber > 0:        # whether to ignore 
#            torrent.ignoreNumber -= 1
#            list_good.append(torrent)
#        else:
#            break
#    if not_too_fast(torrent):        # limitation 2 (see up)
#        status = tracker_check(torrent)  # check the status of the torrent file from tracker
#        if (status == 'good'):
#            setTime(torrent)    # set the last checking time
#            setIgnoreNumber(torrent) # set the ignoreNumber
#            list_good.append(torrent)  # add torrent to the tail of the list_good
#        if (status == 'not available now')
#            setTime(torrent)
#            setIgnoreNumber(torrent)
#            torrent.retryNumber = 0
#            list_unknown.append(torrent)    # add torrent to the tail of the list_unknown
# else:
#    while (1):                    # pop the first torrent file from list_unknown
#        torrent = list_unknown.getFirst()        
#        if torrent.ignoreNumber > 0:        # whether to ignore 
#            torrent.ignoreNumber -= 1
#            list_unknown.append(torrent)
#        else:
#            break
#    if not_too_fast(torrent):        # limitation 2 (see up)
#        status = tracker_check(torrent)
#        if (status == 'good'):
#            setTime(torrent)    # set the last checking time
#            setIgnoreNumber(torrent)
#            list_good.append(torrent)  # add torrent to the tail of the list_good
#        if (status == 'not available now')
#            setTime(torrent)
#            if too_much_retry(torrent):     # judge whether this torrent file should add to the list_dead
#                list_dead.append(torrent)     # add torrent to the tail of the list_dead
#            else:
#                torrent.retryNumber += 1
#                setIgnoreNumber(torrent)
#                list_unknown.append(torrent)    # add torrent to the tail of the list_unknown
#        
# 
# design issue:
# 
# First. we use fun(g,n) to control the selection between list_good or list_unknown. now we can simply 
# implement it like this:
# 
# def fun(g,n):
#    total = g + n
#    if (g / total) > THRESHOLD:
#        return (g / total)
#    else
#        return THRESHOLD
# 
# The THRESHOLD is used to insure that the chance that we select the list_unknown is not too low,because 
# our major goal is to give each torrent file a certain status.
# 
# Another factor to control the efficiency of this algorithm may be the "torrent.ignoreNumber",the 
# setIgnoreNumber function. To implement "the more popular, recommended and active the torrent, the 
# more often it will be checked". we can just simple set the ignoreNumber of an unpopular (or 
# un-recommended or un-active) torrent file to n (n > 0,means the ignore times,count from "number of source","recommendation value" and "age"),then its checking-frequency will be 1/(n + 1) as the popular torrent file.
# 
# About the "not_too_fast" function,we may not use the rule that "for every known torrent file the 
# tracker is contacted no more than once a day". Because for a client contain 5000 torrent files,
# "once a day" may be a good choice. But for a client just has 100 torrent files,I think twice a day 
# may also be acceptable.
# 
# Note we do not use "Rank method",because to keep a sorted 5000-length list is too expensive. 
#
# Arno, 2007-07-13: Apparently the retry part was not implemented or has been removed since the design.
#
#
#===============================================================================

import sys
from threading import Thread
from random import random
from time import time, asctime

from Tribler.TrackerChecking.TrackerChecking import trackerChecking
from Tribler.TrackerChecking.TorrentCheckingList import TorrentCheckingList
from Tribler.CacheDB.SynDBHandler import SynTorrentDBHandler
from Tribler.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

DEBUG = False

class TorrentChecking(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        self.setName('TorrentChecking'+self.getName())
        if DEBUG:
            print 'TorrentChecking: Started torrentchecking'
        self.setDaemon(True)
        
        self.torrentList = TorrentCheckingList.getInstance()
        self.retryThreshold = 10
        self.gnThreashold = 0.9
        self.torrent_db = SynTorrentDBHandler()
        self.mldhtchecker = mainlineDHTChecker.getInstance() 
        
    def run(self):
        """ Gets one torrent from good or unknown list and checks it """
        self.torrentList.acquire()
        g = self.torrentList.getGoodLen()
        n = self.torrentList.getUnknownLen()
        self.torrentList.release()

        r = random()
        if (r < self.gnFun(g, n)):
            # good list
            if (g == 0):
                return;

            self.torrentList.acquire()
            torrent = self.torrentList.getFirstGood()
            self.torrentList.release()
            if not torrent:
                return
            if DEBUG:
                #print "TorrentChecking: ", asctime(), "Get From Good", repr(torrent["info"]["name"])
                pass
            # whether to ignore
            if (torrent["ignore_number"] > 0):    
                torrent["ignore_number"] -= 1
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, 
                                              ignore_number=torrent["ignore_number"])
                return
            
            # whether too fast
            if (self.tooFast(torrent)):
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True)
                return
            
            # may be block here because the internet IO
            trackerChecking(torrent)
            
            # Must come after tracker check, such that if tracker dead and DHT still alive, the
            # status is still set to good
            self.mldhtchecker.lookup(torrent['infohash'])
            
            self.setIgnoreNumber(torrent)            # set the ignore_number
            
            kw = {
                'last_check_time': int(time()),
                'seeder': torrent['seeder'],
                'leecher': torrent['leecher'],
                'status': torrent['status'],
                'ignore_number': torrent['ignore_number'],
                'retry_number': torrent['retry_number'],
                #'info': torrent['info']
                }
            self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, **kw)
        else:   
            # unknown list
            if (n == 0):
                return
            
            self.torrentList.acquire()
            torrent = self.torrentList.getFirstUnknown()
            self.torrentList.release()
            if not torrent:
                return
            if DEBUG:
                #print "TorrentChecking: ", asctime(), "Get from Unknown", repr(torrent["info"]["name"])
                pass
            # whether to ignore
            if (torrent["ignore_number"] > 0):    
                torrent["ignore_number"] -= 1
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, 
                                              ignore_number=torrent["ignore_number"])
                return
            
            # whether too fast
            if (self.tooFast(torrent)):
                self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True)
                return
            
            
            # may be block here because the internet IO
            trackerChecking(torrent)
            
            # Must come after tracker check, such that if tracker dead and DHT still alive, the
            # status is still set to good
            self.mldhtchecker.lookup(torrent['infohash'])
            
            self.setIgnoreNumber(torrent)
            kw = {
                'last_check_time': int(time()),
                'seeder': torrent['seeder'],
                'leecher': torrent['leecher'],
                'status': torrent['status'],
                'ignore_number': torrent['ignore_number'],
                'retry_number': torrent['retry_number'],
                #'info': torrent['info']
                }
            self.torrent_db.updateTorrent(torrent['infohash'], updateFlag=True, **kw)
        
        
    
    def gnFun(self, g, n):            # judgeing to pop list_good or list_unknown
        if (n == 0):
            return 1
        total = float(g + 2 * n)        # list_unkown 2x as fast as list_good
        result = g / total
        if (result > self.gnThreashold):
            result = self.gnThreashold
        return result
            
    def tooFast(self, torrent):
        interval_time = long(time()) - torrent["last_check_time"]
        if interval_time < 60 * 5:
            return True
        return False
    
        
    def setIgnoreNumber(self,torrent):
        if (torrent["status"] == "good"):
            torrent["ignore_number"] = 0
        elif (torrent["status"] == "unknown"):
            if (torrent["retry_number"] > self.retryThreshold):    # dead
                torrent["ignore_number"] = 0
            else:
                torrent["ignore_number"] = torrent["retry_number"]
        else:
            torrent["ignore_number"] = 0
        
    def tooMuchRetry(self, torrent):
        if (torrent["retry_number"] > self.retryThreshold):
            return True
        return False
