import sys
import os
import wx

from shutil import copy, move
from Dialogs.aboutme import AboutMeDialog, VersionDialog
from Dialogs.abcoption import ABCOptionDialog
from Dialogs.localupload import LocalSettingDialog
from webservice import WebDialog

from Utility.helpers import stopTorrentsIfNeeded
from TorrentMaker.btmaketorrentgui import TorrentMaker

from Utility.constants import * #IGNORE:W0611


################################
# 
################################
class ABCBitmap(wx.Bitmap):
    def __init__(self, utility, filename, trans_color = wx.Colour(200, 200, 200)):
        self.utility = utility
                
        self.trans_color = trans_color
        
        self.filename = filename
                
        self.path = os.path.join(utility.getPath(), 'icons', self.filename)
        
        wx.Bitmap.__init__(self, self.path, wx.BITMAP_TYPE_BMP)
        
        mask = wx.Mask(self, self.trans_color)
        self.SetMask(mask)


################################
# 
################################
class ABCAction:
    def __init__(self, 
                 utility, 
                 filename = None, 
                 shortdesc = None, 
                 longdesc = None, 
                 menudesc = None, 
                 trans_color = wx.Colour(200, 200, 200), 
                 kind = None, 
                 id = None):
        self.utility = utility
        
        if id is None:
            self.id = wx.NewId()
        else:
            self.id = id
        
        if shortdesc is not None:
            self.shortdesc = self.utility.lang.get(shortdesc)
        else:
            self.shortdesc = ""
            
        if longdesc is not None:
            self.longdesc = self.utility.lang.get(longdesc)
        else:
            self.longdesc = self.shortdesc
            
        if menudesc is not None:
            self.menudesc = self.utility.lang.get(menudesc)
        else:
            self.menudesc = self.shortdesc
        
        self.kind = kind
        
        if filename is not None:
            self.bitmap = ABCBitmap(utility, filename, trans_color)
        else:
            self.bitmap = None
            
        self.toolbars = []

    def action(self, event = None):
        pass
        
    def addToMenu(self, menu, bindto = None):
        if bindto is None:
            bindto = menu
            
        bindto.Bind(wx.EVT_MENU, self.action, id = self.id)
        
        item = wx.MenuItem(menu, self.id, self.menudesc)
        menu.AppendItem(item)
        
        return self.id
        
    def removeFromToolbar(self, toolbar):
        if toolbar in self.toolbars:
            self.toolbars.remove(toolbar)
            removed = toolbar.DeleteTool(self.id)
            if removed:
                toolbar.toolcount -= 1
               
    def addToToolbar(self, toolbar):
        if (toolbar.firsttime):
            #Find size of images so it will be dynamics
            width = self.bitmap.GetWidth() + toolbar.hspacing
            height = self.bitmap.GetHeight() + toolbar.vspacing
            toolbar.SetToolBitmapSize(wx.Size(width, height))
            toolbar.firsttime = False
                
        if self.kind is None:
            tool = toolbar.AddSimpleTool(self.id, 
                                         self.bitmap, 
                                         shortHelpString = self.shortdesc, 
                                         longHelpString = self.longdesc)
        else:
            tool = toolbar.AddCheckTool(self.id, 
                                        self.bitmap, 
                                        shortHelp = self.shortdesc, 
                                        longHelp = self.longdesc)
            
        toolbar.Bind(wx.EVT_TOOL, self.action, tool)
        
        if not toolbar in self.toolbars:
            self.toolbars.append(toolbar)
        
        return tool
        
        
################################
# 
################################
class ABCActionMenu(ABCAction):
    def __init__(self, 
                 utility, 
                 menudesc = None, 
                 subactions = None):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = menudesc)
                           
        if subactions is None:
            subactions = []
        self.subactions = subactions
                           
    def addToMenu(self, menu, bindto = None):       
        if bindto is None:
            bindto = menu

        submenu = wx.Menu()

        for actionid in self.subactions:
            if actionid == -1:
                submenu.AppendSeparator()
            else:
                action = self.utility.actions[actionid]
                action.addToMenu(submenu, bindto)
                
        # wx.Menu and wx.MenuBar have different methods
        # for appending submenus
        if isinstance(menu, wx.Menu):
            menu.AppendMenu(self.id, self.menudesc, submenu)
        elif isinstance(menu, wx.MenuBar):
            menu.Append(submenu, self.menudesc)
        
        return self.id
