# Written by Richard Gwin
# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import random, sys
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxBitmap
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Core.simpledefs import *
from time import time
from traceback import print_exc,print_stack
import urllib

class BasicOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
#        print "<mluc> tribler_topButton in init"
        self.initDone = False
        self.elementsName = ['searchFieldCentre']
        self.elements = {}
        self.data = {} #data related to basic information, to be used in details panel
        self.mypref = None
        
        # SELDOM cache
        self.bartercast_db = None
        self.barterup = 0
        self.barterdown = 0
        
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()     
        
    def OnCreate(self, event):
#        print "<mluc> tribler_topButton in OnCreate"
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        #print >>sys.stderr,"basicOverviewPanel: in _PostInit"
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()

        self.frame = self.guiUtility.frame

        self.frame.standardDetails.Hide()
        self.frame.pageTitlePanel.Hide()
        self.frame.pageTitle.Hide()
        self.frame.sharing_reputation.Hide()
        self.frame.srgradient.Hide()
        self.frame.help.Hide()
        self.frame.sr_indicator.Hide()
        self.frame.videopanel.Hide()
        self.frame.familyfilter.Hide()
        self.frame.pagerPanel.Hide()
  

        
        self.utility = self.guiUtility.utility
        # All mainthread, no need to close
        self.torrent_db = self.guiUtility.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.peer_db = self.guiUtility.utility.session.open_dbhandler(NTFY_PEERS)
        self.friend_db = self.guiUtility.utility.session.open_dbhandler(NTFY_FRIENDS)
        self.bartercast_db = self.guiUtility.utility.session.open_dbhandler(NTFY_BARTERCAST)
        self.mypref = self.guiUtility.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'basicOverviewPanel: Error: Could not identify xrc element:',element
            self.elements['searchFieldCentre'] = xrcElement

        self.elements['searchFieldCentre'].Bind(wx.EVT_KEY_DOWN, self.OnSearchKeyDown)
        self.initDone = True
        
        self.timer = None
         
        wx.CallAfter(self.Refresh)
        



    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
#            print "[basicOverviewPanel] gui element %s not available" % name
            return None
        return self.elements[name]
    
        self.nat_type = -1


    def OnSearchKeyDown(self,event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN and self.elements['searchFieldCentre'].GetValue().strip() != '': 
            self.guiUtility.standardFilesOverview()
            self.guiUtility.dosearch()
        else:
            event.Skip()     
      

