import sys
import os
import wx

from ABC.Actions.actionbase import ABCAction

from Utility.constants import * #IGNORE:W0611
              

################################
# 
################################
class PauseAll(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'pauseall.bmp', 
                           'pauseall', 
                           kind = wx.ITEM_CHECK)
        
    def action(self, event = None, release = True):
        #Force All active to on-hold state
        ####################################
        if (event is None or event.IsChecked()):
            release = False
        
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procPAUSE(release = release)
        list.SetFocus()
        
        
################################
# 
################################
class StopAll(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'stopall.bmp', 
                           'stopall', 
                           menudesc = 'menu_stopall')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procSTOP()
        list.SetFocus()     


################################
# 
################################
class UnStopAll(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'unstopall.bmp', 
                           'unstopall', 
                           menudesc = 'menu_unstopall')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procUNSTOP()
        list.SetFocus()
                   
        
################################
# 
################################
class Resume(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'resume.bmp', 
                           'tb_resume_short', 
                           menudesc = 'rResume')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procRESUME(list.getTorrentSelected())
        list.SetFocus()


################################
# 
################################
#class ReseedResume(ABCAction):
#    def __init__(self, utility):
#        ABCAction.__init__(self, 
#                           utility, 
#                           'reseedresume.bmp', 
#                           'tb_reseedresume_short',
#                           longdesc = 'tb_reseedresume_long',
#                           menudesc = 'tb_reseedresume_short')
#                           
#    def action(self, event = None):
#        list = self.utility.window.getSelectedList()
#        self.utility.actionhandler.procRESUME(list.getTorrentSelected(), skipcheck = True)
#        list.SetFocus()

        
################################
# 
################################
class Pause(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'pause.bmp', 
                           'tb_pause_short', 
                           longdesc = 'tb_pause_long', 
                           menudesc = 'rPause')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procPAUSE(list.getTorrentSelected())
        list.SetFocus()
        

################################
# 
################################
class Stop(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'stop.bmp', 
                           'tb_stop_short', 
                           longdesc = 'tb_stop_long', 
                           menudesc = 'rStop')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procSTOP(list.getTorrentSelected())
        list.SetFocus()
        

################################
# 
################################
class Queue(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'queue.bmp', 
                           'tb_queue_short', 
                           longdesc = 'tb_queue_long', 
                           menudesc = 'rQueue')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procQUEUE(list.getTorrentSelected())
        list.SetFocus()
               

################################
# 
################################
class Scrape(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'currentseedpeer.bmp', 
                           'tb_spy_short', 
                           longdesc = 'tb_spy_long', 
                           menudesc = 'rcurrentseedpeer')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        # Multi-selected torrent scraping
        for ABCTorrentTemp in list.getTorrentSelected():
            ABCTorrentTemp.actions.scrape(faildialog = True, manualscrape = True)


################################
# 
################################
class SuperSeed(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rsuperseedmode')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        for ABCTorrentTemp in list.getTorrentSelected():
            ABCTorrentTemp.connection.superSeed()


################################
# 
################################
class HashCheck(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rHashCheck')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        self.utility.actionhandler.procHASHCHECK(list.getTorrentSelected())
        list.SetFocus()
        

################################
# 
################################
class ClearMessage(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rclearmessage')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected()
        
        for ABCTorrentTemp in selected:
            # For all torrents, active and inactive, we erase both the list and the message from the engine.
            # This is to avoid active torrent to be erased with a little delay (up to 2 seconds) in the list
            # by the refresh routine.
            ABCTorrentTemp.changeMessage(type = "clear")
            
        list.SetFocus()
                    
            
################################
# 
################################
class ChangePriority(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rpriosetting')
                           
        self.priorities = [ self.utility.lang.get('rhighest'), 
                            self.utility.lang.get('rhigh'), 
                            self.utility.lang.get('rnormal'), 
                            self.utility.lang.get('rlow'), 
                            self.utility.lang.get('rlowest') ]
        self.prioID = {}
        for prio in self.priorities:
            self.prioID[prio] = wx.NewId()
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected()
               
        newprio = None
        for prio in self.priorities:
            id = self.prioID[prio]
            if id == event.GetId():
                newprio = self.priorities.index(prio)
            
        for ABCTorrentTemp in selected:
            ABCTorrentTemp.changePriority(newprio)
        
        list.SetFocus()
        
    def getCurrentPrio(self, prio = None):
        list = self.utility.window.getSelectedList()
        selected = list.getTorrentSelected(firstitemonly = True)
        
        if not selected:
            return None
            
        ABCTorrentTemp = selected[0]
        
        prio = ABCTorrentTemp.prio
        if prio is None:
            prio = self.utility.config.Read('defaultpriority')

        return self.priorities[prio]
               
    def addToMenu(self, menu, bindto = None):
        if bindto is None:
            bindto = menu

        currentprio = self.getCurrentPrio()
        if currentprio is None:
            return
            
        priomenu = wx.Menu()
            
        for prio in self.priorities:
            id = self.prioID[prio]
            bindto.Bind(wx.EVT_MENU, self.action, id = id)
            priomenu.Append(id, prio, prio, wx.ITEM_RADIO)

        priomenu.Check(self.prioID[currentprio], True)

        menu.AppendMenu(self.id, self.menudesc, priomenu)
        
        return self.id

