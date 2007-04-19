import wx, os, sys, os.path, random
import wx.xrc as xrc
from Tribler.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
from Tribler.utilities import *
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking

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
        self.item = None
        self.data = {}
        for mode in DETAILS_MODES+['status']:
            self.data[mode] = {}
        self.currentPanel = None
        self.addComponents()
        #self.Refresh()
        self.modeElements = {'filesMode': ['titleField', 'popularityField1', 'popularityField2', 'creationdateField', 
                                            'descriptionField', 'sizeField', 'thumbField', 'up', 'down', 'refresh', 'download', 'files_detailsTab'],
                             'personsMode': ['TasteHeart', 'recommendationField']
                             }

        self.guiUtility.report(self)
        self.guiUtility.initStandardDetails(self)

        
    def addComponents(self):
        self.SetBackgroundColour(wx.Colour(102,102,102))
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
            
            for element in self.modeElements[self.mode]:
                xrcElement = xrc.XRCCTRL(currentPanel, element)
                if not xrcElement:
                    print 'standardDetails: Error: Could not identify xrc element: %s for mode %s' % (element, self.mode)
                self.data[self.mode][element] = xrcElement
            
            # do extra init
            if modeString == 'files':
                print 'extra files init'
                self.data[self.mode].get('up').setBackground(wx.WHITE)
                self.data[self.mode].get('down').setBackground(wx.WHITE)
                self.data[self.mode].get('refresh').setBackground(wx.WHITE)
                
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
            
     
    def getData(self):
        return self.item
    
    def getIdentifier(self):
        if not self.item:
            return None
        try:
            if self.mode == 'filesMode':
                return self.item['infohash']
            elif self.mode == 'personsMode':
                return self.item['permid']
        except:
            print 'standardDetails: Error in getIdentifier, item=%s' % self.item
        
    def setData(self, item):
        self.item = item
        if self.mode == 'filesMode':
            torrent = item
            if not torrent:
                return
            
            torrentData = self.data[self.mode]
            
            titleField = torrentData.get('titleField')
            titleField.SetLabel(torrent.get('content_name'))
            titleField.Wrap(-1)
        
            if torrent.has_key('description'):
                descriptionField = torrentData.get('descriptionField')
                descriptionField.SetLabel(torrent.get('Description'))
                descriptionField.Wrap(-1)        

            if torrent.has_key('length'):
                sizeField = torrentData.get('sizeField')
                sizeField.SetLabel(self.utility.size_format(torrent['length']))
            
            if torrent.get('info', {}).get('creation date'):
                creationField = torrentData.get('creationdateField')
                creationField.SetLabel(friendly_time(torrent['info']['creation date']))\
                
            if torrent.has_key('seeder'):
                seeders = torrent['seeder']
                seedersField = torrentData.get('popularityField1')
                leechersField = torrentData.get('popularityField2')
                
                if seeders > -1:
                    seedersField.SetLabel('%d' % seeders)
                    leechersField.SetLabel('%d' % torrent['leecher'])
                else:
                    seedersField.SetLabel('?')
                    leechersField.SetLabel('?')
                    
            
        elif self.mode in ['personsMode', 'friendsMode']:
            print "<mluc> details for person"
            #recomm = random.randint(0,4)
            rank = self.guiUtility.peer_manager.getRank(item['permid'])
            #because of the fact that hearts are coded so that lower index means higher ranking, then:
            if rank > 0 and rank <= 5:
                recomm = 0
            elif rank > 5 and rank <= 10:
                recomm = 1
            elif rank > 10 and rank <= 15:
                recomm = 2
            elif rank > 15 and rank <= 20:
                recomm = 3
            else:
                recomm = 4
            if rank != -1:
                self.getGuiObj('recommendationField').SetLabel("%d" % rank)
            else:
                self.getGuiObj('recommendationField').SetLabel("")
            if recomm != -1:
                self.getGuiObj('TasteHeart').setHeartIndex(recomm)
            else:
                self.getGuiObj('TasteHeart').setHeartIndex(0)
            
        elif self.mode == 'libraryMode':
            pass
        elif self.mode == 'subscriptionMode':
            pass
        
    def getGuiObj(self, obj_name):
        """handy function to retrive an object based on it's name for the current mode"""
        return self.data[self.mode].get(obj_name)
        
#        creationdateField = self.data[self.mode].get('creationdate')
#        creationdateField.SetLabel(item.get('creation date'))
#        creationdateField.Wrap(-1) 
        
#        thumbField = self.data[self.mode].get('thumb')        
#        thumbField.SetBackgroundColour(wx.Colour(255,51,0))        
#        thumbField.Refresh()
        
        self.currentPanel.Refresh()
        
    def onResize(self, event):
        print 'details resize'
        self.currentPanel.SetSize(self.currentPanel.GetSize())
        self.currentPanel.Refresh()
        if event:
            event.Skip()
        
    def tabClicked(self, name):
        print 'Tabclicked: %s' % name
        
    def mouseAction(self, event):
        print 'mouseAction'
        
        obj = event.GetEventObject()
        print obj
        
        if not self.data:
            return
        if obj == self.downloadButton:
            self.download(self.data)
        elif obj == self.refreshButton: 
            #and self.refreshButton.isEnabled():
            print "refresh seeders and leechers"
            #self.swarmText.SetLabel(self.utility.lang.get('refreshing')+'...')
            #self.swarmText.Refresh()
            
            self.refresh(self.data)
            
    def refresh(self, torrent):
        if DEBUG:
            print >>sys.stderr,'contentpanel: refresh ' + repr(torrent.get('content_name', 'no_name'))
        check = SingleManualChecking(torrent)
        check.start()
            
#    def isEnabled(self):
#        return self.enabled

    def download(self, torrent):
        src1 = os.path.join(torrent['torrent_dir'], 
                            torrent['torrent_name'])
        src2 = os.path.join(self.utility.getConfigPath(), 'torrent2', torrent['torrent_name'])
        if torrent['content_name']:
            name = torrent['content_name']
        else:
            name = showInfoHash(torrent['infohash'])
        #start_download = self.utility.lang.get('start_downloading')
        #str = name + "?"
        if os.path.isfile(src1):
            src = src1
        else:
            src = src2
            
        if os.path.isfile(src):
            str = self.utility.lang.get('download_start') + u' ' + name + u'?'
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('click_and_download'), 
                                        wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                ret = self.utility.queue.addtorrents.AddTorrentFromFile(src)
                if ret == 'OK':
                    self.setRecommendedToMyDownloadHistory(torrent)
                    
        else:
        
            # Torrent not found            
            str = self.utility.lang.get('delete_torrent') % name
            dlg = wx.MessageDialog(self, str, self.utility.lang.get('delete_dead_torrent'), 
                                wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                infohash = torrent['infohash']
                self.data_manager.deleteTorrent(infohash, delete_file = True)
            
            