import wx, os, sys, os.path, random
import wx.xrc as xrc
from binascii import hexlify
from time import sleep,time
import math
from traceback import print_exc
import cStringIO

from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.utilities import *
from Tribler.Dialogs.MugshotManager import MugshotManager
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
from Tribler.vwxGUI.torrentManager import TorrentDataManager
from Tribler.unicode import bin2unicode
from safeguiupdate import FlaglessDelayedInvocation
#from Tribler.vwxGUI.tribler_topButton import tribler_topButton
from Utility.constants import COL_PROGRESS
from Tribler.Dialogs.GUIServer import GUIServer


DETAILS_MODES = ['filesMode', 'personsMode', 'profileMode', 'libraryMode', 'friendsMode', 'subscriptionsMode', 'messageMode']
DEBUG = True

def showInfoHash(infohash):
    if infohash.startswith('torrent'):    # for testing
        return infohash
    try:
        n = int(infohash)
        return str(n)
    except:
        pass
    return encodestring(infohash).replace("\n","")
            
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
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.mm = MugshotManager.getInstance()
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
                                            'download', 'tabs', ('files_detailsTab','tabs'), ('info_detailsTab','tabs'), 'TasteHeart', 'details', 'peopleWhoField']
        self.modeElements['personsMode'] = ['TasteHeart', 'recommendationField','addAsFriend', 'commonFilesField',
                                            'alsoDownloadedField', 'info_detailsTab', 'advanced_detailsTab','detailsC',
                                            'titleField','statusField','thumbField']
        self.modeElements['libraryMode'] = ['titleField', 'popularityField1', 'popularityField2', 'creationdateField', 
                                            'descriptionField', 'sizeField', 'thumbField', 'up', 'down', 'refresh', 
                                            'download', 'files_detailsTab', 'info_detailsTab', 'TasteHeart', 'details', 'peopleWhoField']
        self.modeElements['profileMode'] = ['descriptionField0']
        
        
        self.modeElements['subscriptionsMode'] = ['titleField', 'receivedToday', 'subscrTodayField', 'receivedYesterday', 'subscrYesterdayField', 'receivedTotal']
        
        self.tabElements = {'filesTab_files': [ 'download', 'includedFiles', 'filesField'],                            
                            'personsTab_advanced': ['lastExchangeField', 'noExchangeField', 'timesConnectedField','addAsFriend','similarityValueField'],
                            'libraryTab_files': [ 'download', 'includedFiles'],
                            'profileDetails_Quality': ['descriptionField0','howToImprove','descriptionField1'],
                            'profileDetails_Files': ['descriptionField0','descriptionField1','takeMeThere0'],
                            'profileDetails_Persons': ['descriptionField0','descriptionField1','takeMeThere0'],
                            'profileDetails_Download': ['descriptionField','descriptionField0','descriptionField1','descriptionField2','descriptionField3','descriptionField4','descriptionField5','takeMeThere0','takeMeThere1'],
                            'profileDetails_Presence': ['descriptionField','descriptionField0','descriptionField1','descriptionField2','descriptionField3','descriptionField4','descriptionField5', 'takeMeThere0']}
            
        self.statdlElements = ['st28c','st30c','download1','percent1','download2','percent2','download3','percent3','download4','percent4']
            
        self.guiUtility.initStandardDetails(self)
        
        self.subscr_old_source = None


    def addComponents(self):
        self.SetBackgroundColour(wx.Colour(102,102,102))
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        print "tb"
        print self.GetSize()
    
        
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
        self.currentPanel.SetBackgroundColour("red")
        
        self.currentPanel.Show(True)
        
        if self.oldpanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            #self.oldpanel.Disable()
        
        self.hSizer.Insert(0, self.currentPanel, 0, wx.ALL|wx.EXPAND, 0)
        
            
#        self.currentPanel.Layout()
        wx.CallAfter(self.hSizer.Layout)
#        wx.CallAfter(self.currentPanel.Refresh)
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
            xrcResource = os.path.join(self.utility.getPath(),'Tribler','vwxGUI', modeString+'Details.xrc')
            panelName = modeString+'Details'
            currentPanel = self.loadXRCPanel(xrcResource, panelName)
            # Save paneldata in self.data
            self.data[self.mode]['panel'] = currentPanel
            #titlePanel = xrc.XRCCTRL(currentPanel, 'titlePanel')
            
            if self.modeElements.has_key(self.mode):
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
            else:
                self.modeElements[self.mode] = []
            
            # do extra init
            if modeString == 'files' or modeString == 'library':
                self.getGuiObj('up').setBackground(wx.WHITE)
                self.getGuiObj('down').setBackground(wx.WHITE)
                self.getGuiObj('refresh').setBackground(wx.WHITE)
                self.getGuiObj('TasteHeart').setBackground(wx.WHITE)
                self.setListAspect2OneColumn("peopleWhoField")
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
                ofList = self.getGuiObj("alsoDownloadedField")
                cfList = self.getGuiObj("commonFilesField")
                ofList.setOtherList(cfList)
            
            elif modeString == "profile":
                self.data[self.mode]['profileDetails_Overall'] = currentPanel #also add first panel as an named element in the data list
