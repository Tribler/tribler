import sys
import os

#from traceback import print_exc
#from cStringIO import StringIO

from Utility.constants import * #IGNORE:W0611
from Utility.helpers import intersection

################################################################
#
# Class: ActionHandler
#
# Separates out some of the methods that are solely used to
# deal with actions that occur in ABCList
#
################################################################
class ActionHandler:
    def __init__(self, utility):
        self.utility = utility
        self.queue = self.utility.queue

    def procREMOVE(self, workinglist = None, removefiles = False):
        if workinglist is None:
            workinglist = []
            
        Read = self.utility.config.Read
        
        indexremoved = []
        for ABCTorrentTemp in workinglist:
            indexremoved.append(ABCTorrentTemp.listindex)
            
            if Read('removetorrent', "boolean"):
                try:
                    os.remove(ABCTorrentTemp.src)
                except:
                    pass

            ABCTorrentTemp.shutdown()
            ABCTorrentTemp.remove(removefiles)
            ABCTorrentTemp = None

        # Only need to update if we actually removed something
        if indexremoved:
            #indexremoved.sort(reverse = True)    ## for compatible with python2.3
            indexremoved.sort()
            indexremoved.reverse()
            for index in indexremoved:
                # Remove from the display
                self.utility.list.DeleteItem(index)
        
                # Remove from scheduler
                self.utility.torrents["all"].pop(index)

            self.queue.updateListIndex(startindex = indexremoved[-1])
            self.queue.updateAndInvoke()

    def procMOVE(self, workinglist = None):
        if workinglist is None:
            workinglist = self.utility.torrents["all"]

        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.files.move()]
            
        if update:
            self.queue.updateAndInvoke()

    def procSTOP(self, workinglist = None):
        if workinglist is None:
            workinglist = self.utility.torrents["all"]
            
        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.actions.stop()]
            
        if update:
            self.queue.updateAndInvoke()

    def procUNSTOP(self, workinglist = None):
        fulllist = self.utility.torrents["inactive"].keys()
        if workinglist is None:
            workinglist = fulllist
        else:
            workinglist = intersection(fulllist, workinglist)

        update = [1 for ABCTorrentTemp in workinglist
                    if ABCTorrentTemp.status.value == STATUS_STOP
                       and ABCTorrentTemp.actions.queue()]

        if update:
            self.queue.updateAndInvoke()
        
    def procPAUSE(self, workinglist = None, release = False):
        fulllist = self.utility.torrents["active"].keys()
        if workinglist is None:
            workinglist = fulllist
        else:
            workinglist = intersection(fulllist, workinglist)

        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.actions.pause(release)]

        if update:
            self.queue.UpdateRunningTorrentCounters()
       
    def procRESUME(self, workinglist = None, skipcheck = False):
        fulllist = self.utility.torrents["inactive"].keys()
        if workinglist is None:
            workinglist = fulllist
        else:
            workinglist = intersection(fulllist, workinglist)
        
        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.actions.resume(skipcheck)]

        if update:
            self.queue.updateAndInvoke(invokeLater = False)

    def procQUEUE(self, workinglist = None):
        if workinglist is None:
            workinglist = self.utility.torrents["all"]
        
        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.actions.queue()]
        
        if update:
            self.queue.updateAndInvoke()

    def procHASHCHECK(self, workinglist = None):
        if workinglist is None:
            workinglist = self.utility.torrents["all"]
        
        update = [1 for ABCTorrentTemp in workinglist if ABCTorrentTemp.actions.hashCheck()]
        
        if update:
            self.queue.updateAndInvoke()
