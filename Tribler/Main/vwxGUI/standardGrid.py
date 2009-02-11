# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat
# see LICENSE.txt for license information

import os, sys, wx, math
from traceback import print_exc,print_stack
import wx.xrc as xrc
from time import time

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.filesItemPanel import FilesItemPanel
from Tribler.Main.vwxGUI.LibraryItemPanel import LibraryItemPanel
from Tribler.Main.vwxGUI.PersonsItemPanel import PersonsItemPanel
from Tribler.Main.vwxGUI.FriendsItemPanel import FriendsItemPanel
from Tribler.Main.vwxGUI.ColumnHeader import ColumnHeaderBar
from Tribler.Main.vwxGUI.SubscriptionsItemPanel import SubscriptionsItemPanel
from Tribler.Main.vwxGUI.SearchGridManager import SEARCHMODE_NONE, SEARCHMODE_SEARCHING, SEARCHMODE_STOPPED
from Tribler.Main.vwxGUI.GridState import GridState
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Category.Category import Category

DEBUG = True

ntfy_mappings = {'filesMode':[NTFY_MYPREFERENCES, NTFY_TORRENTS],
                 'personsMode':[NTFY_PEERS],
                 'friendsMode':[NTFY_PEERS],
                 'libraryMode':[NTFY_MYPREFERENCES, NTFY_TORRENTS],
                 
                 }