#                self.item = "profileDetails_Overall" #the name of the panel that's currently selected
                self.getAlternativeTabPanel('profileDetails_Quality', parent=self).Hide() #parent is self because it is not a tab, it replaces the details panel
                self.getAlternativeTabPanel('profileDetails_Files', parent=self).Hide() #parent is self because it is not a tab, it replaces the details panel
                self.getAlternativeTabPanel('profileDetails_Persons', parent=self).Hide() #parent is self because it is not a tab, it replaces the details panel
                self.getAlternativeTabPanel('profileDetails_Download', parent=self).Hide() #parent is self because it is not a tab, it replaces the details panel
                self.getAlternativeTabPanel('profileDetails_Presence', parent=self).Hide() #parent is self because it is not a tab, it replaces the details panel
                
        return currentPanel
    
    def loadStatusPanel(self):
        currentPanel = self.loadXRCPanel(os.path.join(self.utility.getPath(),'Tribler','vwxGUI', 'statusDownloads.xrc'), 'statusDownloads')
        mode = 'status'
        for element in self.statdlElements:
            xrcElement = None
            name = None
            if type(element) == str:
                xrcElement = xrc.XRCCTRL(currentPanel, element)
                name = element
            elif type(element) == tuple:
                name = element[0]
                xrcElement = xrc.XRCCTRL(self.data[mode][element[1]],name)
            if not xrcElement:
                print 'standardDetails: Error: Could not identify xrc element: %s for mode %s' % (element, mode)
            if name:
                self.data[mode][name] = xrcElement
        return currentPanel

    
    def loadXRCPanel(self, filename, panelName, parent=None):
        try:
            currentPanel = None
            if not os.path.exists(filename):
                dummyFile = os.path.join(self.utility.getPath(),'Tribler','vwxGUI', 'dummy.xrc')
                filename = dummyFile
                panelName = "dummy"
            res = xrc.XmlResource(filename)
            # create panel
            if parent is None:
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
            elif self.mode in ['subscriptionsMode']:
                return self.item['url']
            else:
                print 'standardDetails: Error in getIdentifier for mode %s, item=%s' % (self.mode,self.item)
        except:
            print 'standardDetails: Error in getIdentifier for mode %s, item=%s' % (self.mode,self.item)
        
    def setData(self, item):
        self.item = item
        if not item:
            return
        if self.mode in ['filesMode', 'libraryMode']:
            #check if this is a corresponding item from type point of view
            if item.get('infohash') is None:
                return #no valid torrent
            torrent = item
            
            titleField = self.getGuiObj('titleField')
            titleField.SetLabel(torrent.get('content_name'))
            titleField.Wrap(-1)
            
            self.setTorrentThumb(self.mode, torrent, self.getGuiObj('thumbField'))        

    
            if self.getGuiObj('info_detailsTab').isSelected():
                # The info tab is selected, show normal torrent info
                descriptionField = self.getGuiObj('descriptionField')
                descrtxt = ''
                if 'metadata' in torrent:
                    metadata = torrent['metadata']

                    encoding = None
                    if 'encoding' in metadata and metadata['encoding'].strip():
                        encoding = metadata['encoding']

                    flag = False
                    for key in ['comment','comment-utf8','Description']: # reverse priority
                        if key in metadata: # If vuze torrent
                            tdescrtxt = metadata[key]
                            if key == 'comment-utf8':
                                tencoding = 'utf_8'
                            else:
                                tencoding = encoding
                            descrtxt = bin2unicode(tdescrtxt,tencoding)
                            flag = True
                    if not flag:
                        if 'source' in torrent:
                            s = torrent['source']
                            if s == 'BC':
                                s = 'Received from other user'
                            descrtxt = "Source: "+s

                descriptionField.SetLabel(descrtxt)
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
                
                # Call a function to retrieve similar torrent data
                self.fillSimTorrentsList(item['infohash'])

                # Show or hide download button in detailstab
                if self.mode == 'filesMode':
                    downloadButton = self.getGuiObj('download')
                    if self.showDownloadbutton(self.mode, torrent):
                        downloadButton.Show()
                    else:
                        downloadButton.Hide()
                
            elif self.getGuiObj('files_detailsTab').isSelected():
                filesList = self.getGuiObj('includedFiles', tab = 'filesTab_files')
                filesList.setData(torrent)
                self.getGuiObj('filesField', tab = 'filesTab_files').SetLabel('%d' % filesList.getNumFiles())
                # Remove download button for libraryview
                downloadButton = self.getGuiObj('download', tab='filesTab_files')
                if self.showDownloadbutton(self.mode, torrent):
                    downloadButton.Show()
                else:
                    downloadButton.Hide()
                    
                
            else:
                print 'standardDetails: error: unknown tab selected'
            
                        
        elif self.mode in ['personsMode', 'friendsMode']:
            #check if this is a corresponding item from type point of view
            if item.get('permid') is None:
                return #no valid torrent
            
            titleField = self.getGuiObj('titleField')
            titleField.SetLabel(item.get('content_name'))
            titleField.Wrap(-1)
            
            #set the picture
            try:
                bmp = self.mm.get_default('personsMode','DEFAULT_THUMB')
                # Check if we have already read the thumbnail and metadata information from this torrent file
                if item.get('metadata'):
                    bmp = item['metadata'].get('ThumbnailBitmap')
                    if not bmp:
                        bmp = self.mm.get_default('personsMode','DEFAULT_THUMB')
                else:
                    guiserver = GUIServer.getInstance()
                    guiserver.add_task(lambda:self.loadMetadata(item),0)
                
                thumbField = self.getGuiObj("thumbField")
                thumbField.setBitmap(bmp)
                width, height = thumbField.GetSize()
                d = 1
                thumbField.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
                thumbField.Refresh()
                
            except:
                print_exc(file=sys.stderr)
            

            if self.getGuiObj('info_detailsTab').isSelected():
                #recomm = random.randint(0,4)
                rank = self.guiUtility.peer_manager.getRank(peer_data=item)#['permid'])
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
                    if rank == 1:
                        self.getGuiObj('recommendationField').SetLabel("%d" % rank + "st of top 20")
                    elif rank == 2:
                        self.getGuiObj('recommendationField').SetLabel("%d" % rank + "nd of top 20")                        
                    elif rank == 3:
                        self.getGuiObj('recommendationField').SetLabel("%d" % rank + "rd of top 20")
                    else:
                        self.getGuiObj('recommendationField').SetLabel("%d" % rank + "th of top 20")
                else:
                    self.getGuiObj('recommendationField').SetLabel("")
                if recomm != -1:
                    self.getGuiObj('TasteHeart').setHeartIndex(recomm)
                else:
                    self.getGuiObj('TasteHeart').setHeartIndex(0)
                
                if item.get('online'):
                    self.getGuiObj('statusField').SetLabel( 'online')
                else:
                    self.getGuiObj('statusField').SetLabel('connected  %s' % friendly_time(item['last_seen']))
                
                if item['friend']:
