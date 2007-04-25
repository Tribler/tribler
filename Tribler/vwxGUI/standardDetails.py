import wx, os, sys, os.path, random
import wx.xrc as xrc
from binascii import hexlify
from time import sleep
from Tribler.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc
from Tribler.utilities import *
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
import cStringIO
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from safeguiupdate import FlaglessDelayedInvocation
import time

DEFAULT_THUMB = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'thumbField.png'))
DETAILS_MODES = ['filesMode', 'personsMode', 'profileMode', 'libraryMode', 'friendsMode', 'subscriptionsMode', 'messageMode']
DEBUG = True

ISFRIEND_BITMAP = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'isfriend.png'))

class standardDetails(wx.Panel,FlaglessDelayedInvocation):
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
        FlaglessDelayedInvocation.__init__(self)
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.mode = None
        self.item = None
        self.lastItemSelected = {} #keeps the last item selected for each mode
        self.data = {} #keeps gui elements for each mode
        for mode in DETAILS_MODES+['status']:
            self.data[mode] = {} #each mode has a dictionary of gui elements with name and reference
            self.lastItemSelected[mode] = None
        self.currentPanel = None
        self.addComponents()
        
        #self.Refresh()
        self.modeElements = {}
        for elem in DETAILS_MODES:
            self.modeElements[elem] = []
        self.modeElements['filesMode'] = ['titleField', 'popularityField1', 'popularityField2', 'creationdateField', 
                                            'descriptionField', 'sizeField', 'thumbField', 'up', 'down', 'refresh', 
                                            'download', 'tabs', ('files_detailsTab','tabs'), ('info_detailsTab','tabs'), 'TasteHeart', 'details',]
        self.modeElements['personsMode'] = ['TasteHeart', 'recommendationField','addAsFriend', 'commonFilesField',
                                            'alsoDownloadedField', 'info_detailsTab', 'advanced_detailsTab','detailsC',
                                            'titleField']
        self.modeElements['libraryMode'] = ['titleField', 'popularityField1', 'popularityField2', 'creationdateField', 
                                            'descriptionField', 'sizeField', 'thumbField', 'up', 'down', 'refresh', 
                                            'download', 'files_detailsTab', 'info_detailsTab', 'TasteHeart', 'details',]
        
        self.tabElements = {'filesTab_files': [ 'download', 'includedFiles', 'filesField'],                            
                            'personsTab_advanced': ['lastExchangeField', 'noExchangeField', 'timesConnectedField','addAsFriend'],
                            'libraryTab_files': [ 'download', 'includedFiles']}
            
        self.guiUtility.initStandardDetails(self)

        try:
            self.embedplayer_enabled = False
            feasible = return_feasible_playback_modes()
            if PLAYBACKMODE_INTERNAL in feasible:
                self.embedplayer_enabled = True
                videoplayer = VideoPlayer.getInstance()
                videoplayer.set_parentwindow(self)
                
                oldcwd = os.getcwd()
                if sys.platform == 'win32':
                    vlcinstalldir = os.path.join(self.utility.getPath(),"vlc")
                    os.chdir(vlcinstalldir)
        
                self.showingvideo = False
                from Tribler.Video.EmbeddedPlayer import EmbeddedPlayer
                self.videopanel = EmbeddedPlayer(self, -1, self, False, self.utility)
                self.videopanel.Hide()
                # Arno, 2007-04-02: There is a weird problem with stderr when using VLC on Linux
                # see Tribler\Video\vlcmedia.py:VLCMediaCtrl. Solution is to sleep 1 sec here.
                # Arno: 2007-04-23: Appears to have been cause by wx.SingleInstanceChecker
                # in wxPython-2.8.1.1.
                #
                #if sys.platform == 'linux2':
                #    print "Sleeping for a few seconds to allow VLC to initialize"
                #    sleep(5)
                    
                if sys.platform == 'win32':
                    os.chdir(oldcwd)
            else:
                self.showingvideo = False
                self.videopanel = None
        except Exception,e:
            print "EXCEPTION IN STANDARDA",str(e)
            print_exc()

    def addComponents(self):
        self.SetBackgroundColour(wx.Colour(102,102,102))
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
    
        
    def setMode(self, mode, item = None):
        
        print >>sys.stderr,"standardDetails: setMode called, new mode is",mode,"old",self.mode,"###########"
        
        if self.mode != mode:
            #change the mode, so save last item selected
            self.lastItemSelected[self.mode] = self.item
            self.mode = mode
            self.refreshMode()
        if item:
            self.setData(item)
        elif self.lastItemSelected[self.mode]:
            self.guiUtility.selectData(self.lastItemSelected[self.mode])
        else:
            self.setData(None)
    
    def getMode(self):
        return self.mode
            
    def refreshMode(self):
        # load xrc
        self.oldpanel = self.currentPanel
        #self.Show(False)
        
        self.currentPanel = self.loadPanel()
        assert self.currentPanel, "Panel could not be loaded"
        self.currentPanel.Layout()
        self.currentPanel.SetAutoLayout(1)
        #self.currentPanel.Enable(True)
        self.currentPanel.Show(True)
        
        if self.oldpanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            #self.oldpanel.Disable()
        
        self.hSizer.Insert(0, self.currentPanel, 0, wx.ALL|wx.EXPAND, 0)
        
            
