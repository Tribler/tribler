# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker, Lucian Musat 
# see LICENSE.txt for license information

import wx, os
from wx import xrc
from traceback import print_exc
from threading import Event, Thread
import urllib
import webbrowser
from webbrowser import open_new

from time import time

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Search.SearchManager import split_into_keywords
from Tribler.Core.CacheDB.sqlitecachedb import bin2str, str2bin
from Tribler.Category.Category import Category
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.GridState import GridState
from Tribler.Main.vwxGUI.SearchGridManager import TorrentSearchGridManager, ChannelSearchGridManager
from Tribler.Main.Utility.constants import *

from Tribler.Video.VideoPlayer import VideoPlayer
from fontSizes import *

from Tribler.__init__ import LIBRARYNAME


DEBUG = False


class GUIUtility:
    __single = None
    
    def __init__(self, utility = None, params = None):
        if GUIUtility.__single:
            raise RuntimeError, "GUIUtility is singleton"
        GUIUtility.__single = self 
        # do other init
        self.xrcResource = None
        self.scrollWindow = None # set from tribler.py
        self.utility = utility
        self.vwxGUI_path = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI')
        self.utility.guiUtility = self
        self.params = params
        self.frame = None
        self.standardOverview = None
        self.standardDetails = None

       # videoplayer
        self.videoplayer = VideoPlayer.getInstance()

        # current GUI page
        self.guiPage = None

        # standardGrid
        self.standardGrid = None

        # port number
        self.port_number = None


        # search mode
        self.search_mode = 'files' # 'files' or 'channels'

        # first channel search
        self.firstchannelsearch = True

        # number subsciptions
        self.nb_subscriptions = None


        # firewall
        self.firewall_restart = False # ie Tribler needs to restart for the port number to be updated



        # Arno: 2008-04-16: I want to keep this for searching, as an extension
        # of the standardGrid.GridManager
        self.torrentsearch_manager = TorrentSearchGridManager.getInstance(self)
        self.channelsearch_manager = ChannelSearchGridManager.getInstance(self)
        
        self.guiOpen = Event()
     
      
        self.selectedColour = wx.Colour(216,233,240) ## 155,200,187
        self.unselectedColour = wx.Colour(255,255,255) ## 102,102,102      
        self.unselectedColour2 = wx.Colour(255,255,255) ## 230,230,230       
        self.selectedColourPending = wx.Colour(216,233,240)  ## 208,251,244
        self.bgColour = wx.Colour(102,102,102)
        
        # Recall improves by 20-25% by increasing the number of peers to query to 20 from 10 !
        self.max_remote_queries = 20    # max number of remote peers to query
        self.remote_search_threshold = 20    # start remote search when results is less than this number

    
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)

    def buttonClicked(self, event):
        "One of the buttons in the GUI has been clicked"
        self.frame.SetFocus()

        event.Skip(True) #should let other handlers use this event!!!!!!!
            
        name = ""
        obj = event.GetEventObject()
        
        print 'tb > name of object that is clicked = %s' % obj.GetName()

        try:
            name = obj.GetName()
        except:
            print >>sys.stderr,'GUIUtil: Error: Could not get name of buttonObject: %s' % obj
        
        if DEBUG:
            print >>sys.stderr,'GUIUtil: Button clicked %s' % name
            #print_stack()
        
        elif name in ['save','save_big', 'save_medium']: 
            self.standardDetails.download()
        elif name == 'browse':
            self.standardOverview.currentPanel.sendClick(event)
        elif name == 'edit':
            self.standardOverview.currentPanel.sendClick(event)
        elif name == 'firewallStatus':
            self.firewallStatusClick()
        elif name == 'remove':
           self.onDeleteTorrentFromDisk() # default behaviour for preview 1

        elif DEBUG:
            print >> sys.stderr, 'GUIUtil: A button was clicked, but no action is defined for: %s' % name
                
 
    def setSearchMode(self, search_mode):
        if search_mode not in ('files', 'channels'):
            return
        self.search_mode = search_mode

    def set_port_number(self, port_number):
        self.port_number = port_number

    def get_port_number(self):
        return self.port_number



    def toggleFamilyFilter(self, state = None):
        catobj = Category.getInstance()
        ff_enabled = not catobj.family_filter_enabled()
        print 'Setting family filter to: %s' % ff_enabled
        if state is not None:
            ff_enabled = state    
        catobj.set_family_filter(ff_enabled)
      
        if sys.platform == 'win32':
            self.frame.top_bg.familyfilter.setToggled(ff_enabled)
        else:
            if ff_enabled:
                self.frame.top_bg.familyfilter.SetLabel('Family Filter:ON')
            else:
                self.frame.top_bg.familyfilter.SetLabel('Family Filter:OFF')
        for filtername in ['filesFilter', 'libraryFilter']:
            filterCombo = xrc.XRCCTRL(self.frame, filtername)
            if filterCombo:
                filterCombo.refresh()
        
 


    def standardStartpage(self, filters = ['','']):
        self.standardOverview.setMode('startpageMode')

            
    def standardFilesOverview(self):
        self.guiPage = 'search_results'
        if self.frame.top_bg.ag.IsPlaying():
            self.frame.top_bg.ag.Show() 

        if sys.platform != 'darwin':
            self.frame.videoframe.show_videoframe()
        self.frame.videoparentpanel.Show()            

        if self.frame.videoframe.videopanel.vlcwin.is_animation_running():
            self.frame.videoframe.videopanel.vlcwin.show_loading()
            
        #self.frame.channelsDetails.reinitialize()
        self.frame.channelsDetails.Hide()



        self.frame.top_bg.results.SetForegroundColour((0,105,156))
        self.frame.top_bg.channels.SetForegroundColour((255,51,0))
        self.frame.top_bg.settings.SetForegroundColour((255,51,0))
        self.frame.top_bg.my_files.SetForegroundColour((255,51,0))

        self.frame.top_bg.results.SetFont(wx.Font(FONT_SIZE_PAGE_OVER, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.channels.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.settings.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.my_files.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))

        self.frame.top_bg.search_results.Show()

        if sys.platform == 'win32':
            self.frame.top_bg.Refresh()

        self.showPager(True)
        if sys.platform == "linux2":
            self.frame.pagerPanel.SetMinSize((634,20))
        elif sys.platform == 'darwin':
            self.frame.pagerPanel.SetMinSize((634,20))
        else:
            self.frame.pagerPanel.SetMinSize((635,20))


        self.standardOverview.setMode('filesMode')

        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass

        ##self.frame.pageTitlePanel.Show()

        
    def channelsOverview(self, erase=False):
        if self.guiPage != 'search_results':
            if sys.platform == 'darwin':
                self.frame.top_bg.ag.Stop()
            self.frame.top_bg.ag.Hide()
        elif self.frame.top_bg.ag.IsPlaying():
            self.frame.top_bg.ag.Show() 
            
        if erase:
            self.frame.channelsDetails.reinitialize(force=True)