#                    self.getGuiObj('addAsFriend').Enable(False)
                    isfriend = self.mm.get_default('personsMode','ISFRIEND_BITMAP')
                    isfriend_clicked = self.mm.get_default('personsMode','ISFRIEND_CLICKED_BITMAP')
                    self.getGuiObj('addAsFriend').switchTo(isfriend,isfriend_clicked)
                else:
                    self.getGuiObj('addAsFriend').switchBack()
#                    self.getGuiObj('addAsFriend').Enable(True)
#                if item.get('online'):
                    
                self.fillTorrentLists()
            elif self.getGuiObj('advanced_detailsTab').isSelected():
                if item.get('last_seen') is not None:
                    if item['last_seen'] < 0:
                        self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel("never seen online")
                    else:
                        self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel('%s %s'%(friendly_time(item['last_seen']),'ago'))
                else:
                    self.getGuiObj('lastExchangeField', tab = 'personsTab_advanced').SetLabel('')
                if item.get("connected_times") is not None:
                    self.getGuiObj('timesConnectedField', tab = 'personsTab_advanced').SetLabel(str(item["connected_times"]))
                else:
                    self.getGuiObj('timesConnectedField', tab = 'personsTab_advanced').SetLabel("")
                if item.get("similarity") is not None:
                    self.getGuiObj('similarityValueField', tab = 'personsTab_advanced').SetLabel("%.1f" % item["similarity"])
                else:
                    self.getGuiObj('similarityValueField', tab = 'personsTab_advanced').SetLabel("")
                
                addAsFriend = self.getGuiObj('addAsFriend', tab = 'personsTab_advanced')
                if addAsFriend.initDone:
                    if item['friend']:
                        isfriend = self.mm.get_default('personsMode','ISFRIEND_BITMAP')
                        isfriend_clicked = self.mm.get_default('personsMode','ISFRIEND_CLICKED_BITMAP')
                        addAsFriend.switchTo(isfriend,isfriend_clicked)
                    else:
                        addAsFriend.switchBack()