#        self.currentPanel.Layout()
        wx.CallAfter(self.hSizer.Layout)
        wx.CallAfter(self.currentPanel.Refresh)
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
        
    def setListAspect2OneColumn(self, list_name):
        ofList = self.getGuiObj(list_name)
        ofList.ClearAll()
        if sys.platform == 'win32':
            ofList.SetWindowStyleFlag(wx.LC_REPORT|wx.NO_BORDER|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL) #it doesn't work
        else:
            ofList.SetSingleStyle(wx.NO_BORDER)
            ofList.SetSingleStyle(wx.LC_REPORT)
            ofList.SetSingleStyle(wx.LC_NO_HEADER)
            ofList.SetSingleStyle(wx.LC_SINGLE_SEL)
        ofList.InsertColumn(0, "Torrent") #essential code
#        ofList.SetColumnWidth(0,wx.LIST_AUTOSIZE)
        
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
                xrcElement = None
                name = None
                if type(element) == str:
                    xrcElement = xrc.XRCCTRL(currentPanel, element)
                    name = element
                elif type(element) == tuple:
                    name = element[0]
                    xrcElement = xrc.XRCCTRL(self.getGuiObj(element[1]), name)
                if not xrcElement:
                    print 'standardDetails: Error: Could not identify xrc element: %s for mode %s' % (element, self.mode)
                if name:
                    self.data[self.mode][name] = xrcElement
            
            # do extra init
            if modeString == 'files' or modeString == 'library':
                self.getGuiObj('up').setBackground(wx.WHITE)
                self.getGuiObj('down').setBackground(wx.WHITE)
                self.getGuiObj('refresh').setBackground(wx.WHITE)
                self.getGuiObj('TasteHeart').setBackground(wx.WHITE)
                infoTab = self.getGuiObj('info_detailsTab')
                infoTab.setSelected(True)
                self.getAlternativeTabPanel('filesTab_files', parent=currentPanel).Hide()
                
            elif modeString == 'persons' or modeString == 'friends':
                self.getGuiObj('TasteHeart').setBackground(wx.WHITE)
                self.getGuiObj('info_detailsTab').setSelected(True)
                self.getGuiObj('advanced_detailsTab').SetLabel(" advanced")
                #get the list in the right mode for viewing
                self.setListAspect2OneColumn("alsoDownloadedField")
                self.setListAspect2OneColumn("commonFilesField")
                self.getAlternativeTabPanel('personsTab_advanced', parent=currentPanel).Hide()
            
            elif modeString == "profile":
                pass
                #self.getAlternativeTabPanel('profileDetails_Quality').Hide() #parent is self because it is not a tab, it replaces the details panel
                
        return currentPanel
    
    def loadStatusPanel(self):
        return self.loadXRCPanel(os.path.join('Tribler','vwxGUI', 'statusDownloads.xrc'), 'statusDownloads')
    
    def loadXRCPanel(self, filename, panelName, parent=None):
        try:
            currentPanel = None
            if not os.path.exists(filename):
                dummyFile = os.path.join('Tribler','vwxGUI', 'dummy.xrc')
                filename = dummyFile
                panelName = "dummy"
            res = xrc.XmlResource(filename)
            # create panel
            if parent==None:
                parent = self
            currentPanel = res.LoadPanel(parent, panelName)
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
            if self.mode in ['filesMode','libraryMode']:
                return self.item['infohash']
            elif self.mode in ['personsMode','friendsMode']:
                return self.item['permid']
        except:
            print 'standardDetails: Error in getIdentifier for mode %s, item=%s' % (self.mode,self.item)
        
    def setData(self, item):
        
        
        print >>sys.stderr,"standardDetails: setData called, mode is",self.mode,"###########"
        
        self.item = item
        if not item:
            return
        if self.mode == 'filesMode':
            #check if this is a corresponding item from type point of view
            if item.get('infohash')==None:
                return #no valid torrent
            torrent = item
            
            titleField = self.getGuiObj('titleField')
            titleField.SetLabel(torrent.get('content_name'))
            titleField.Wrap(-1)
            
            self.setTorrentThumb(torrent, self.getGuiObj('thumbField'))        
            
            if self.getGuiObj('info_detailsTab').isSelected():
                # The info tab is selected, show normal torrent info
                if torrent.has_key('description'):
                    descriptionField = self.getGuiObj('descriptionField')
                    descriptionField.SetLabel(torrent.get('Description'))
                    descriptionField.Wrap(-1)        
    
                if torrent.has_key('length'):
                    sizeField = self.getGuiObj('sizeField')
                    sizeField.SetLabel(self.utility.size_format(torrent['length']))
                
                if torrent.get('info', {}).get('creation date'):
                    creationField = self.getGuiObj('creationdateField')
                    creationField.SetLabel(friendly_time(torrent['info']['creation date']))\
                    
                if torrent.has_key('seeder'):
                    seeders = torrent['seeder']
                    seedersField = self.getGuiObj('popularityField1')
                    leechersField = self.getGuiObj('popularityField2')
                    
                    if seeders > -1:
                        seedersField.SetLabel('%d' % seeders)
                        leechersField.SetLabel('%d' % torrent['leecher'])
                    else:
                        seedersField.SetLabel('?')
                        leechersField.SetLabel('?')
            
            elif self.getGuiObj('files_detailsTab').isSelected():
                filesList = self.getGuiObj('includedFiles', tab = 'filesTab_files')
                filesList.setData(torrent)
                self.getGuiObj('filesField', tab = 'filesTab_files').SetLabel('%d' % filesList.getNumFiles())
                
                
            else:
                print 'standardDetails: error: unknown tab selected'
            
                        
        elif self.mode in ['personsMode', 'friendsMode']:
            #check if this is a corresponding item from type point of view
            if item.get('permid')==None:
                return #no valid torrent
            
            titleField = self.getGuiObj('titleField')
            titleField.SetLabel(item.get('content_name'))
            titleField.Wrap(-1)

            if self.getGuiObj('info_detailsTab').isSelected():
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
                    self.getGuiObj('recommendationField').SetLabel("%d" % rank + " of 20")
                else:
                    self.getGuiObj('recommendationField').SetLabel("")
                if recomm != -1:
                    self.getGuiObj('TasteHeart').setHeartIndex(recomm)
                else:
                    self.getGuiObj('TasteHeart').setHeartIndex(0)
                
                if item['friend']:
                    self.getGuiObj('addAsFriend').Enable(False)
                    self.getGuiObj('addAsFriend').switchTo(ISFRIEND_BITMAP)
                else:
                    self.getGuiObj('addAsFriend').switchBack()
                    self.getGuiObj('addAsFriend').Enable(True)
                    
                self.fillTorrentLists()
            elif self.getGuiObj('advanced_detailsTab').isSelected():
                if item.get('last_seen')!=None:
                    if item['last_seen'] < 0:
                        self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel("never seen online")
                    else:
                        self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel('%s %s'%(friendly_time(item['last_seen']),'ago'))
                else:
                    self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel('')
                if item.get("connected_times")!=None:
                    self.getGuiObj('timesConnectedField', tab = 'personsTab_advanced').SetLabel(str(item["connected_times"]))
                else:
                    item.getGuiObj('timesConnectedField', tab = 'personsTab_advanced').SetLabel("")
                
                addAsFriend = self.getGuiObj('addAsFriend', tab = 'personsTab_advanced')
                if addAsFriend.initDone:
                    if item['friend']:
                        addAsFriend.Enable(False)
                        addAsFriend.switchTo(ISFRIEND_BITMAP)
                    else:
                        addAsFriend.switchBack()
                        addAsFriend.Enable(True)
            
        elif self.mode == 'libraryMode':
            #check if this is a corresponding item from type point of view
            if item.get('infohash')==None:
                return #no valid torrent
            torrent = item
            
            self.play(torrent)
        elif self.mode == 'subscriptionMode':
            pass

        self.currentPanel.Refresh()
        
    def getGuiObj(self, obj_name, tab=None):
        """handy function to retreive an object based on it's name for the current mode"""
        if tab:
            obj_name = tab+'_'+obj_name
        return self.data[self.mode].get(obj_name)
        
    def fillTorrentLists(self):
        ofList = self.getGuiObj("alsoDownloadedField")