#            self.frame.top_bg.indexMyChannel = -1

        self.frame.channelsDetails.Show()
             
        if self.guiPage == 'search_results':
            self.frame.top_bg.channels.SetForegroundColour((255,51,0))
            self.frame.top_bg.results.SetForegroundColour((0,105,156))
            self.frame.top_bg.channels.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.results.SetFont(wx.Font(FONT_SIZE_PAGE_OVER, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.search_results.Show()
        elif self.guiPage == 'channels':
            self.frame.top_bg.channels.SetForegroundColour((0,105,156))
            self.frame.top_bg.results.SetForegroundColour((255,51,0))
            self.frame.top_bg.channels.SetFont(wx.Font(FONT_SIZE_PAGE_OVER, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.results.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.search_results.Hide()

        self.frame.top_bg.settings.SetForegroundColour((255,51,0))
        self.frame.top_bg.my_files.SetForegroundColour((255,51,0))

        self.frame.top_bg.settings.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.my_files.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))

#        self.frame.top_bg.Refresh()



        if sys.platform != 'darwin':
            self.frame.videoframe.show_videoframe()
        self.frame.videoparentpanel.Show()

        self.showPager(False)



        self.frame.Layout()

        t1 = time()

        self.standardOverview.setMode('channelsMode')


        t2 = time()
        print >> sys.stderr , "channelsMode" , t2 -t1

        self.standardOverview.data['channelsMode']['grid'].reloadChannels()
        self.standardOverview.data['channelsMode']['grid2'].reloadChannels()


        ##wx.CallAfter(self.frame.channelsDetails.reinitialize)


    def loadInformation(self, mode, sort, erase = False):
        """ Loads the information in a specific mode """
        if erase:
            self.standardOverview.getGrid().clearAllData()
        gridState = GridState(mode, 'all', sort)
        self.standardOverview.filterChanged(gridState)



    def settingsOverview(self):
        self.guiPage = 'settings' 
        if sys.platform == 'darwin':
            self.frame.top_bg.ag.Stop() # only calling Hide() on mac isnt sufficient 
        self.frame.top_bg.ag.Hide()
        if sys.platform == 'win32':
            self.frame.top_bg.Layout()

        self.frame.channelsDetails.Hide()
                
        self.frame.top_bg.results.SetForegroundColour((255,51,0))
        self.frame.top_bg.channels.SetForegroundColour((255,51,0))
        self.frame.top_bg.settings.SetForegroundColour((0,105,156))
        self.frame.top_bg.my_files.SetForegroundColour((255,51,0))

        self.frame.top_bg.results.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.channels.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.settings.SetFont(wx.Font(FONT_SIZE_PAGE_OVER, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
        self.frame.top_bg.my_files.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))


        self.frame.videoframe.hide_videoframe()
        self.frame.videoparentpanel.Hide()            

        if sys.platform == 'darwin':
            self.frame.videoframe.videopanel.vlcwin.stop_animation()

        self.showPager(False)

        if self.frame.top_bg.search_results.GetLabel() != '':
            self.frame.top_bg.search_results.Hide()
        self.frame.Layout()
        self.standardOverview.setMode('settingsMode')


    def showPager(self, b):
        self.frame.pagerPanel.Show(b)
        self.frame.BL.Show(b)
        self.frame.BR.Show(b)
        

    def standardLibraryOverview(self, filters = None, refresh=False):
        
        setmode = refresh
        if self.guiPage != 'my_files':
            self.guiPage = 'my_files' 
            if sys.platform == 'darwin':
                self.frame.top_bg.ag.Stop()
            self.frame.top_bg.ag.Hide()
            self.frame.top_bg.results.SetForegroundColour((255,51,0))
            self.frame.top_bg.channels.SetForegroundColour((255,51,0))
            self.frame.top_bg.settings.SetForegroundColour((255,51,0))
            self.frame.top_bg.my_files.SetForegroundColour((0,105,156))
            self.frame.top_bg.results.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.channels.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.settings.SetFont(wx.Font(FONT_SIZE_PAGE, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))
            self.frame.top_bg.my_files.SetFont(wx.Font(FONT_SIZE_PAGE_OVER, wx.SWISS, wx.NORMAL, wx.NORMAL, 0, "UTF-8"))

            self.frame.channelsDetails.Hide()

            if sys.platform != 'darwin':
                self.frame.videoframe.show_videoframe()
            self.frame.videoparentpanel.Show()


            if self.frame.top_bg.search_results.GetLabel() != '':
                self.frame.top_bg.search_results.Hide()
            self.frame.top_bg.Layout()
            
            if sys.platform == "linux2":
                self.frame.pagerPanel.SetMinSize((634,20))
            elif sys.platform == 'darwin':
                self.frame.pagerPanel.SetMinSize((634,20))
            else:
                self.frame.pagerPanel.SetMinSize((635,20))

            self.showPager(True)
           
            setmode = True
            
        if setmode:
            self.standardOverview.setMode('libraryMode',refreshGrid=refresh)
            self.loadInformation('libraryMode', "name", erase=False)

            if sys.platform != 'darwin':
                wx.CallAfter(self.frame.videoframe.show_videoframe)
            
        self.standardDetails.setMode('libraryMode')

        try:
            wx.CallAfter(self.frame.standardPager.Show,self.standardOverview.getGrid().getGridManager().get_total_items()>0)
        except:
            pass
           
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
        self.standardStartpage()
        self.standardOverview.Show(True)

        # Family filter initialized from configuration file
        catobj = Category.getInstance()
        print >> sys.stderr , "FAMILY FILTER :" , self.utility.config.Read('family_filter', "boolean")

        
    def initStandardDetails(self, standardDetails):
        "Called by standardDetails when ready with init"
        self.standardDetails = standardDetails
        firstItem = self.standardOverview.getFirstItem()
        self.standardDetails.setMode('filesMode', firstItem)        
        self.guiOpen.set()

    
    def selectData(self, data):
        "User clicked on item. Has to be selected in detailPanel"
        self.standardDetails.setData(data)
        self.standardOverview.updateSelection()
        
    def selectTorrent(self, torrent):
        "User clicked on torrent. Has to be selected in detailPanel"
        self.standardDetails.setData(torrent)
        self.standardOverview.updateSelection()

            
    def updateSizeOfStandardOverview(self):
        print 'tb > SetProportion'
        self.standardOverview.SetProportion(1)
        
        
        if self.standardOverview.gridIsAutoResizing():
            #print 'size1: %d, size2: %d' % (self.frame.GetClientSize()[1], self.frame.window.GetClientSize()[1])
            margin = 10
            newSize = (-1, #self.scrollWindow.GetClientSize()[1] - 
                           self.frame.GetClientSize()[1] - 
                               100 - # height of top bar
                               self.standardOverview.getPager().GetSize()[1] -
                               margin)
        else:
            newSize = self.standardOverview.GetSize()
                    
        #print 'ClientSize: %s, virtual : %s' % (str(self.scrollWindow.GetClientSize()), str(self.scrollWindow.GetVirtualSize()))
        #print 'Position: %s' % str(self.standardOverview.GetPosition())
        self.standardOverview.SetSize(newSize)
        self.standardOverview.SetMinSize(newSize)
        self.standardOverview.SetMaxSize(newSize)            
        #print 'Overview is now: %s' % str(self.standardOverview.GetSize())
        self.standardOverview.GetContainingSizer().Layout()
            
            

    def dosearch(self):
        sf = self.frame.top_bg.searchField
        if sf is None:
            return
        input = sf.GetValue().strip()
        if input == '':
            return

        if self.search_mode == 'files':
            ##wx.CallAfter(self.frame.pageTitlePanel.pageTitle.SetLabel, 'File search')
            self.searchFiles('filesMode', input)
        else:
            ##wx.CallAfter(self.frame.pageTitlePanel.pageTitle.SetLabel, 'Channel search')
            self.searchChannels('channelsMode', input)

      


    def searchFiles(self, mode, input):
        wantkeywords = split_into_keywords(input)
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchFiles:", wantkeywords

        #wantkeywords = [i for i in low.split(' ') if i]
        self.torrentsearch_manager.setSearchKeywords(wantkeywords, mode)
        self.torrentsearch_manager.set_gridmgr(self.standardOverview.getGrid().getGridManager())
        #print "******** gui uti searchFiles", wantkeywords

        self.frame.channelsDetails.Hide()
        self.frame.channelsDetails.mychannel = False
        ##self.frame.pageTitlePanel.Show()

        self.standardOverview.setMode('filesMode')

        ##self.frame.pageTitlePanel.pageTitle.SetMinSize((665,20))
        self.frame.standardOverview.SetMinSize((300,490)) # 476

        self.showPager(True)
        if sys.platform == "linux2":
            self.frame.pagerPanel.SetMinSize((626,20))
        elif sys.platform == 'darwin':
            self.frame.pagerPanel.SetMinSize((674,21))
        else:
            self.frame.pagerPanel.SetMinSize((626,20))



        self.standardOverview.getGrid().clearAllData()
        gridstate = GridState('filesMode', 'all', 'rameezmetric')
        self.standardOverview.filterChanged(gridstate)
        #self.standardOverview.getGrid().Refresh()        

        #
        # Query the peers we are connected to
        #
        # Arno, 2010-02-03: Query starts as Unicode
        q = u'SIMPLE '
        for kw in wantkeywords:
            q += kw+u' '
        q = q.strip()
            
        print >>sys.stderr,"GUIUtil: query",`q`
            
        self.utility.session.query_connected_peers(q,self.sesscb_got_remote_hits,self.max_remote_queries)
        self.standardOverview.setSearchFeedback('remote', False, 0, wantkeywords,self.frame.top_bg.search_results)
                



    def searchChannels(self, mode, input):
        wantkeywords = split_into_keywords(input)
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchChannels:", wantkeywords
        #wantkeywords = [i for i in low.split(' ') if i]
        self.channelsearch_manager.setSearchKeywords(wantkeywords, mode)

        ##### GUI specific code
        self.channelsearch_manager.set_gridmgr(self.standardOverview.getGrid().getGridManager())

        if self.standardOverview.getMode != 'channelsMode':
            self.standardOverview.setMode('channelsMode')


#        self.frame.top_bg.indexMyChannel=-1

        self.frame.channelsDetails.Show()
        self.frame.channelsDetails.mychannel = False
        if not self.frame.channelsDetails.isEmpty():
            self.frame.channelsDetails.reinitialize()
        self.showPager(False)

        self.loadInformation('channelsMode', 'name', erase=True)


        
        if mode == 'channelsMode':
            q = 'CHANNEL k '
            for kw in wantkeywords:
                q += kw+' '
            
            self.utility.session.query_connected_peers(q,self.sesscb_got_channel_hits)
            ##### GUI specific code




    def complete(self, term):
        """autocompletes term."""
        completion = self.utility.session.open_dbhandler(NTFY_TERM).getTermsStartingWith(term, num=1)
        if completion:
            return completion[0][len(term):]
        # boudewijn: may only return unicode compatible strings. While
        # "" is unicode compatible it is better to return u"" to
        # indicate that it must be unicode compatible.
        return u""

    def sesscb_got_remote_hits(self,permid,query,hits):
        # Called by SessionCallback thread 

        if DEBUG:
            print >>sys.stderr,"GUIUtil: sesscb_got_remote_hits",len(hits)

        # 22/01/10 boudewijn: use the split_into_keywords function to
        # split.  This will ensure that kws is unicode and splits on
        # all 'splittable' characters
        kwstr = query[len('SIMPLE '):]
        kws = split_into_keywords(kwstr)

        wx.CallAfter(self.torrentsearch_manager.gotRemoteHits,permid,kws,hits,self.standardOverview.getMode())
        
    def sesscb_got_channel_hits(self,permid,query,hits):
        # Called by SessionCallback thread 
        if DEBUG:
            print >>sys.stderr,"GUIUtil: sesscb_got_channel_hits",len(hits)

        # 22/01/10 boudewijn: use the split_into_keywords function to
        # split.  This will ensure that kws is unicode and splits on
        # all 'splittable' characters
        kwstr = query[len("CHANNEL x "):]
        kws = split_into_keywords(kwstr)

        records = []
        for k,v in hits.items():
            records.append((bin2str(v['publisher_id']),v['publisher_name'],bin2str(v['infohash']),bin2str(v['torrenthash']),v['torrentname'],v['time_stamp'],bin2str(k)))


        if DEBUG:
            print >> sys.stderr , "CHANNEL HITS" , records



        #Code that calls GUI
        # 1. Grid needs to be updated with incoming hits, from each remote peer
        # 2. Sorting should also be done by that function
        wx.CallAfter(self.channelsearch_manager.gotRemoteHits,permid,kws,records,self.standardOverview.getMode())
        

    def set_firewall_restart(self,b):
        self.firewall_restart = b

    def firewallStatusClick(self,event=None):
        title = self.utility.lang.get('tribler_information')
        if self.firewall_restart:
            type = wx.ICON_WARNING
            msg = self.utility.lang.get('restart_tooltip')
        elif self.isReachable():
            type = wx.ICON_INFORMATION
            msg = self.utility.lang.get('reachable_tooltip')
        else:
            type = wx.ICON_INFORMATION
            msg = self.utility.lang.get('connecting_tooltip')
            
        dlg = wx.MessageDialog(None, msg, title, wx.OK|type)
        result = dlg.ShowModal()
        dlg.Destroy()

    def getSearchField(self,mode=None):
        return self.standardOverview.getSearchField(mode=mode)
   
    def isReachable(self):
        return self.utility.session.get_externally_reachable()
   
          
    def onDeleteTorrentFromDisk(self, event = None):
        item = self.standardDetails.getData()
        
        if item.get('ds'):
            self.utility.session.remove_download(item['ds'].get_download(),removecontent = True)
            
        self.standardOverview.removeTorrentFromLibrary(item)
                
    def onDeleteTorrentFromLibrary(self, event = None):
        item = self.standardDetails.getData()
        
        if item.get('ds'):
            self.utility.session.remove_download(item['ds'].get_download(),removecontent = False)
            
        self.standardOverview.removeTorrentFromLibrary(item)
    