#                        self.getGuiObj('addAsFriend').switchBack()
            
        elif self.mode == 'subscriptionsMode':
            if item.get('url') is None:
                return #no valid url
            subscrip = item
            rssurl = subscrip.get('url')
            
            if self.subscr_old_source is not None and self.subscr_old_source == rssurl:
                print >>sys.stderr,"standardDetails: setData: subscriptionMode: Not refreshing"
                return # no need to refresh
            self.subscr_old_source = rssurl
            
            titleField = self.getGuiObj('titleField')
            titleField.SetLabel(rssurl)
            titleField.Wrap(-1)

            bcsub = self.utility.lang.get('buddycastsubscription')
            if rssurl == bcsub:
                rssurl = 'BC'
            
            # Gather data for views
            torrents = self.data_manager.getFromSource(rssurl)
            todayl = []
            yesterdayl = []
            now = long(time())
            sotoday = long(math.floor(now / (24*3600.0))*24*3600.0)
            soyester = long(sotoday - (24*3600.0))
            for torrent in torrents:
                    if torrent['inserttime'] > sotoday:
                        todayl.append(torrent)
                    elif torrent['inserttime'] > soyester:
                        yesterdayl.append(torrent)
            
            todayl.sort(reverse_torrent_insertime_cmp)
            yesterdayl.sort(reverse_torrent_insertime_cmp)
            
            # Update Today view
            todayField = self.getGuiObj('receivedToday')
            todaystr = "   Today ("+str(len(todayl))+")"
            todayField.SetLabel(todaystr)

            todayList = self.getGuiObj('subscrTodayField')
            todayList.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_SINGLE_SEL|wx.LC_NO_HEADER)
            if todayList.GetColumnCount() == 0:
                todayList.InsertColumn(0, "Torrent",wx.LIST_FORMAT_LEFT,280)
            todayList.DeleteAllItems()
            for torrent in todayl:
                todayList.Append([torrent['content_name']])

            # Update Yesterday view
            ydayField = self.getGuiObj('receivedYesterday')
            ydaystr = "   Yesterday ("+str(len(yesterdayl))+")"
            ydayField.SetLabel(ydaystr)

            ydayList = self.getGuiObj('subscrYesterdayField')
            ydayList.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_SINGLE_SEL|wx.LC_NO_HEADER)
            if ydayList.GetColumnCount() == 0:
                ydayList.InsertColumn(0, "Torrent",wx.LIST_FORMAT_LEFT,280)
            ydayList.DeleteAllItems()
            for torrent in yesterdayl:
                ydayList.Append([torrent['content_name']])

        
        elif self.mode == 'profileMode':
            tab = None
            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            ## --- Overall performance  !!!! we'll leave it probably out!!!
            if self.currentPanel == self.getGuiObj('profileDetails'):
                text = self.utility.lang.get("profileDetails_Overall_description", giveerror=False)
                #self.getGuiObj('descriptionField0').SetLabel(text % item.get('overall_rank'))            
            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            # --- Quality of tribler recommendations    
            elif self.currentPanel == self.getGuiObj('profileDetails_Quality'):
                tab = 'profileDetails_Quality'
                count = 0            
                if item is not None:
                    if item.has_key('downloaded_files'):
                        count = item['downloaded_files']
                text = self.utility.lang.get("profileDetails_Quality_description", giveerror=False)
                text1 = self.utility.lang.get("profileDetails_Quality_improve", giveerror=False)
                if count < 10:
                    only = self.utility.lang.get("profileDetails_Quality_description_onlyword", giveerror=False)
                else:
                    only=""
                self.getGuiObj('descriptionField0', tab = 'profileDetails_Quality').SetLabel(text % (only,count))
                self.getGuiObj('descriptionField1', tab = 'profileDetails_Quality').SetLabel(text1)
            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            # --- Discovered Files
            elif self.currentPanel == self.getGuiObj('profileDetails_Files'):  
                tab = 'profileDetails_Files'              
                count = 0            
                if item is not None:
                    if item.has_key('taste_files'):
                        count = item['taste_files']
                text = self.utility.lang.get("profileDetails_Files_description", giveerror=False)
                text1 = self.utility.lang.get("profileDetails_Files_improve", giveerror=False)
                self.getGuiObj('descriptionField0', tab = 'profileDetails_Files').SetLabel(text % count)
                self.getGuiObj('descriptionField1', tab = 'profileDetails_Files').SetLabel(text1)            
            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            # --- Discovered Persons
            elif self.currentPanel == self.getGuiObj('profileDetails_Persons'):
                tab = 'profileDetails_Persons'
                count = 0            
                if item is not None:
                    if item.has_key('similar_peers'):
                        count = item['similar_peers']
                text = self.utility.lang.get("profileDetails_Persons_description", giveerror=False)
                text1 = self.utility.lang.get("profileDetails_Persons_improve", giveerror=False)
                self.getGuiObj('descriptionField0', tab = 'profileDetails_Persons').SetLabel(text % count)
                self.getGuiObj('descriptionField1', tab = 'profileDetails_Persons').SetLabel(text1)  
            # --------------------------------------------------------------------------------------------------------------------------------------------------------
            ## --- Optimal download speed    
            elif self.currentPanel == self.getGuiObj('profileDetails_Download'):    
                tab = 'profileDetails_Download'
                text = self.utility.lang.get("profileDetails_Download_info", giveerror=False)
                self.getGuiObj('descriptionField', tab = 'profileDetails_Download').SetLabel(text)

                maxuploadrate = self.guiUtility.utility.config.Read('maxuploadrate', 'int') #kB/s
                if ( maxuploadrate == 0 ):
                    text1 = self.utility.lang.get("profileDetails_Download_UpSpeedMax", giveerror=False)
                else:
                    text1 = self.utility.lang.get("profileDetails_Download_UpSpeed", giveerror=False)
                    text1 = text1 % maxuploadrate                    
    #            maxuploadslots = self.guiUtility.utility.config.Read('maxupload', "int")
    #            if ( maxuploadslots == 0 ):
    #                text2 = self.utility.lang.get("profileDetails_Download_UpSlotsMax", giveerror=False)
    #            else:
    #                text2 = self.utility.lang.get("profileDetails_Download_UpSlots", giveerror=False)
    #                text2 = text2 % maxuploadslots
    #            maxdownloadrate = self.guiUtility.utility.config.Read('maxdownloadrate', "int")
    #            if ( maxdownloadrate == 0 ):
    #                text3 = self.utility.lang.get("profileDetails_Download_DlSpeedMax", giveerror=False)
    #            else:
    #                text3 = self.utility.lang.get("profileDetails_Download_DlSpeed", giveerror=False)
    #                text3 = text3 % maxdownloadrate
    #            text = "%s\n%s\n%s" % (text1,text2,text3)
                text = "%s" % (text1)
                self.getGuiObj('descriptionField0', tab = 'profileDetails_Download').SetLabel( text)            
                text = self.utility.lang.get("profileDetails_Download_UpSpeed_improve", giveerror=False)
                self.getGuiObj('descriptionField1', tab = 'profileDetails_Download').SetLabel(text)
                #
                count = 0
                if item is not None:
                    if item.has_key('friends_count'):
                        count = item['friends_count']
                text = self.utility.lang.get("profileDetails_Download_Friends", giveerror=False)
                self.getGuiObj('descriptionField2', tab = 'profileDetails_Download').SetLabel(text % count)
                text = self.utility.lang.get("profileDetails_Download_Friends_improve", giveerror=False)
                self.getGuiObj('descriptionField3', tab = 'profileDetails_Download').SetLabel(text)
                
                if self.guiUtility.isReachable:
                    text1 = self.utility.lang.get("profileDetails_Download_VisibleYes", giveerror=False)
                    #text2 = self.utility.lang.get("profileDetails_Download_VisibleYes", giveerror=False)
                    self.getGuiObj('descriptionField4', tab = 'profileDetails_Download').SetLabel(text1)
                    self.getGuiObj('descriptionField5', tab = 'profileDetails_Download').SetLabel("")
                else:
                    text1 = self.utility.lang.get("profileDetails_Download_VisibleNo", giveerror=False)
                    text2 = self.utility.lang.get("profileDetails_Download_Visible_improve", giveerror=False)
                    self.getGuiObj('descriptionField4', tab = 'profileDetails_Download').SetLabel(text1)
                    self.getGuiObj('descriptionField5', tab = 'profileDetails_Download').SetLabel(text2)
            # --------------------------------------------------------------------------------------------------------------------------------------------------------        
            ## --- Optimal download speed
            elif self.currentPanel == self.getGuiObj('profileDetails_Presence'):    
                tab = 'profileDetails_Presence'
                text = self.utility.lang.get("profileDetails_Presence_info", giveerror=False)
                self.getGuiObj('descriptionField', tab = 'profileDetails_Presence').SetLabel(text)
                
                count = 0
                if item is not None:
                    if item.has_key('friends_count'):
                        count = item['friends_count']
                # use text that is also used in 'optimal download details        
                text = self.utility.lang.get("profileDetails_Download_Friends", giveerror=False)
                self.getGuiObj('descriptionField0', tab = 'profileDetails_Presence').SetLabel(text % count)
                text = self.utility.lang.get("profileDetails_Download_Friends_improve", giveerror=False)
                self.getGuiObj('descriptionField1', tab = 'profileDetails_Presence').SetLabel(text)
                
                text = self.utility.lang.get("profileDetails_Presence_Sharingratio", giveerror=False)
                self.getGuiObj('descriptionField2', tab = 'profileDetails_Presence').SetLabel(text % count)
                text = self.utility.lang.get("profileDetails_Presence_Sharingratio_improve", giveerror=False)
                self.getGuiObj('descriptionField3', tab = 'profileDetails_Presence').SetLabel(text)

                text = self.utility.lang.get("profileDetails_Presence_VersionNo", giveerror=False)
                self.getGuiObj('descriptionField4', tab = 'profileDetails_Presence').SetLabel(text)
                text = self.utility.lang.get("profileDetails_Presence_VersionNo_improve", giveerror=False)
                self.getGuiObj('descriptionField5', tab = 'profileDetails_Presence').SetLabel(text)
            else:
                tab = "error"
            if tab != "error":
                if self.reHeightToFit(tab):
                    self.currentPanel.Layout()
                    self.currentPanel.SetAutoLayout(1)
                    self.hSizer.Layout()
        else:
            print "standardDetails: setData: No entry for mode",self.mode
                    
        self.currentPanel.Refresh()
    
    def reHeightToFit(self, tab=None):
        """the ideea is to itterate through all object mentioned in the list of 
        object for current tab and to reposition them on y axis so that all of
        them are fully visible
        returns true if elements have been repositioned so that the layout be redone"""
        print "<mluc> trying to reheight panel for mode",self.mode,"and tab",tab
        VERTICAL_SPACER=3
        bElementsMoved = False
        try:
            if tab is None:
                list = self.modeElements[self.mode]
            else:
                list = self.tabElements[tab]
            print "<mluc> there are",len(list),"elements waiting to be moved"
            #check to see it it's worth trying to reposition elements
            if len(list)>1:
                prevElement = self.getGuiObj(list[0], tab)
                prevElement.Wrap(284)
                print "<mluc> first element",list[0],"is at",prevElement.GetPosition().y,"and has height",prevElement.GetSize().height
                for index in range(1,len(list)):
                    currentElement = self.getGuiObj(list[index], tab)
                    print "<mluc> element",list[index],"is at",currentElement.GetPosition().y,"and has height",currentElement.GetSize().height
                    if currentElement.GetPosition().y < prevElement.GetPosition().y + prevElement.GetSize().height + VERTICAL_SPACER:
                        bElementsMoved = True
                        print "<mluc> moving",list[index],"from",currentElement.GetPosition().y,"to",(prevElement.GetPosition().y + prevElement.GetSize().height + VERTICAL_SPACER)
                        #reposition element as it overlaps the one above
                        currentElement.SetPosition(wx.Point(currentElement.GetPosition().x,prevElement.GetPosition().y + prevElement.GetSize().height + VERTICAL_SPACER))
                    prevElement = currentElement
        except:
            print_exc()
        return bElementsMoved
    
    def showDownloadbutton(self, mode, torrent):
        return (self.mode == 'filesMode' and not torrent.get('eventComingUp') == 'downloading') or \
               (self.mode == 'libraryMode' and torrent.get('eventComingUp') == 'notDownloading')
               
                 
    def getGuiObj(self, obj_name, tab=None):
        """handy function to retreive an object based on it's name for the current mode"""
        if tab:
            obj_name = tab+'_'+obj_name
        return self.data[self.mode].get(obj_name)
     
    def fillSimTorrentsList(self, infohash):
        sim_torrent_list = self.getGuiObj('peopleWhoField')
        try:
            sim_torrents = self.data_manager.getSimItems(infohash, 8)
            sim_torrent_list.DeleteAllItems()
            sim_torrent_list.setInfoHashList(None)
            alist = []
            for torrent,name,sim in sim_torrents:
                index = sim_torrent_list.InsertStringItem(sys.maxint, name)
                alist.append(torrent)