#        ofList.SetWindowStyleFlag(wx.LC_LIST)
        cfList = self.getGuiObj("commonFilesField")
#        cfList.SetWindowStyleFlag(wx.LC_LIST)
        try:
            if self.mode != "personsMode" or self.item==None or self.item['permid']==None:
                return
            permid = self.item['permid']
            hash_list = self.guiUtility.peer_manager.getPeerHistFiles(permid)
            torrents_info = self.guiUtility.data_manager.getTorrents(hash_list)
#            # get my download history
#            hist_torr = self.parent.mydb.getPrefList()
#            #print hist_torr
#            files = self.parent.prefdb.getPrefList(self.data['permid'])
#            #live_files = self.torrent_db.getLiveTorrents(files)
#            #get informations about each torrent file based on it's hash
#            torrents_info = self.parent.tordb.getTorrents(files)
#            for torrent in torrents_info[:]:
#                if (not 'info' in torrent) or (len(torrent['info']) == 0) or (not 'name' in torrent['info']):
#                    torrents_info.remove(torrent)
#            #sort torrents based on status: { downloading (green), seeding (yellow),} good (blue), unknown(black), dead (red); 
#            torrents_info.sort(self.status_sort)
#            torrents_info = filter( lambda torrent: not torrent['status'] == 'dead', torrents_info)
            #tempdata[i]['torrents_list'] = torrents_info
            ofList.DeleteAllItems()
            cfList.DeleteAllItems()
            for f in torrents_info:
                #print f
                the_list = None
                if f.get('myDownloadHistory', False):
                    the_list = cfList
                else:
                    the_list = ofList
                index = the_list.InsertStringItem(sys.maxint, f['info']['name'])
                color = "black"
                if f['status'] == 'good':
                    color = "blue"
                elif f['status'] == 'unknown':
                    color = "black"
                elif f['status'] == 'dead':
                    color = "red"
                the_list.SetItemTextColour(index, color)
                #self.ofList.SetStringItem(index, 1, f[1])
            if cfList.GetItemCount() == 0:
                index = cfList.InsertStringItem(sys.maxint, "No common files with this person.")
                font = cfList.GetItemFont(index)
                font.SetStyle(wx.FONTSTYLE_ITALIC)
                cfList.SetItemFont(index, font)
                cfList.SetItemTextColour(index, "#f0c930")
            if ofList.GetItemCount() == 0:
                index = ofList.InsertStringItem(sys.maxint, "No files advertised by this person.")
                font = ofList.GetItemFont(index)
                font.SetStyle(wx.FONTSTYLE_ITALIC)
                ofList.SetItemFont(index, font)
                ofList.SetItemTextColour(index, "#f0c930")
