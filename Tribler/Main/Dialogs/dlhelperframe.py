# Written by Arno Bakker
# see LICENSE.txt for license information

import wx
import os
import sys
from traceback import print_exc
from threading import Lock

from Tribler.Core.Utilities.utilities import show_permid_short
#from managefriends import createImageList
## from Tribler.Main.vwxGUI.IconsManager import IconsManager
from Tribler.Core.Utilities.utilities import show_permid_shorter
from Tribler.Core.simpledefs import *

DEBUG = True

################################################################
#
# Class: DownloadHelperPanel
#
# Panel for coordinating the help of friends in downloading 
# a torrent
#
################################################################


class DownloadHelperFrame(wx.Frame):
    
    def __init__(self,parent,utility,download_state):
        self.utility = utility
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('tb_dlhelp_short'), 
                          size=(640,520))
        
        main_panel = wx.Panel(self)
        self.downloadHelperPanel = self.createMainPanel(main_panel,download_state)
        bot_box = self.createBottomBoxer(main_panel)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        mainbox.Add(self.downloadHelperPanel, 1, wx.EXPAND|wx.ALL, 5)
        mainbox.Add(bot_box, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        main_panel.SetSizer(mainbox)


        iconpath = os.path.join(self.utility.session.get_tracker_favicon())
        # Giving it the whole bundle throws an exception about image 6
        self.icons = wx.IconBundle()
        print >> sys.stderr, iconpath
        if iconpath:
            self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Show()

    def createMainPanel(self,main_panel,download_state):
        return DownloadHelperPanel(main_panel,self.utility,download_state)

    def createBottomBoxer(self, main_panel):
        bot_box = wx.BoxSizer(wx.HORIZONTAL)
        button = wx.Button(main_panel, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.OnCloseWindow, button)
        bot_box.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        return bot_box


    def OnCloseWindow(self, event = None):
        self.Destroy()
        


class DownloadHelperPanel(wx.Panel):
    def __init__(self, parent, utility, download_state):
        wx.Panel.__init__(self, parent, -1)

        self.utility = utility
        self.download_state = download_state
        self.lock = Lock()

        # If the torrent is stopped, don't allow helping
        dlstopped = self.download_state is None or self.download_state.get_status() != DLSTATUS_DOWNLOADING
        dlhelper = self.download_state.get_download().get_coopdl_role() == COOPDL_ROLE_HELPER
        
        if dlstopped or dlhelper:
            if dlstopped:
                msg = self.utility.lang.get('dlhelpdisabledstop')
            elif dlhelper: 
                msg = self.utility.lang.get('dlhelpdisabledhelper')
            mainbox = wx.BoxSizer(wx.VERTICAL)
            mainbox.Add(wx.StaticText(self, -1, msg), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
            self.SetSizerAndFit(mainbox)
            return

        # 0. Read friends from DB, and figure out who's already helping 
        # for this torrent
        peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
        friends = peer_db.getGUIPeers(category_name = 'friends',
                                                                              sort = 'name', reverse = False
                                                                              )
        helpingFriends = peer_db.getPeers(self.download_state.get_coopdl_helpers(), ['permid', 'name', 'ip'])

        if DEBUG:
            print >> sys.stderr,"dlhelperframe: friends is",[a['name'] for a in friends]
            print >> sys.stderr,"dlhelperframe: helping friends is",[a['name'] for a in helpingFriends]

        # 1. Create list of images of all friends
        type = wx.LC_LIST
        #type = wx.LC_REPORT

        imgList = None
        if type != wx.LC_REPORT:
            try:
                #imgList = createImageList(self.utility,friends)
                im = IconsManager.getInstance()
                imgList = im.create_wxImageList(friends,setindex=True)
            except:
                print_exc()
                # disable icons
                type = wx.LC_REPORT

        # 2. Filter out friends already helping for left window
        self.remainingFriends = []
        for index, friend in enumerate(friends):
            
            if friend['name'] == '':
                friend['name']= 'peer %s' % show_permid_shorter(friend['permid'])
            
            flag = 0
            for helper in helpingFriends:
                if friend['permid'] == helper['permid']:
                    helper['tempiconindex'] = index
                    flag = 1
                    break
            if flag:
                continue
            #friend['tempiconindex'] = index
            self.remainingFriends.append(friend)
            

        # 3. TODO: remove entries from helpingFriends that are no longer friends

        # 4. Build GUI
        mainbox = wx.BoxSizer(wx.VERTICAL)
        topbox = wx.BoxSizer(wx.HORIZONTAL)
        botbox1 = wx.BoxSizer(wx.HORIZONTAL)
        botbox2 = wx.BoxSizer(wx.HORIZONTAL)

        # 4a. Friends in left window
        friendsbox = wx.BoxSizer(wx.VERTICAL)
        friendsbox.Add(wx.StaticText(self, -1, self.utility.lang.get('availcandidates')), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.leftListCtl = FriendList(self,self.remainingFriends,type,imgList)
        #self.leftListCtl.SetToolTipString(self.utility.lang.get('multiannouncehelp'))
        
        friendsbox.Add(self.leftListCtl, 1, wx.EXPAND|wx.TOP, 5)
        topbox.Add(friendsbox, 1, wx.EXPAND)

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
        topbox.Add(helperbox, 1, wx.EXPAND)      

        # Keep helpers up-to-date
        #self.timer = wx.Timer(self)
        #self.Bind(wx.EVT_TIMER, self.OnTimer)
        #self.timer.Start(4000)
        self.init_download_state_update()

        howtotext1 = wx.StaticText(self, -1, self.utility.lang.get('dlhelphowto1'))
        howtotext1.Wrap(500)
        botbox1.Add(howtotext1, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, 5)
        
        howtotext2 = wx.StaticText(self, -1, self.utility.lang.get('dlhelphowto2'))
        howtotext2.Wrap(500)
        botbox2.Add(howtotext2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, 5)


        # 5. Show GUI
        mainbox.Add(botbox1, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)        
        mainbox.Add(topbox, 0, wx.EXPAND|wx.ALL)
        mainbox.Add(botbox2, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)        
        
        #self.SetSizerAndFit(mainbox)
        self.SetSizer(mainbox)
        self.SetAutoLayout(True)


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
            print >> sys.stderr,"dlhelperframe: before exec: remaining friends is",[a['name'] for a in remainingFriends]
            print >> sys.stderr,"dlhelperframe: before exec: helping friends is",[a['name'] for a in helpingFriends]

        self.lock.acquire()
        self.download_state.get_download().stop_coopdl_helpers([a['permid'] for a in remainingFriends])
        self.download_state.get_download().ask_coopdl_helpers([a['permid'] for a in helpingFriends])
        self.lock.release()
        
    def OnActivated(self, event = None):
        pass

    def OnTimer(self, event = None):
        if DEBUG:
            print >> sys.stderr,"dlhelperframe: ON TIMER"

        peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
        self.lock.acquire()
        realhelpers = peer_db.getPeers(self.download_state.get_coopdl_helpers(), ['permid', 'name', 'ip'])
        self.lock.release()
        shownhelpers = self.rightListCtl.getFriends()


        removehelpers = []
        removeitems = []
        for i, shown in enumerate(shownhelpers):
            found = False
            for real in realhelpers:
                if real['permid'] == shown['permid']:
                    found = True
                    break
            if not found:
                if DEBUG:
                    print >>sys.stderr,"dlhelperframe: Helper",shown['name'],show_permid_short(shown['permid']),"could not be reached apparently, removing"
                removehelpers.append(shown)
                removeitems.append(i)
        self.rightListCtl.removeFriends(removeitems)
        self.leftListCtl.addFriends(removehelpers)

    def init_download_state_update(self):
        dl = self.download_state.get_download()
        dl.set_state_callback(self.download_state_update)

    def download_state_update(self, ds):
        try:
            self.lock.acquire()
            self.download_state = ds
            self.lock.release()
            wx.CallAfter(self.OnTimer)
            if not self.IsShown(): # do not call me again
                return -1, False
            else:
                return 4.0, False
        except wx.PyDeadObjectError:
            return -1, False
        

################################################################
#
# Class: FriendList
#
# ListCtrl for managing friends
#
################################################################
class FriendList(wx.ListCtrl):
    def __init__(self, parent, friends, type, imgList):

        self.type = type
        self.imgList = imgList
        style = wx.VSCROLL|wx.SIMPLE_BORDER|self.type|wx.LC_VRULES|wx.CLIP_CHILDREN
        if (sys.platform == 'win32'):
            style |= wx.LC_ALIGN_TOP
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        self.SetMinSize(wx.Size(200, 300))

        self.parent = parent
        self.friends = friends
        self.utility = parent.utility

        self.SetImageList(imgList,wx.IMAGE_LIST_SMALL)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.loadList()

    def loadList(self):
        if self.type == wx.LC_REPORT:
            try:    # get system font width
                fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
            except:
                fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
            self.InsertColumn(0, self.utility.lang.get('name'), format=wx.LIST_FORMAT_CENTER, width=fw*6)

        self.updateAll()
        self.Show(True)

    def updateAll(self):
        self.DeleteAllItems() 
        i = 0;
        for friend in self.friends:
            self.addItem(i,friend)
            i += 1

    def OnActivated(self, event):
        self.parent.OnActivated(event)

    def addItem(self,i,friend):
        if self.type != wx.LC_REPORT:
            label = friend['name']
            if not label:
                label = friend['ip']
            self.InsertImageStringItem(i,label,friend['tempiconindex'])
        else:
            self.InsertStringItem(i, friend['name'])

    def removeFriends(self,itemList):
        # Assumption: friends in list are in insert-order, i.e., not sorted afterwards!
        friendList = []
        # Make sure item ids stay the same during delete
        itemList.sort()
        itemList.reverse()
        for item in itemList:
            friend = self.friends[item]
            friendList.append(friend)
            del self.friends[item]
            self.DeleteItem(item)
        return friendList

    def addFriends(self,friendList):
        flag = 0
        i = self.GetItemCount()
        for friend in friendList:
            for chum in self.friends:
                if friend['permid'] == chum['permid']:    # here we must use 'permid' to distinguish 
                    flag = 1
                    break
            if flag:
                continue
            self.friends.append(friend)
            self.addItem(i,friend)
            i += 1

    def getFriends(self):
        return self.friends
    