#                color = "black"
#                f = self.data_manager.getTorrent(torrent)
#                if f['status'] == 'good':
#                    color = "blue"
#                elif f['status'] == 'unknown':
#                    color = "black"
#                elif f['status'] == 'dead':
#                    color = "red"
#                sim_torrent_list.SetItemTextColour(index, color)
                
            if sim_torrent_list.GetItemCount() == 0:
                index = sim_torrent_list.InsertStringItem(sys.maxint, "No similar files found yet.")
                font = sim_torrent_list.GetItemFont(index)
                font.SetStyle(wx.FONTSTYLE_ITALIC)
                sim_torrent_list.SetItemFont(index, font)
                sim_torrent_list.SetItemTextColour(index, "#222222")
            else:
                sim_torrent_list.setInfoHashList(alist)
                
        except Exception, e:
            print_exc()
            sim_torrent_list.DeleteAllItems()
            sim_torrent_list.setInfoHashList(None)
            index = sim_torrent_list.InsertStringItem(0, "Error getting similar files list")
            sim_torrent_list.SetItemTextColour(index, "dark red")
        try:
            sim_torrent_list.onListResize() #SetColumnWidth(0,wx.LIST_AUTOSIZE)
        except:
            if DEBUG:
                print "could not resize lists in sim_torrent_list panel" 
        
        
    def fillTorrentLists(self):
        ofList = self.getGuiObj("alsoDownloadedField")