#            self.onListResize(None) 
        except Exception, e:
            print_exc(e)
            ofList.DeleteAllItems()
            cfList.DeleteAllItems()
            index = ofList.InsertStringItem(sys.maxint, "Error getting files list")
            ofList.SetItemTextColour(index, "dark red")
        try:
            ofList.onListResize() #SetColumnWidth(0,wx.LIST_AUTOSIZE)
            cfList.onListResize() #SetColumnWidth(0,wx.LIST_AUTOSIZE)
        except:
            if DEBUG:
                print "could not resize lists in person detail panel"
        
    def tabClicked(self, name):
        print 'Tabclicked: %s' % name
        
        # currently, only tabs in filesDetailspanel work
        if self.mode in ['filesMode', 'libraryMode']:
        
            tabFiles = self.getGuiObj('files_detailsTab')
            tabInfo = self.getGuiObj('info_detailsTab')
            infoPanel = self.getGuiObj('details')
#            sizer = infoPanel.GetContainingSizer()
            filesPanel = self.getGuiObj('filesTab_files')
            
            if name == 'files_detailsTab' and not tabFiles.isSelected():
                tabFiles.setSelected(True)
                tabInfo.setSelected(False)
                self.swapPanel( infoPanel, filesPanel)#, sizer, 3)
                
            elif name == 'info_detailsTab' and not tabInfo.isSelected():
                tabFiles.setSelected(False)
                tabInfo.setSelected(True)
                self.swapPanel( filesPanel, infoPanel)#, sizer, 3)
            else:
                print '%s: Unknown tab %s' % (self.mode,name)
                return

        elif self.mode in ["personsMode","friendsMode"]:
            tabAdvanced = self.getGuiObj('advanced_detailsTab')
            tabInfo = self.getGuiObj('info_detailsTab')
            infoPanel = self.getGuiObj('detailsC')
            advancedPanel = self.getGuiObj('personsTab_advanced')
            if name == 'advanced_detailsTab' and not tabAdvanced.isSelected():
                tabAdvanced.setSelected(True)
                tabInfo.setSelected(False)
                self.swapPanel( infoPanel, advancedPanel)
            elif name == 'info_detailsTab' and not tabInfo.isSelected():
                tabAdvanced.setSelected(False)
                tabInfo.setSelected(True)
                self.swapPanel( advancedPanel, infoPanel)
            else:
                print '%s: Unknown tab %s' % (self.mode,name)
                return
