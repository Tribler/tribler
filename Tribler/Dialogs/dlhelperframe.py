# Written by Arno Bakker
# see LICENSE.txt for license information

import wx
import os
import sys
from traceback import print_exc

from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from managefriends import FriendList, createImageList

DEBUG = False


################################################################
#
# Class: DownloadHelperPanel
#
# Panel for coordinating the help of friends in downloading 
# a torrent
#
################################################################
class DownloadHelperPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)

        self.utility = dialog.utility
        engine = dialog.torrent.connection.engine
        if engine is not None:
            self.coordinator = engine.getDownloadhelpCoordinator()

        # If the torrent is stopped, don't allow helping
        if engine is None or self.coordinator is None:
            if engine is None:
                msg = self.utility.lang.get('dlhelpdisabledstop')
            else:
                msg = self.utility.lang.get('dlhelpdisabledhelper')
            mainbox = wx.BoxSizer(wx.VERTICAL)
            mainbox.Add(wx.StaticText(self, -1, msg), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
            self.SetSizerAndFit(mainbox)
            return

        # 0. Read friends from DB, and figure out who's already helping 
        # for this torrent
        friends = FriendDBHandler().getFriends()
        helpingFriends = self.coordinator.get_asked_helpers_copy()

        if DEBUG:
            print >> sys.stderr,"dlhelperframe: friends is",friends
            print >> sys.stderr,"dlhelperframe: helping friends is",helpingFriends

        # 1. Create list of images of all friends
        type = wx.LC_LIST
        # type = wx.LC_REPORT

        imgList = None
        if type != wx.LC_REPORT:
            try:
                imgList = createImageList(self.utility,friends)
            except:
                print_exc()
                # disable icons
                type = wx.LC_REPORT

        # 2. Filter out friends already helping for left window
        self.remainingFriends = []
        for index in range(len(friends)):
            friend = friends[index]
            flag = 0
            for helper in helpingFriends:
                if friend['name'] == helper['name']:
                    helper['tempiconindex'] = index
                    flag = 1
                    break
            if flag:
                continue
            friend['tempiconindex'] = index
            self.remainingFriends.append(friend)

        # 3. TODO: remove entries from helpingFriends that are no longer friends

        # 4. Build GUI
        mainbox = wx.BoxSizer(wx.VERTICAL)
        topbox = wx.BoxSizer(wx.HORIZONTAL)
        botbox = wx.BoxSizer(wx.HORIZONTAL)

        # 4a. Friends in left window
        friendsbox = wx.BoxSizer(wx.VERTICAL)
        friendsbox.Add(wx.StaticText(self, -1, self.utility.lang.get('availcandidates')), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.leftListCtl = FriendList(self,self.remainingFriends,type,imgList)
        #self.leftListCtl.SetToolTipString(self.utility.lang.get('multiannouncehelp'))
        
        friendsbox.Add(self.leftListCtl, 1, wx.EXPAND|wx.TOP, 5)
        topbox.Add(friendsbox, 0, wx.EXPAND)

        # 4b. +/- buttons in between
        operatorbox = wx.BoxSizer(wx.VERTICAL)
       
        button = wx.Button(self, -1, self.utility.lang.get('requestdlhelp'), style = wx.BU_EXACTFIT)
        button.SetToolTipString(self.utility.lang.get('requestdlhelp_help'))
        wx.EVT_BUTTON(self, button.GetId(), self.add_helper)
        operatorbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button2 = wx.Button(self, -1, self.utility.lang.get('stopdlhelp'), style = wx.BU_EXACTFIT)
        button2.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        wx.EVT_BUTTON(self, button2.GetId(), self.remove_helper)
        operatorbox.Add(button2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        topbox.Add(operatorbox, 0, wx.ALIGN_CENTER_VERTICAL)

        # 4c. Selected helpers in right window
        helperbox = wx.BoxSizer(wx.VERTICAL)
        helperbox.Add(wx.StaticText(self, -1, self.utility.lang.get('helpers')), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
       
        self.rightListCtl = FriendList(self,helpingFriends,type,imgList)
        #self.rightListCtl.SetToolTipString(self.utility.lang.get('httpseedshelp'))
        helperbox.Add(self.rightListCtl, 1, wx.EXPAND|wx.ALL, 5)
        topbox.Add(helperbox, 0, wx.EXPAND)      

        # 5. Show GUI
        mainbox.Add(topbox, 0, wx.EXPAND)
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        self.SetSizerAndFit(mainbox)


    def add_helper(self, event = None):
        changed_list = self.add_friends(self.leftListCtl,self.rightListCtl)
        self.make_it_so(True,changed_list)

    def remove_helper(self, event = None):
        changed_list = self.add_friends(self.rightListCtl,self.leftListCtl)
        self.make_it_so(False,changed_list)

    def add_friends(self,left,right):
        item = -1
        itemList = []
        while 1:
            item = left.GetNextItem(item,wx.LIST_NEXT_ALL,wx.LIST_STATE_SELECTED)
            if item == -1:
                break
            else:
                itemList.append(item)
        if len(itemList) > 0:
            friendsList = left.removeFriends(itemList)
            right.addFriends(friendsList)
            return friendsList
        else:
            return []
        
    def make_it_so(self, add, changed_list):
        helpingFriends = self.rightListCtl.getFriends()
        remainingFriends = self.leftListCtl.getFriends()

        if DEBUG:
            print >> sys.stderr,"dlhelperframe: before exec: remaining friends is",remainingFriends
            print >> sys.stderr,"dlhelperframe: before exec: helping friends is",helpingFriends
        self.coordinator.stop_help(remainingFriends, force = False)
        self.coordinator.request_help(helpingFriends, force = False)