#        ofList.SetWindowStyleFlag(wx.LC_LIST)
        cfList = self.getGuiObj("commonFilesField")
#        cfList.SetWindowStyleFlag(wx.LC_LIST)
        try:
            if self.mode != "personsMode" or self.item is None or self.item['permid'] is None:
                return
            permid = self.item['permid']
            hash_list = self.guiUtility.peer_manager.getPeerHistFiles(permid)
            torrents_info = self.data_manager.getTorrents(hash_list)
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
            ofList.setInfoHashList(None)
            alist = []
            for f in torrents_info:
                #print f
                the_list = None
                infohash = f.get('infohash')
                if f.get('myDownloadHistory', False):
                    the_list = cfList
                else:
                    the_list = ofList
                if f['status'] != 'dead':
                    index = the_list.InsertStringItem(sys.maxint, f['info']['name'])
                    if the_list == ofList:
                        alist.append(infohash)
#                color = "black"
#                if f['status'] == 'good':
#                    color = "blue"
#                elif f['status'] == 'unknown':
#                    color = "black"
#                elif f['status'] == 'dead':
#                    color = "red"
#                the_list.SetItemTextColour(index, color)
                #self.ofList.SetStringItem(index, 1, f[1])
            if cfList.GetItemCount() == 0:
                index = cfList.InsertStringItem(sys.maxint, "No common files with this person.")
                font = cfList.GetItemFont(index)
                font.SetStyle(wx.FONTSTYLE_ITALIC)
                cfList.SetItemFont(index, font)
                cfList.SetItemTextColour(index, "#222222")
                cfList.isEmpty = True    # used by DLFilesList to remove "No common files with this person."
            else:
                cfList.isEmpty = False
            if ofList.GetItemCount() == 0:
                index = ofList.InsertStringItem(sys.maxint, "No files advertised by this person.")
                font = ofList.GetItemFont(index)
                font.SetStyle(wx.FONTSTYLE_ITALIC)
                ofList.SetItemFont(index, font)
                ofList.SetItemTextColour(index, "#222222")
            else:
                ofList.setInfoHashList(alist)