class GridManager(object):
    """ Grid manager handles:
         - handling of notifies in grid
         - retrieval of data from db on paging events
         - retrieval of data from db on state changes from GUI
        
    """
    def __init__(self, grid, utility):
        self.session = utility.session
        
        self.peer_db = self.session.open_dbhandler(NTFY_PEERS)
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.friend_db = self.session.open_dbhandler(NTFY_FRIENDS)

        self.state = None
        self.total_items = 0
        self.page = 0
        self.grid = grid
        self.data = []
        self.callbacks_disabled = False
        self.download_states_callback_set = False
        self.dslist = []
        
        self.torrentsearch_manager = utility.guiUtility.torrentsearch_manager
        self.torrentsearch_manager.register(self.torrent_db)

        self.peersearch_manager = utility.guiUtility.peersearch_manager
        self.peersearch_manager.register(self.peer_db,self.friend_db)
        self.guiserver = GUITaskQueue.getInstance()
        
        # Jie's hacks to avoid DB concurrency, REMOVE ASAP!!!!!!!!!!!!
        # ARNOCOMMENT
        self.refresh_rate = 1.5   # how often to refresh the GUI in seconds
        
        self.cache_numbers = {}
        self.cache_ntorrent_interval = 1
        self.cache_npeer_interval = 1
        
    def set_state(self, state, reset_page = False):
        self.state = state
        if reset_page or self.inSearchMode(state):
            self.page = 0
        self.refresh(update_observer = True)
        
    def refresh(self, update_observer = False):
        """
        Refresh the data of the grid
        """
        
        #print >>sys.stderr,"standardGrid: refresh",update_observer,"ready",self.grid.initReady,"state",self.state
        
        
        #print >> sys.stderr, '**********==============********* refresh', self.grid.initReady
        if not self.grid.initReady:
            standardgrid_refresh_lambda = lambda:self.refresh(update_observer=update_observer)
            wx.CallAfter(standardgrid_refresh_lambda)
            return

        if self.state is None:
            return
        
        if update_observer:
            self.setObserver()
            
        self.data, self.total_items = self._getData(self.state)
        #print >> sys.stderr, 'GridManager: Data length: %d/%d' % (len(self.data), self.total_items)
        self.grid.setData(self.data)
        if DEBUG:
            print >> sys.stderr, 'GridManager: state: %s gave %d results' % (self.state, len(self.data))
        
    def set_page(self, page):
        if page != self.page:
            self.page = page
            self.refresh()

    def get_total_items(self):
        return self.total_items
    
    def get_number_torrents(self, state):
        # cache the numbers to avoid loading db, which is a heavy operation
        category_name = state.category
        library = (state.db == 'libraryMode')
        key = (category_name, library)

        now = time()
        
        if (key not in self.cache_numbers or
            now - self.cache_numbers[key][1] > self.cache_ntorrent_interval):
       
            ntorrents = self.torrent_db.getNumberTorrents(category_name = category_name, library = library)
            self.cache_numbers[key] = [ntorrents, now]
            #if ntorrents > 1000:
            #    self.cache_ntorrent_interval = 120
            #elif ntorrents > 100 and self.cache_ntorrent_interval < 30:
            #    self.cache_ntorrent_interval = 30
            #print >> sys.stderr, '***** update get_number_torrents', ntorrents, self.cache_ntorrent_interval, time()-now
        
        return self.cache_numbers[key][0]
    
    def get_number_peers(self, state):
        # cache the numbers to avoid loading db, which is a heavy operation
        category_name = state.category
        library = 'peer'
        key = (category_name, library)
        
        if (key not in self.cache_numbers or
            time() - self.cache_numbers[key][1] > self.cache_npeer_interval):
            
            # print >> sys.stderr, '*********** get_number_peers', key, self.cache_numbers[key], now - self.last_npeer_cache, self.cache_npeer_interval, self.grid.items
            npeers = self.peer_db.getNumberPeers(category_name = category_name)
            self.cache_numbers[key] = [npeers, time()]
            #print >> sys.stderr, '***** update get_number_peers', npeers, self.cache_npeer_interval, time()-now
        
        return self.cache_numbers[key][0]
    
    def _getData(self, state):
        #import threading
        #print >> sys.stderr, 'threading>>','****'*10, threading.currentThread().getName()
        
        #print >>sys.stderr,"standardGrid: _getData: state is",state
        
        range = (self.page * self.grid.items, (self.page+1)*self.grid.items)
        if state.db in ('filesMode', 'libraryMode'):
            
            # Arno: state.db should be NTFY_ according to GridState...
            if self.torrentsearch_manager.getSearchMode(state.db) == SEARCHMODE_NONE:
            
                total_items = self.get_number_torrents(state)   # read from cache
                data = self.torrent_db.getTorrents(category_name = state.category, 
                                                       sort = state.sort,
                                                       range = range,
                                                       library = (state.db == 'libraryMode'),
                                                       reverse = state.reverse)
            else:
                [total_items,data] = self.torrentsearch_manager.getHitsInCategory(state.db,state.category,range,state.sort,state.reverse)
                
            #if state.db == 'libraryMode':
            data = self.addDownloadStates(data)
        elif state.db in ('personsMode', 'friendsMode'):
            if state.db == 'friendsMode':
                state.category = 'friend'
                
            if self.peersearch_manager.getSearchMode(state.db) == SEARCHMODE_NONE:
                #print >>sys.stderr,"GET GUI PEERS #################################################################################"
                total_items = self.get_number_peers(state)
                data = self.peer_db.getGUIPeers(category_name = state.category, 
                                                        sort = state.sort,
                                                        reverse = state.reverse,
                                                        range = range,
                                                        get_online = True)
            else:
                #print >>sys.stderr,"SEARCH GUI PEERS $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
                try:
                    [total_items,data] = self.peersearch_manager.getHits(state.db,range)
                except:
                    print_exc()

            if state.db == 'friendsMode':
                data = self.addCoopDLStatus(data)

        else:
            raise Exception('Unknown data db in GridManager: %s' % state.db)

        return data, total_items
    
    def _last_page(self):
        return self.total_items == 0 or (0 < len(self.data) < self.grid.items)
    
    def setObserver(self):
        self.session.remove_observer(self.item_network_callback)
        for notify_constant in ntfy_mappings[self.state.db]:
            #print >> sys.stderr, 'gridmgr: For %s we added %s' % (self.state.db, notify_constant)
            self.session.add_observer(self.item_network_callback, notify_constant,
                                      [NTFY_UPDATE, NTFY_INSERT, NTFY_DELETE, NTFY_CONNECTION])
        
        if self.state.db == 'libraryMode':
            if not self.download_states_callback_set:
                self.download_states_callback_set = True
        
    def reactivate(self):
        # After a grid has been hidden by the standardOverview, network/db callbacks
        # are not handled anymore. This function is called if a resize event is caught
        # if callbacks were disabled, they are enabled again
            
        if self.callbacks_disabled:
            #print >> sys.stderr, ('*' * 50 + '\n')*3
            #print >> sys.stderr, 'Reactivating grid', self.grid.__class__.__name__
            self.callbacks_disabled = False
            self.refresh(update_observer = True)
        else:
            # also refresh normally on resize (otherwise new rows cannot be added
            self.refresh()
            
