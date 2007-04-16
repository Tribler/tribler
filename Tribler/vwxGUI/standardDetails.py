import wx, os, sys, os.path
import wx.xrc as xrc
from Tribler.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
from Tribler.utilities import *

DETAILS_MODES = ['filesMode', 'personsMode', 'profileMode', 'friendsMode', 'subscriptionMode', 'messageMode']
DEBUG = True

class standardDetails(wx.Panel):
    """
    Wrappers around details xrc panels
    """
    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.mode = None
        self.data = {}
        for mode in DETAILS_MODES+['status']:
            self.data[mode] = {}
        self.currentPanel = None
        self.addComponents()
        #self.Refresh()
        self.guiUtility.report(self)
        self.guiUtility.initStandardDetails(self)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        
    def setMode(self, mode, data):
        if self.mode != mode:
            self.mode = mode
            self.data[self.mode]['data'] = data
            self.refreshMode()
            
    def refreshMode(self):
        # load xrc
        self.oldpanel = self.currentPanel
        #self.Show(False)
        
        self.currentPanel = self.loadPanel()
        assert self.currentPanel, "Panel could not be loaded"
        self.currentPanel.Layout()
        self.currentPanel.SetAutoLayout(1)
        self.currentPanel.SetSizer(self.data[self.mode]['sizer'])
        self.currentPanel.Bind(wx.EVT_SIZE, self.onResize)
        #self.currentPanel.Enable(True)
        self.currentPanel.Show(True)
        
        if self.oldpanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            #self.oldpanel.Disable()
        
        self.hSizer.Insert(0, self.currentPanel, 0, wx.ALL|wx.EXPAND, 0)
        
            
            
        self.hSizer.Layout()
        self.currentPanel.Refresh()
        #self.Show(True)
        
        
    def refreshStatusPanel(self, show):
        if show:
            statusPanel = self.data['status'].get('panel')
            if not statusPanel:
                statusPanel = self.loadStatusPanel()
                self.data['status']['panel'] = statusPanel
            #statusPanel.Enable()
            statusPanel.Show()
            self.hSizer.Insert(1, statusPanel, 0, wx.TOP|wx.EXPAND, 6)
            self.hSizer.Layout()
        else:
            # Remove statusPanel if necessary
            if self.data['status'].get('panel'):
                statusPanel = self.data['status']['panel']
                try:
                    self.hSizer.Detach(statusPanel)
                    statusPanel.Hide()
                    #statusPanel.Disable()
                except:
                    print_exc()
        
    def loadPanel(self):
        currentPanel = self.data[self.mode].get('panel',None)
        modeString = self.mode[:-4]
        if not currentPanel:
            xrcResource = os.path.join('Tribler','vwxGUI', modeString+'Details.xrc')
            panelName = modeString+'Details'
            currentPanel = self.loadXRCPanel(xrcResource, panelName)
            
            # Save paneldata in self.data
            self.data[self.mode]['panel'] = currentPanel
            #titlePanel = xrc.XRCCTRL(currentPanel, 'titlePanel')
            self.data[self.mode]['title'] = xrc.XRCCTRL(currentPanel, 'titleField')
            self.data[self.mode]['sizer'] = xrc.XRCCTRL(currentPanel, 'mainSizer')
            self.data[self.mode]['creationdate'] = xrc.XRCCTRL(currentPanel, 'creationdateField')
            self.data[self.mode]['description'] = xrc.XRCCTRL(currentPanel, 'descriptionField')
            self.data[self.mode]['size'] = xrc.XRCCTRL(currentPanel, 'sizeField')
            self.data[self.mode]['thumb'] = xrc.XRCCTRL(currentPanel, 'thumbField')
        return currentPanel
    
    def loadStatusPanel(self):
        return self.loadXRCPanel(os.path.join('Tribler','vwxGUI', 'statusDownloads.xrc'), 'statusDownloads')
    
    def loadXRCPanel(self, filename, panelName):
        try:
            currentPanel = None
            res = xrc.XmlResource(filename)
            # create panel
            currentPanel = res.LoadPanel(self, panelName)
            if not currentPanel:
                raise Exception()
            return currentPanel
        except:
            print 'Error: Could not load panel from XRC-file %s' % filename
            print 'Tried panel: %s=%s' % (panelName, currentPanel)
            print_exc()
            return None
            
     
    def setData(self, item):
        if self.mode == 'filesMode':
            torrent = item
            titleField = self.data[self.mode].get('title')
            titleField.SetLabel(torrent.get('content_name'))
            titleField.Wrap(-1)
        
            if torrent.has_key('description'):
                descriptionField = self.data[self.mode].get('description')
                descriptionField.SetLabel(torrent.get('Description'))
                descriptionField.Wrap(-1)        

            if torrent.has_key('length'):
                sizeField = self.data[self.mode].get('size')
                sizeField.SetLabel(self.utility.size_format(torrent['length']))
            
            if torrent.get('info', {}).get('creation date'):
                creationField = self.data[self.mode].get('creationdate')
                creationField.SetLabel(friendly_time(torrent['info']['creation date']))\
                
        elif self.mode in ['personsMode', 'friendsMode']:
            pass
        elif self.mode == 'libraryMode':
            pass
        elif self.mode == 'subscriptionMode':
            pass
        

#        creationdateField = self.data[self.mode].get('creationdate')
#        creationdateField.SetLabel(item.get('creation date'))
#        creationdateField.Wrap(-1) 
        
#        thumbField = self.data[self.mode].get('thumb')        
#        thumbField.SetBackgroundColour(wx.Colour(255,51,0))        
#        thumbField.Refresh()
        
       
        
        
    def onResize(self, event):
        print 'details resize'
        self.currentPanel.SetSize(self.currentPanel.GetSize())
        self.currentPanel.Refresh()
        