#            self.onListResize(None) 
        except:
            print_exc()
            ofList.DeleteAllItems()
            cfList.DeleteAllItems()
            ofList.setInfoHashList(None)
            index = ofList.InsertStringItem(sys.maxint, "Error getting files list")
            ofList.SetItemTextColour(index, "#222222")
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

        elif self.mode == "profileMode":
#            print "<mluc> try to switch to",name
            if name.startswith("bgPanel"):
                name = "profileDetails"+name[7:]
#            if name == "profileDetails_Overall":
#                name = 'panel'
#            print "<mluc> current panel is:",self.item
#            if self.item is None:
#                self.item = 'panel'
            panel1 = self.currentPanel #getGuiObj(self.item)
            panel2 = self.getGuiObj(name)
            if panel1 is not None and panel2 is not None and panel1 != panel2:
#===============================================================================
#                print "<mluc> switch from %s[%s] to %s[%s]" % (panel1.GetName(), panel1.GetParent().GetName(), panel2.GetName(), panel2.GetParent().GetName())
#                if isinstance(panel1,tribler_topButton):
#                    print "<mluc> set unselected for",panel1.GetName()
#                    panel1.setSelected(False)
#                else:
#                    print "<mluc> panel1 ",panel1.GetName()," is of type ",panel1.__class__.__name__
#                if panel2.__class__.__name__.endswith("tribler_topButton"):
#                    print "<mluc> set selected for",panel2.GetName()
#                    panel2.setSelected(True)
#                else:
#                    print "<mluc> panel2 ",panel2.GetName()," is of type ",panel2.__class__.__name__
#===============================================================================
                self.swapPanel(panel1, panel2)
                #each time the panel changes, update the 'panel' reference in data list
                self.data[self.mode]['panel'] = panel2
                #actually, update the currentPanel reference
                self.currentPanel = panel2
#                self.item = name
#            else:
#                print "<mluc> can't switch, one of the panel is None or the same panel"

                print "<mluc> switch from %s[%s] to %s[%s]" % (panel1.GetName(), panel1.GetParent().GetName(), panel2.GetName(), panel2.GetParent().GetName())
        else:
            print 'standardDetails: Tabs for this mode (%s) not yet implemented' % self.mode
            return
        
        self.setData(self.item)

            
    def swapPanel(self, oldpanel, newpanel, sizer=None, index=-1):
        """replaces in a sizer a panel with another one to simulate tabs"""
        if sizer is None:
            sizer = oldpanel.GetContainingSizer()
            if not sizer:
                return #could not swap
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
        print "<mluc> found sizer equal to hSizer?",(sizer==self.hSizer)
        # add files tab panel
        sizer.Insert(index, newpanel, 0, wx.ALL|wx.EXPAND, 0)
        if not newpanel.IsShown():
            newpanel.Show()
#        newpanel.Layout()
        self.currentPanel.Layout()
        self.currentPanel.SetAutoLayout(1)
        #wx.CallAfter(self.hSizer.Layout)
        sizer.Layout()
#        newpanel.GetParent().Refresh()
        
    def getAlternativeTabPanel(self, name, parent=None):
        "Load a tabPanel that was not loaded as default"
        panel = self.getGuiObj(name)
        if panel:
            return panel
        else:
            # generate new panel
            xrcResource = os.path.join(self.utility.getPath(),'Tribler','vwxGUI', name+'.xrc')
            if os.path.exists(xrcResource):
                panelName = name
                if parent is None:
                    parent = self.currentPanel
                panel = self.loadXRCPanel(xrcResource, panelName, parent=parent)
            if panel is not None and self.tabElements.has_key(name):
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

    def download(self, torrent = None, dest = None):
        if torrent == None:
            torrent = self.item
            
        src1 = os.path.join(torrent['torrent_dir'], 
                            torrent['torrent_name'])
        src2 = os.path.join(self.utility.getConfigPath(), 'torrent2', torrent['torrent_name'])
        if torrent.get('content_name'):
            name = torrent['content_name']
        elif torrent.get('info') and torrent['info'].get('name'):
            name = torrent['info']['name']
        else:
            name = showInfoHash(torrent['infohash'])
        #start_download = self.utility.lang.get('start_downloading')
        #str = name + "?"
        if os.path.isfile(src1):
            src = src1
        else:
            src = src2
            
        if os.path.isfile(src):
