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

from ABC.Actions.move import *
from ABC.Actions.status import *
from ABC.Actions.menus import *
from ABC.Actions.other import *

from Utility.constants import * #IGNORE:W0611

def makeActionList(utility):
    actions = {}

    actions[ACTION_MOVEUP] = MoveUp(utility)
    actions[ACTION_MOVEDOWN] = MoveDown(utility)
    actions[ACTION_MOVETOP] = MoveTop(utility)
    actions[ACTION_MOVEBOTTOM] = MoveBottom(utility)
    
    actions[ACTION_CLEARCOMPLETED] = ClearCompleted(utility)
    
    actions[ACTION_PAUSEALL] = PauseAll(utility)
    actions[ACTION_STOPALL] = StopAll(utility)
    actions[ACTION_UNSTOPALL] = UnStopAll(utility)
    
    actions[ACTION_WEBSERVICE] = WebService(utility)
    
    actions[ACTION_ADDTORRENT] = AddTorrentFile(utility)
    actions[ACTION_ADDTORRENTNONDEFAULT] = AddTorrentNonDefault(utility)
    actions[ACTION_ADDTORRENTURL] = AddTorrentURL(utility)
    
    actions[ACTION_RESUME] = Resume(utility)
#    actions[ACTION_RESEEDRESUME] = ReseedResume(utility)
    
    actions[ACTION_PAUSE] = Pause(utility)
    actions[ACTION_STOP] = Stop(utility)
    actions[ACTION_QUEUE] = Queue(utility)
    actions[ACTION_REMOVE] = Remove(utility)
    actions[ACTION_REMOVEFILE] = RemoveFile(utility)
    actions[ACTION_SCRAPE] = Scrape(utility)
    actions[ACTION_DETAILS] = Details(utility)
    actions[ACTION_BUDDIES] = Buddies(utility)
    actions[ACTION_FILES] = Files(utility)
    
    actions[ACTION_SUPERSEED] = SuperSeed(utility)
    
    actions[ACTION_HASHCHECK] = HashCheck(utility)
    actions[ACTION_CLEARMESSAGE] = ClearMessage(utility)
    actions[ACTION_LOCALUPLOAD] = LocalUploadSettings(utility)
    
    actions[ACTION_OPENDEST] = OpenDest(utility)
    actions[ACTION_OPENFILEDEST] = OpenFileDest(utility)
    
    actions[ACTION_PREFERENCES] = Preferences(utility)
    actions[ACTION_ABOUT] = About(utility)
    actions[ACTION_CHECKVERSION] = CheckVersion(utility)
    
    actions[ACTION_MAKETORRENT] = MakeTorrent(utility)
    actions[ACTION_WEBPREFERENCES] = WebServicePreferences(utility)
    
    actions[ACTION_EXTRACTFROMLIST] = ExtractFromList(utility)
    actions[ACTION_COPYFROMLIST] = CopyFromList(utility)
    actions[ACTION_MANUALANNOUNCE] = ManualAnnounce(utility)
    actions[ACTION_EXTERNALANNOUNCE] = ExternalAnnounce(utility)
    actions[ACTION_CHANGEDEST] = ChangeDest(utility)
    actions[ACTION_CHANGEPRIO] = ChangePriority(utility)
    
    actions[ACTION_EXPORTMENU] = ExportMenu(utility)
    
    actions[ACTION_FILEMENU] = FileMenu(utility)
    actions[ACTION_ADDTORRENTMENU] = AddTorrentMenu(utility)
    actions[ACTION_TORRENTACTIONMENU] = TorrentActionMenu(utility)
    actions[ACTION_TOOLSMENU] = ToolsMenu(utility)
    actions[ACTION_VERSIONMENU] = VersionMenu(utility)
    
    actions[ACTION_EXIT] = Exit(utility)
    
    actions[ACTION_SEPARATOR] = Separator(utility)
    
    
    imagelist = { "list": None, 
                  "imageToId": {}, 
                  "idToImage": {} }
    first = True
    for actionid in actions:
        action = actions[actionid]
    
        bitmap = action.bitmap
        if bitmap is not None:            
            if first:
                width = bitmap.GetWidth()
                height = bitmap.GetHeight()
                imagelist["list"] = wx.ImageList(width, height)
                first = False
            
            imageindex = imagelist["list"].Add(bitmap)
            imagelist["imageToId"][imageindex] = actionid
            imagelist["idToImage"][actionid] = imageindex
            
    utility.actions = actions
    utility.imagelist = imagelist
#    
#    return actions