#            print "<mluc> advanced tab has label:",tabAdvanced.GetLabel()
        else:
            print 'standardDetails: Tabs for this mode (%s) not yet implemented' % self.mode
            return
        
        self.setData(self.item)
        
            
    def swapPanel(self, oldpanel, newpanel, sizer=None, index=-1):
        """replaces in a sizer a panel with another one to simulate tabs"""
        if sizer is None:
            sizer = oldpanel.GetContainingSizer()
        #if index not given, use sizer's own replace method
        if index == -1:
            index = 0
            for panel in sizer.GetChildren():
                if panel.GetWindow() == oldpanel:
                    break
                index = index + 1
            if index == len(sizer.GetChildren()):
                return #error: index not found so nothing to change
#            sizerItem = sizer.Replace(oldpanel, newpanel)
#            print "found index is:",index,"number of children in sizer:",len(sizer.GetChildren())
        # remove info tab panel
        sizer.Detach(oldpanel)
        oldpanel.Hide()
        # add files tab panel
        sizer.Insert(index, newpanel, 1, wx.EXPAND, 3)
        if not newpanel.IsShown():
            newpanel.Show()
        newpanel.Layout()
        sizer.Layout()
        newpanel.GetParent().Refresh()
        
    def getAlternativeTabPanel(self, name, parent=None):
        "Load a tabPanel that was not loaded as default"
        panel = self.getGuiObj(name)
        if panel:
            return panel
        else:
            # generate new panel
            xrcResource = os.path.join('Tribler','vwxGUI', name+'.xrc')
            panelName = name
            if parent==None:
                parent = self.currentPanel
            panel = self.loadXRCPanel(xrcResource, panelName, parent=parent)
            
            for element in self.tabElements[name]:
                xrcElement = xrc.XRCCTRL(panel, element)
                if not xrcElement:
                    print 'standardDetails: Error: Could not identify xrc element: %s for mode %s' % (element, self.mode)
                self.data[self.mode][name+'_'+element] = xrcElement
                            
            self.data[self.mode][name] = panel
            
            return panel
        
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

    def download(self):
        torrent = self.item
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
                    print 'standardDetails: download started'
                    
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

    def play(self,torrent):
            infohash = torrent['infohash']
            for ABCTorrentTemp in self.utility.torrents["all"]:
                print >>sys.stderr,"standardDetails: play: comparing",hexlify(ABCTorrentTemp.torrent_hash),hexlify(infohash)
                if ABCTorrentTemp.torrent_hash == infohash:
                    videoplayer = VideoPlayer.getInstance()
                    videoplayer.play(ABCTorrentTemp)
            
    def setTorrentThumb(self, torrent, thumbPanel):
        
        if not thumbPanel:
            return 
        
        thumbBitmap = torrent.get('metadata',{}).get('ThumbnailBitmapLarge')
        thumbnailString = torrent.get('metadata', {}).get('Thumbnail')
        
        if thumbBitmap:
            thumbPanel.setBitmap(thumbBitmap)
            
        elif thumbnailString:
            #print 'Found thumbnail: %s' % thumbnailString
            stream = cStringIO.StringIO(thumbnailString)
            img =  wx.ImageFromStream( stream )
            iw, ih = img.GetSize()
            w, h = thumbPanel.GetSize()
            if (iw/float(ih)) > (w/float(h)):
                nw = w
                nh = int(ih * w/float(iw))
            else:
                nh = h
                nw = int(iw * h/float(ih))
            if nw != iw or nh != ih:
                #print 'Rescale from (%d, %d) to (%d, %d)' % (iw, ih, nw, nh)
                img.Rescale(nw, nh, quality = wx.IMAGE_QUALITY_HIGH)
            bmp = wx.BitmapFromImage(img)
             
            thumbPanel.setBitmap(bmp)
            torrent['metadata']['ThumbnailBitmapLarge'] = bmp
        else:
             thumbPanel.setBitmap(DEFAULT_THUMB)
     
    def addAsFriend(self):
        # add the current user selected in details panel as a friend
        if self.mode == "personsMode":
            peer_data = self.item
            if peer_data!=None and peer_data.get('permid'):
                #update the database
