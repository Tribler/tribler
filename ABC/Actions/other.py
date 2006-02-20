import sys
import os
import wx

from shutil import copy, move
from Dialogs.aboutme import AboutMeDialog, VersionDialog
from Dialogs.abcoption import ABCOptionDialog
from Dialogs.localupload import LocalSettingDialog
from Tribler.Dialogs.abcbuddyframe import ABCBuddyFrame
from Tribler.Dialogs.abcfileframe import ABCFileFrame
from Tribler.Dialogs.managefriends import MyInfoDialog
from webservice import WebDialog

from Utility.helpers import stopTorrentsIfNeeded
from TorrentMaker.btmaketorrentgui import TorrentMaker

from ABC.Actions.actionbase import ABCAction

from Utility.constants import * #IGNORE:W0611

        
################################
# 
################################
class Exit(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menuexit', 
                           id = wx.ID_CLOSE)
                           
    def action(self, event = None):
        self.utility.frame.Close()
               

################################
# 
################################
class WebService(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'webservice.bmp', 
                           'toolbar_webservice', 
                           kind = wx.ITEM_CHECK)
        
    def action(self, event = None):
        webserver = self.utility.webserver
        
        if webserver.active:
            webserver.stop()
        else:
            webserver.start()
            
    def updateButton(self):
        active = self.utility.webserver.active
        
        for toolbar in self.toolbars:
            try:
                toolbar.ToggleTool(self.id, active)
                
                if active:
                    toolbar.SetToolShortHelp(self.id, self.utility.lang.get('active'))
                    toolbar.SetToolLongHelp(self.id, self.utility.lang.get('active'))
                else:
                    toolbar.SetToolShortHelp(self.id, self.utility.lang.get('inactive'))
                    toolbar.SetToolLongHelp(self.id, self.utility.lang.get('inactive'))
            except wx.PyDeadObjectError:
                pass
                   

################################
# 
################################
class Details(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'torrentdetail.bmp', 
                           'tb_torrentdetail_short', 
                           menudesc = 'rtorrentdetail')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        for ABCTorrentTemp in list.getTorrentSelected():
            ABCTorrentTemp.dialogs.advancedDetails()
        
        
        
        
################################
# 
################################
class LocalUploadSettings(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rlocaluploadsetting')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected()
        if selected:
            dialog = LocalSettingDialog(self.utility.window, selected)
            dialog.ShowModal()
            dialog.Destroy()
        list.SetFocus()
            
            
################################
# 
################################
class OpenDest(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'ropendest')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        for ABCTorrentTemp in list.getTorrentSelected(firstitemonly = True):
            if not ABCTorrentTemp.files.onOpenDest():
                list.SetFocus()


################################
# 
################################
class ChangeDest(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rchangedownloaddest')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        for ABCTorrentTemp in list.getTorrentSelected(firstitemonly = True):
            if not ABCTorrentTemp.dialogs.changeDest():
                list.SetFocus()
                

################################
# 
################################
class OpenFileDest(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'ropenfiledest')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        for ABCTorrentTemp in list.getTorrentSelected(firstitemonly = True):
            if not ABCTorrentTemp.files.onOpenFileDest():
                return
                
                
################################
# Display Preferences
################################
class Preferences(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menuabcpreference')
                           
    def action(self, event = None):
        dialog = ABCOptionDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
        

################################
# Display About me Dialog
################################
class About(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menuaboutabc')
                           
    def action(self, event = None):
        dialog = AboutMeDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
        
        
################################
# Display version info
################################
class CheckVersion(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menuchecklatestversion')
                           
    def action(self, event = None):
        dialog = VersionDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
        
        
################################
# 
################################
class MakeTorrent(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menucreatetorrent')
                           
        self.torrentmaker = None
                           
    def action(self, event = None):
        self.torrentmaker = TorrentMaker(self.utility.frame)
        
    def closeWin(self):
        try:
            if self.torrentmaker is not None:
                self.torrentmaker.closeWin()
        except wx.PyDeadObjectError:
            pass
        
        
################################
# 
################################
class WebServicePreferences(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'menuwebinterfaceservice')
                           
    def action(self, event = None):
        dialog = WebDialog(self.utility.frame)
        dialog.ShowModal()
        dialog.Destroy()
                       
               
################################
# 
################################
class ManualAnnounce(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'manualannounce')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected()
        for ABCTorrentTemp in selected:
            ABCTorrentTemp.connection.reannounce()

            
################################
# 
################################
class ExternalAnnounce(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'externalannounce')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected(firstitemonly = True)
        
        for ABCTorrentTemp in selected:
            ABCTorrentTemp.connection.reannounce_external()
                        
                             
################################
# 
################################
class Separator(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           shortdesc = 'separator')
                               
        self.menudesc = "--------------"
        mask = wx.Mask(wx.EmptyBitmap(24, 24))
        self.bitmap = wx.EmptyBitmap(24, 24)
        self.bitmap.SetMask(mask)
        
# -- new functions in Tribler --        
################################
# 
################################
class BuddiesAction(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'buddies.bmp', 
                           'tb_buddy_short', 
                           menudesc = 'managefriends')
                           
    def action(self, event = None):
        if self.utility.frame.buddyFrame is None:
            self.utility.frame.buddyFrame = ABCBuddyFrame(self.utility.frame)


################################
# 
################################
class FilesAction(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'files.bmp', 
                           'tb_file_short', 
                           menudesc = 'rtorrentdetail')
                           
    def action(self, event = None):
        if self.utility.frame.fileFrame is None:
            self.utility.frame.fileFrame = ABCFileFrame(self.utility.frame)


################################
# 
################################

class MyInfoAction(ABCAction):
    
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'friends.bmp', 
                           'tb_file_short',
                           menudesc = 'menumyinfo')
                           
    def action(self, event = None):
        dialog = MyInfoDialog(self.utility.frame,self.utility)
        dialog.ShowModal()
        dialog.Destroy()