#    def download_state_network_callback(self, *args):
#        """ Called by SessionThread from ABCApp """
#        if self.download_states_callback_set:
#            if self.grid.isShowByOverview():
#                wx.CallAfter(self.download_state_gui_callback, *args)
#            else:
#                self.callbacks_disabled = True
#                self.download_states_callback_set = False
        
    def item_network_callback(self, *args):
        #print >>sys.stderr,"standardGrid: item_network_callback",`args`
        # print >> sys.stderr, '***** searchmode: ', self.torrentsearch_manager.getSearchMode(self.state.db)
        
        # only handle network callbacks when grid is shown
        if not self.grid.isShowByOverview():
            self.callbacks_disabled = True
            self.session.remove_observer(self.item_network_callback) #unsubscribe this function
        else:
            # 15/07/08 Boudewijn: only change grid when still searching
            #if self.torrentsearch_manager.inSearchMode(self.state.db):    # 25/07/08 Jie: it causes GUI never updated when not in search mode
                self.itemChanged(*args)
             
        
    def itemChanged(self,subject,changeType,objectID,*args):
        "called by GuiThread"
        if changeType == NTFY_INSERT:
            self.itemAdded(subject, objectID, args)
        elif changeType in (NTFY_UPDATE, NTFY_CONNECTION):
            self.itemUpdated(subject, objectID, args)
        elif changeType == NTFY_DELETE:
            self.itemDeleted(subject, objectID, args)
        else:
            raise Exception('Unknown notify.changeType')
    
    def itemAdded(self,subject, objectID, args):
        #if self._last_page(): # This doesn't work as the pager is not updated if page becomes full
        #print >> sys.stderr, '******* standard Grid: itemAdded:', objectID, args, 'search?', self.torrentsearch_manager.inSearchMode(self.state.db) 
        if self.torrentsearch_manager.getSearchMode(self.state.db) == SEARCHMODE_SEARCHING:
            #print >> sys.stderr, 'Grid refresh because search item added!!!============================='
            wx.CallAfter(self.refresh)
        elif self.isRelevantItem(subject, objectID):
            task_id = str(subject) + str(int(time()/self.refresh_rate))
            self.guiserver.add_task(lambda:wx.CallAfter(self.refresh), self.refresh_rate, id=task_id)
            # that's important to add the task 3 seconds later, to ensure the task will be executed at proper time  
            #self.refresh()
    
    def itemUpdated(self,subject, objectID, args):
        # Both in torrent grid and peergrid, changed items can make new items appear on the screen
        # Peers: when first buddycast
        # Friends: if just became new friend
        # Torrent: when status changes to 'good'
        # So we have to alway refresh here
        
        #if (self._objectOnPage(subject, objectID)
        if self.torrentsearch_manager.getSearchMode(self.state.db) == SEARCHMODE_NONE:
            task_id = str(subject) + str(int(time()/self.refresh_rate))
            
            #print >>sys.stderr,"standardGrid: itemUpdated",subject,`objectID`,`args`
            
            self.guiserver.add_task(lambda:wx.CallAfter(self.refresh), self.refresh_rate, id=task_id)
            #self.refresh()
    
    def itemDeleted(self,subject, objectID, args):
        if self._objectOnPage(subject, objectID):
            task_id = str(subject) + str(int(time()/self.refresh_rate))
            self.guiserver.add_task(lambda:wx.CallAfter(self.refresh), self.refresh_rate, id=task_id)
            #self.refresh()
    
    def download_state_gui_callback(self, dslist):
        """
        Called by GUIThread
        """
        self.dslist = dslist
        if self.state.db == 'libraryMode':
            for infohash in [ds.get_download().get_def().get_infohash() for ds in dslist]:
                if self._objectOnPage(NTFY_TORRENTS, infohash):
                    self.refresh()
                    break
        else:
            # friendsMode
            self.refresh()
        
    def _objectOnPage(self, subject, objectID):
        if subject == NTFY_PEERS:
            id_name = 'permid'
        elif subject in (NTFY_TORRENTS, NTFY_MYPREFERENCES, NTFY_SUPERPEERS):
            id_name = 'infohash'
        elif subject in (NTFY_YOUTUBE):
            raise Exception('Not yet implemented')
        
        return objectID in [a[id_name] for a in self.data]
       
    def isRelevantItem(self, subject, objectID):
        return True #Jie: let DB decide if the notifier should be sent
    
        db_handler = self.session.open_dbhandler(subject)
        if subject == NTFY_PEERS:
            peer = db_handler.getPeer(objectID)
            ok = peer and (peer['last_connected']>0 or peer['friend'])
            #if not ok:
            #    print >> sys.stderr, 'Gridmanager: Peer is not relevant: %s' % peer
            return ok
        elif subject in (NTFY_TORRENTS):
            id_name = 'infohash'
            torrent = db_handler.getTorrent(objectID)
            ok = torrent is not None and torrent['status'] == 'good' and Category.getInstance().hasActiveCategory(torrent)
            #if not ok:
            #    print >> sys.stderr, 'Gridmanager: Torrent is not relevant: %s' % torrent
            return ok
        elif subject == NTFY_MYPREFERENCES:
            return True
        
        raise Exception('not yet implemented')
    
    def addDownloadStates(self, liblist):
        # Add downloadstate data to list of torrent dicts
        for ds in self.dslist:
            infohash = ds.get_download().get_def().get_infohash()
            for torrent in liblist:
                if torrent['infohash'] == infohash:
                    print >>sys.stderr,"standardGrid: addDownloadStates: adding ds for",`ds.get_download().get_def().get_name()`
                    torrent['ds'] = ds
                    break
        return liblist

   
    def addCoopDLStatus(self, liblist):
        # Add downloadstate data to list of friend dicts
        for ds in self.dslist:
            helpers = ds.get_coopdl_helpers()
            coordinator = ds.get_coopdl_coordinator()
            
            for friend in liblist:
                if friend['permid'] in helpers:
                    # Friend is helping us
                    friend['coopdlstatus'] = u'Helping you with '+ds.get_download().get_def().get_name_as_unicode()
                elif friend['permid'] == coordinator:
                    # Friend is getting help from us
                    friend['coopdlstatus'] = u'You help with '+ds.get_download().get_def().get_name_as_unicode()
                #else:
                #    friend['coopdlstatus'] = u'Sleeping'
                    
        return liblist

    def inSearchMode(self, state):
        if state.db in ('filesMode', 'libraryMode'):
            return self.torrentsearch_manager.getSearchMode(state.db) == SEARCHMODE_NONE
        elif state.db in ('personsMode', 'friendsMode'):
            return self.peersearch_manager.getSearchMode(state.db) == SEARCHMODE_NONE
        else:
            return False
        
        
    def get_dslist(self):
        return self.dslist
        