#            str = self.utility.lang.get('download_start') + u' ' + name + u'?'
#            dlg = wx.MessageDialog(self, str, self.utility.lang.get('click_and_download'), 
#                                        wx.YES_NO|wx.NO_DEFAULT|wx.ICON_INFORMATION)
#            result = dlg.ShowModal()
#            dlg.Destroy()
#            if result == wx.ID_YES:
            ret = self.utility.queue.addtorrents.AddTorrentFromFile(src, dest = dest)
            if ret and ret[0]:
                print 'standardDetails: download started'
                # save start download time.
                torrent['download_started'] = time()
                torrent['progress'] = 0.0
                self.data_manager.setBelongsToMyDowloadHistory(torrent['infohash'], True)
                return True        
            else:
                return False
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
                return True
            else:
                return False

    def setTorrentThumb(self, mode, torrent, thumbPanel):
        
        if not thumbPanel:
            return 
        
        thumbPanel.setBackground(wx.BLACK)
        if mode in  ['filesMode', 'libraryMode']:
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
                default = self.mm.get_default('filesMode','BIG_DEFAULT_THUMB')
                thumbPanel.setBitmap(default)
                
        elif mode in ['personsMode', 'friendMode']:
            # get thumbimage of person
            if False:
                pass
            else:
                default = self.mm.get_default('personsMode','DEFAULT_THUMB')
                thumbPanel.setBitmap(default)
                
    def addAsFriend(self):
        # add the current user selected in details panel as a friend
        if self.mode in ["personsMode","friendsMode"]:
            peer_data = self.item
            if peer_data is not None and peer_data.get('permid'):
                #update the database
#                    if not self.peer_manager.isFriend(peer_data['permid']):
#                        self.contentFrontPanel.frienddb.deleteFriend(self.data['permid'])
#                    else:
                if self.guiUtility.peer_manager.isFriend(peer_data['permid']):
                    bRemoved = self.guiUtility.peer_manager.deleteFriendwData(peer_data)
                    print "removed friendship with",peer_data['content_name'],":",bRemoved
                else:
                    bAdded = self.guiUtility.peer_manager.addFriendwData(peer_data)
                    print "added",peer_data['content_name'],"as friend:",bAdded
                
                #should refresh?
                self.guiUtility.selectPeer(peer_data)



    def refreshTorrentStats_network_callback(self):
        """ Called by network thread """
        self.invokeLater(self.refreshTorrentStats)
        
    def refreshTorrentStats(self):
        """ Called by GUI thread """
        active = self.utility.torrents["active"]
        
        tl = []
        for ABCTorrentTemp in active:
            progresstxt = ABCTorrentTemp.getColumnText(COL_PROGRESS)[:-1]
            progress = float(progresstxt)
            if progress < 100.0:
                tl.append([progress,ABCTorrentTemp])
            
        # Reverse sort on percentage done, get top 4 
        tl.sort(revtcmp)
        ml = min(len(tl),4)
        newtl = tl[:ml]
        
        for i in range(4):
            if i < ml:
                elem = newtl[i]
                progresstxt = str(elem[0])+'%'
                ABCTorrentTemp = elem[1]
                file = ABCTorrentTemp.info['name']
            else:
                progresstxt = ''
                file = ''
            tname = 'download'+str(i+1)
            pname = 'percent'+str(i+1)
            tlabel = self.data['status'][tname]
            plabel = self.data['status'][pname]
            #print "Setting",pname,"to",progresstxt
            tlabel.SetLabel(file)
            plabel.SetLabel(progresstxt)
        statdlpanel = self.data['status']['panel']
        statdlpanel.Refresh()



    def refreshTorrentTotalStats_network_callback(self,*args,**kwargs):
        """ Called by network thread """
        self.invokeLater(self.refreshTorrentTotalStats,args,kwargs)
        
    def refreshTorrentTotalStats(self,totaldlspeed='',totalulspeed=''):
        """ Called by GUI thread """
        active = self.utility.torrents["active"]
        
        leftlabel = self.data['status']['st28c']
        rightlabel = self.data['status']['st30c']
        
        lefttext = self.utility.lang.get('downloading')+' ('+str(len(active))+')'
        righttxt = 'down: '+totaldlspeed + ' | up: ' + totalulspeed
        leftlabel.SetLabel(lefttext)
        rightlabel.SetLabel(righttxt)

    """
    def subscrNeedsGUIUpdate(self,todayl,yesterdayl):
        update = True
        if len(todayl) > 0:
            if self.subscrDataCopy_today_top is not None and self.subscrDataCopy_today_top == todayl[0]:
               update = False
            self.subscrDataCopy_today_top = todayl[0]
            
        if len(yesterdayl) > 0:
            if self.subscrDataCopy_yday_top is not None and self.subscrDataCopy_yday_top == yesterdayl[0]:
               update = False
            self.subscrDataCopy_yday_top = yesterdayl[0]
        return update
    """
            
def revtcmp(a,b):
    if a[0] < b[0]:
        return 1
    elif a[0] == b[0]:
        return 0
    else:
        return -1

def reverse_torrent_insertime_cmp(a,b):
    if a['inserttime'] < b['inserttime']:
        return 1
    elif a['inserttime'] == b['inserttime']:
        return 0
    else:
        return -1
