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

from ABC.Actions.actionbase import ABCActionMenu

from Utility.constants import * #IGNORE:W0611


################################
# 
################################
class ExportMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_EXTRACTFROMLIST, 
                      ACTION_COPYFROMLIST]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'rexportfromlist', 
                               subactions = subactions)



################################
# 
################################
class AddTorrentMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_ADDTORRENT, 
                      ACTION_ADDTORRENTNONDEFAULT, 
                      ACTION_ADDTORRENTURL]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'menu_addtorrent', 
                               subactions = subactions)


################################
# 
################################
class FileMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_ADDTORRENTMENU, 
                      ACTION_MYINFO,
                      ACTION_PREFERENCES, 
                      -1, 
                      ACTION_EXIT]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'menu_file', 
                               subactions = subactions)
        
        
################################
# 
################################
class TorrentActionMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_STOPALL, 
                      ACTION_UNSTOPALL, 
                      ACTION_CLEARCOMPLETED,
                      ACTION_BUDDIES,
                      ACTION_FILES
                      ]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'menuaction', 
                               subactions = subactions)


################################
# 
################################
class ToolsMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_MAKETORRENT, 
                      ACTION_WEBPREFERENCES]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'menutools', 
                               subactions = subactions)
        
        
################################
# 
################################
class VersionMenu(ABCActionMenu):
    def __init__(self, utility):
        subactions = [ACTION_CHECKVERSION, 
                      ACTION_ABOUT]
        
        ABCActionMenu.__init__(self, 
                               utility, 
                               menudesc = 'menuversion', 
                               subactions = subactions)
                               
                              