class standardGrid(wx.Panel):
    """
    Panel which shows a grid with static number of columns and dynamic number
    of rows
    """
    def __init__(self, cols, subPanelHeight, orientation='horizontal', viewmode = 'list'): ##
        self.initReady = False
        self.data = None
        self.detailPanel = None
        self.orientation = orientation
        self.subPanelClass = None
        self.items = 0 #number of items that are currently visible 
        self.currentRows = 0
        self.sizeMode = 'auto'
        self.columnHeader = None
        self.topMargin = 5
        self.lastSize = None
        self.panels = []
        self.viewmode = viewmode
        self.guiUtility = GUIUtility.getInstance()

        self.guiUtility.standardGrid = self
 
        self.utility = self.guiUtility.utility
        self.gridManager = GridManager(self, self.utility)
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        
        if type(cols) == int:
            self.cols = cols
            self.columnTypes = None
            self.subPanelHeight = subPanelHeight
        else:
            self.columnTypes = cols
            self.subPanelHeights = subPanelHeight
            if self.viewmode == 'thumbnails':
                self.cols = cols[0]
                self.subPanelHeight = self.subPanelHeights[0]
            elif self.viewmode == 'list':
                self.cols = cols[1]
                self.subPanelHeight = self.subPanelHeights[1]
            else:
                raise Exception('unknown viewmode: %s' % self.viewmode)
                
        self.superpeer_db = self.utility.session.open_dbhandler(NTFY_SUPERPEERS)
        self.torrentfeed = TorrentFeedThread.getInstance()
        self.guiserver = GUITaskQueue.getInstance()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    

    def _PostInit(self):
        # Do all init here

        #self.SetSize((500,500))
        self.SetBackgroundColour(wx.WHITE)
        
        #self.cols = 5
        
        self.Bind(wx.EVT_SIZE, self.onResize)
        
        self.addComponents()
        self.calculateRows()
        
        if self.viewmode == 'list':
            self.toggleColumnHeaders(True)
        self.Show()
        self.Layout()
        self.Refresh()

        self.initReady = True
        if self.data:
            self.setData(self.data)
                
    def addComponents(self):
        self.Show(False)

        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.columnHeaderSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.columnHeaderSizer.Add((0,self.topMargin))
        self.vSizer.Add(self.columnHeaderSizer, 0, wx.ALL|wx.EXPAND, 0)
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        #self.Layout();
        #self.Refresh(True)
        #self.Update()
        #print "vSizer: %s, Panel: %s"% (self.vSizer.GetSize(), self.GetSize())

    
    #def Show(self, s):
    #    print >> sys.stderr, '%s is show(%s)' % (self, s)
        #wx.Panel.Show(self, s)
        
    def onViewModeChange(self, event=None, mode = None):
        if not self.initReady:
            wx.CallAfter(self.onViewModeChange, event, mode)
            return
                         
        if not mode:
            if type(event.GetEventObject()) == wx.Choice:
                mode = event.GetEventObject().GetStringSelection()
            
        if self.viewmode != mode:
            self.viewmode = mode
            #oldcols = self.cols
            self.updatePanel(self.currentRows, 0)
            if mode == 'thumbnails':
                self.cols = self.columnTypes[0]
                self.subPanelHeight = self.subPanelHeights[0]
            elif mode == 'list':
                self.cols = self.columnTypes[1]
                self.subPanelHeight = self.subPanelHeights[1]
            self.currentRows = 0
            
            #self.updatePanel(0, self.currentRows)
            self.calculateRows()
            #self.updateCols(oldcols, self.cols)
            self.gridManager.refresh()
            self.toggleColumnHeaders(mode == 'list')
        
    def onSizeChange(self, event=None):
        if type(event.GetEventObject()) == wx.Choice:
            value = event.GetEventObject().GetStringSelection()
        else:
            value = event.GetEventObject().GetValue()
            
        self.sizeMode = value
        if value == 'auto':
            self.guiUtility.updateSizeOfStandardOverview()
            self.SetMinSize((-1, 20))
        else:
            try:
                wantedRows = int(value) / self.cols
                self.SetSize((-1, wantedRows * self.subPanelHeight))
                self.SetMinSize((-1, wantedRows * self.subPanelHeight))
                self.guiUtility.standardOverview.growWithGrid()
                self.guiUtility.standardOverview.Refresh()
            except:
                #print 'Exception!'
                
                raise
                
        
    def refreshData(self):
        self.setData(self.data)
        

    def getData(self):
        return self.data


    def setData(self, dataList):
        
        #if dataList is None:
            #datalength = 0
        #else:
            #datalength = len(dataList)
        
        if type(dataList) == list or dataList is None:
            if DEBUG:
                print >>sys.stderr,'grid.setData: list'
            self.data = dataList
     
        if not self.initReady:
            return
                
        self.refreshPanels()
        if DEBUG:
            print >>sys.stderr,'standardGrid: <mluc>start columns:',\
                self.cols,'rows:',self.currentRows,'items:',self.items

        self.Layout()
        
    def updateItem(self, item, delete = False, onlyupdate = False):
        "Add or update an item in the grid"
        
        if not item:
            return
        
        # Get key to compare this item to others
        key = None
        for tempkey in ['infohash', 'permid', 'content_name']:
            if item.has_key(tempkey):
                key = tempkey
                break
        if not key:
            if DEBUG:
                print >>sys.stderr,'standardGrid: Error, could not find key to compare item: %s' % item
            return
        #get the current data source
        if len(self.data)>0 and self.data[0].has_key("permid"):
            print >>sys.stderr,"\n*****************************************************\n\
*                   big problem                     *\n\
*     in torrentGrid, working on peer data!!!!!     *\n\
*                                                   *\n\
*****************************************************\n"
        i = find_content_in_dictlist(self.data, item, key)
        if i != -1:
            if not delete:
                self.data[i] = item
            else:
                self.data.remove(item)
        elif not onlyupdate:
            self.data.append(item)
        self.refreshData()
        
    def refreshPanels(self):
        "Refresh TorrentPanels with correct data and refresh pagerPanel"
        if self.getStandardPager():
            self.standardPager.refresh()
        
        if self.data is None:
            self.clearAllData()
        else:
            for i in xrange(0, self.items):
                if i < len(self.data):
                    self.setDataOfPanel(i, self.data[i])
                else:
                    self.setDataOfPanel(i, None)
                    
        self.updateSelection()
    
    def gridResized(self, rows):
        self.items = self.cols * rows
        self.refreshPanels()

       
            
    def getStandardPager(self):
        try:
            if self.standardPager:
                return True
        except:
            return False
        
    def setPager(self, pager):
        if DEBUG:
            print >>sys.stderr,'standardGrid: setPager called: %s' % pager
        self.standardPager = pager
       
    def getSubPanel(self, keyfun=None):
        raise NotImplementedError('Method getSubPanel should be subclassed')

    def setDataOfPanel(self, panelNumber, data):
        #if DEBUG:
        #    print >> sys.stderr, 'Set data of panel %d with data: %s' % (panelNumber, data)
        try:
            if self.orientation == 'vertical':
                hSizer = self.vSizer.GetItem(panelNumber%self.currentRows+1).GetSizer()
                panel = hSizer.GetItem(panelNumber/ self.currentRows).GetWindow()
            else:
                hSizer = self.vSizer.GetItem(panelNumber/self.cols+1).GetSizer()
                panel = hSizer.GetItem(panelNumber % self.cols).GetWindow()
                
            panel.setData(data)
        except:
            if DEBUG:
                print >>sys.stderr,"standardGrid: Error: Could not set data in panel number %d, with %d cols" % (panelNumber, self.cols)
            print_exc()
    
    def clearAllData(self):
        for i in range(0, self.items):
            self.setDataOfPanel(i, None)
            
    def onResize(self, event=None):
        if self.GetSize() == self.lastSize:
            return
        self.lastSize = self.GetSize()
        #print >>sys.stderr, "standardGrid: resize event: %s" % self.GetSize()
        self.calculateRows(event)
        self.gridManager.reactivate()
        if event:
            event.Skip()
        
   
        
    def calculateRows(self, event=None):

        size = self.GetSize()
        oldRows = self.currentRows
        if self.columnHeader:
            columnHeaderHeight = self.columnHeader.GetSize()[1]
        else:
            columnHeaderHeight = self.topMargin
            
        if size[1] < 50 or self.subPanelHeight == 0:
            self.currentRows = 0
            self.items = 0
        else:            
            self.currentRows = (size[1] - columnHeaderHeight - 79) / self.subPanelHeight 
            if DEBUG:
                print >> sys.stderr, 'standardGrid: Height: %d, single panel is %d, so %d rows' % (size[1], self.subPanelHeight, self.currentRows)
            self.items = self.cols * self.currentRows
        
        if oldRows != self.currentRows: #changed
            if DEBUG:
                print >>sys.stderr,'standardGrid: Size updated to %d rows and %d columns, oldrows: %d'% (self.currentRows, self.cols, oldRows)
            
            self.updatePanel(oldRows, self.currentRows)
            self.gridResized(self.currentRows)
        
        
    def updateCols(self, oldCols, newCols):
        
        self.items = newCols * self.currentRows
        if newCols > oldCols:
            numNew = newCols - oldCols
            for row in xrange(len(self.panels)):
                hSizer = self.vSizer.GetItem(row).GetSizer()
                for i in xrange(numNew):
                    dataPanel = self.getSubPanel(self.keyTypedOnGridItem)
                    self.subPanelClass = dataPanel.__class__
                    self.panels[row].append(dataPanel)
                    hSizer.Add(dataPanel, 1, wx.ALIGN_CENTER|wx.ALL|wx.GROW, 0)
        elif newCols < oldCols:
            numDelete = oldCols - newCols
            for row in self.panels:
                for i in xrange(numDelete):
                    panel = row[newCols]
                    panel.Destroy()
                    del row[newCols]
                    
        
    
    def updatePanel(self, oldRows, newRows):
        if DEBUG:
            print >> sys.stderr, 'Grid: updating from %d to %d rows' % (oldRows, newRows)
        # put torrent items in grid
        
        if newRows > oldRows:
            for i in range(oldRows, newRows):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.panels.append([])
                
                for panel in range(0, self.cols):
                    dataPanel = self.getSubPanel(self.keyTypedOnGridItem)
                    self.subPanelClass = dataPanel.__class__
                    # add keylistener for arrow selection
                    #dataPanel.Bind(wx.EVT_KEY_UP, self.keyTypedOnGridItem)
                    self.panels[i].append(dataPanel)
                    #dataPanel.SetSize((-1, self.subPanelHeight))
                    hSizer.Add(dataPanel, 1, wx.ALIGN_CENTER|wx.ALL|wx.GROW, 0)
                self.vSizer.Add(hSizer, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
                
        elif newRows < oldRows:
            #print "Destroying row %d up to %d" % (newRows, oldRows-1)
            for row in range(oldRows-1, newRows-1, -1):
                # Destroy old panels
                for col in range(self.cols-1, -1, -1): #destroy panels right to left
                    panel = self.panels[row][col]
                    wx.CallAfter(panel.Destroy)
                    del self.panels[row][col]
                    
                assert self.panels[row] == [], 'We deleted all panels, still the row is %s' % self.panels[row]
                del self.panels[row]
                self.vSizer.Detach(row+1) # detach hSizer of the row
                # +1 compensated for columnheaders
                
       
        
          
    
    def updateSelection(self):
        """Deselect all torrentPanels, but the one selected in detailPanel
        If no torrent is selected in detailPanel, let first in grid be selected
        """
        
        try:
            #print 'standardGrid: update selection'
            if not self.hasDetailPanel():
                return
            
#            title = None
            
            id = self.detailPanel.getIdentifier()
            
            #print "standardGrid: updateSelection: detailsPanel has id",id,self.detailPanel
                
            number = 0
            rowIndex = 0
            for row in self.panels:
                colIndex = 0
                for pan in row:
                    try:
                        panel_id = pan.getIdentifier()
                        #print "standardGrid: updateSelection: panel has id",`panel_id`
                    except:
                        panel_id = None
                        
                    if panel_id is None or repr(panel_id) != repr(id):
                        #print 'item deselected2'
                        pan.deselect(rowIndex,colIndex)#number = number)
                    else:
                        #pan.select(rowIndex,colIndex)
                        pan.select(rowIndex, 
                                   colIndex,
                                   self.standardPager.currentPage, 
                                   self.cols, 
                                   self.currentRows)                         
                    number += 1
                    colIndex += 1
                rowIndex += 1
            self.Layout()
        except:
            # I sometimes get UnicodeErrors here somewhere
            print_exc()


    def deselectAll(self):
        """Deselect all torrentPanels"""
        
        try:
            #print 'standardGrid: update selection'
            if not self.hasDetailPanel():
                return
            
#            title = None
            
            id = self.detailPanel.getIdentifier()
            
            #print "standardGrid: updateSelection: detailsPanel has id",id,self.detailPanel
                
            number = 0
            rowIndex = 0
            for row in self.panels:
                colIndex = 0
                for pan in row:
                    try:
                        panel_id = pan.getIdentifier()
                        #print "standardGrid: updateSelection: panel has id",`panel_id`
                    except:
                        panel_id = None
                        
                    #if panel_id is None or repr(panel_id) != repr(id):
                    print >> sys.stderr , 'item deselected2'
                    pan.deselect(rowIndex,colIndex)#number = number)
                    number += 1
                    colIndex += 1
                rowIndex += 1
            self.Layout()
        except:
            # I sometimes get UnicodeErrors here somewhere
            print_exc()






    def hasDetailPanel(self):
        if self.detailPanel:
            return True
        try:
            self.detailPanel = self.guiUtility.standardDetails
        except:
            pass
        return self.detailPanel is not None

    def keyTypedOnGridItem(self, event):
        obj = event.GetEventObject()
        if DEBUG:
            print >>sys.stderr,'standardGrid: keyTyped: in %s' % obj.__class__.__name__
        while obj.__class__ != self.subPanelClass:
            obj = obj.GetParent()
        
        # Jelle: Turn of key navigation under windows. Windows already has a focus traversal policy and changes 
        # the focus of panel.
        if sys.platform == 'win32': 
            return
        
        if not obj.selected and sys.platform != 'win32':
            return

        keyCode = event.GetKeyCode()
        # Get coord of keytyped panel
        rowIndex = 0
        xpan = ypan = None
        for row in self.panels:
            colIndex = 0    
            for pan in row:
                if obj == pan:
                    (xpan, ypan) = colIndex, rowIndex
                    if DEBUG:
                        print >>sys.stderr,'standardGrid: keyTyped: found: %d, %d' % (colIndex, rowIndex)
                    break
                colIndex += 1
            rowIndex += 1
        if xpan == None:
            raise Exception('Could not find selected panel')
        xpanold = xpan
        ypanold = ypan
        if sys.platform != 'win32':
            if keyCode == wx.WXK_UP:
                ypan = max(0, ypan-1)
            elif keyCode == wx.WXK_DOWN:
                ypan = min(self.currentRows-1, ypan+1)
            elif keyCode == wx.WXK_LEFT:
                xpan = max(0, xpan -1)
            elif keyCode == wx.WXK_RIGHT:
                xpan = min(self.cols-1, xpan+1)
        else:
            if keyCode == wx.WXK_UP:
                if xpan == self.cols-1:
                    xpan = 0
                else:
                    xpan+=1
                    ypan = max(0, ypan-1)
            elif keyCode == wx.WXK_DOWN:
                if xpan == 0:
                    xpan = self.cols-1
                else:
                    xpan = xpan -1
                    ypan = min(self.currentRows-1, ypan+1)
        # Get data of new panel
        if DEBUG:
            print >>sys.stderr,'standardGrid: Old: %s, New: %s' % ((xpanold, ypanold), (xpan, ypan))
        if xpanold != xpan or ypanold != ypan or sys.platform =='win32':
            newpanel = self.panels[ypan][xpan]
            if newpanel.data != None:
                # select new panel
                #newpanel.SetFocus()
                self.guiUtility.selectData(newpanel.data)
        event.Skip()
                
    def getFirstPanel(self):
        try:
             hSizer = self.vSizer.GetItem(1).GetSizer()
             panel = hSizer.GetItem(0).GetWindow()
             return panel
        except:
            return None
        
    def toggleColumnHeaders(self, show):
        # show or hide columnheaders
        if bool(self.columnHeader) == show:
                return
        if show:
            panel = self.getFirstPanel()
            if panel:
                self.columnHeader = ColumnHeaderBar(self, panel)
                self.columnHeaderSizer.Detach(0)
                self.columnHeaderSizer.Add(self.columnHeader, 1, wx.EXPAND, 0)
                self.columnHeaderSizer.Layout()
        else:
            self.columnHeaderSizer.Detach(0)
            self.columnHeader.Destroy()
            self.columnHeader = None
            self.columnHeaderSizer.AddSpacer(5)
            self.columnHeaderSizer.Layout()
        self.vSizer.Layout()
    
            
    def isShowByOverview(self):
        name = self.__class__.__name__
        mode = self.guiUtility.standardOverview.mode
        index = name.find('Grid')
        isshown = name[:index] == mode[:index]
        return isshown
    
    def getGridManager(self):
        return self.gridManager
    
    
class filesGrid(standardGrid):
    def __init__(self):
#        columns = 5
#        self.subPanelHeight = 108 # This will be update after first refresh
        columns = (5, 1)
        subPanelHeight = (5*22, 22)
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return FilesItemPanel(self, keyfun)

    
class personsGrid(standardGrid):
    def __init__(self):
        columns = (6, 1)
        subPanelHeight = (5*22, 22)
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return PersonsItemPanel(self, keyfun)

class friendsGrid(standardGrid):
    def __init__(self):   
        columns = (1,1)
        subPanelHeight = (22,22) # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='vertical', viewmode='list')
        
    def getSubPanel(self, keyfun):
        return FriendsItemPanel(self, keyfun)
    
class libraryGrid(standardGrid):
    def __init__(self):
        columns = (1,1)
        subPanelHeight = (22, 22) # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal', viewmode='list')
            
    def getSubPanel(self, keyfun):
        return LibraryItemPanel(self, keyfun)
    
class subscriptionsGrid(standardGrid):
    def __init__(self):
        columns = 1
        subPanelHeight = 22 # This will be update after first refresh
        standardGrid.__init__(self, columns, subPanelHeight, orientation='horizontal')
        
    def getSubPanel(self, keyfun):
        return SubscriptionsItemPanel(self, keyfun)