#                    if not self.peer_manager.isFriend(peer_data['permid']):
#                        self.contentFrontPanel.frienddb.deleteFriend(self.data['permid'])
#                    else:
                bAdded = self.guiUtility.peer_manager.addFriendwData(peer_data)
                print "added",peer_data['content_name'],"as friend:",bAdded
                
                #should refresh?
                self.guiUtility.selectPeer(peer_data)

    def swapin_videopanel(self,url,play=True,progressinf=None):
        if not self.showingvideo:
            self.showingvideo = True
            thumbField = self.getGuiObj('thumbField')
            sizer = thumbField.GetContainingSizer()
            sizer.Replace(thumbField,self.videopanel)
            thumbField.Hide()
            self.videopanel.Show()
            sizer.RecalcSizes()
            sizer.Layout()
            
            self.Layout()
            self.Refresh()            

        from Tribler.Video.EmbeddedPlayer import VideoItem
        self.item = VideoItem(url)
        self.videopanel.SetItem(self.item,play=play,progressinf=progressinf)

    def swapout_videopanel(self):

        self.videopanel.reset()
        
        if self.showingvideo:
            self.showingvideo = False

            thumbField = self.getGuiObj('thumbField')
            sizer = self.videopanel.GetContainingSizer()
            sizer.Replace(self.videopanel,thumbField)
            self.videopanel.Hide()
            thumbField.Show()

            self.Layout()
            self.Refresh()            

    def get_video_progressinf(self):
        return self.videopanel

    def reset_videopanel(self):
        self.videopanel.reset()
