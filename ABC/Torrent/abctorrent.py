import sys
import wx
import os

from cStringIO import StringIO
from sha import sha
from time import strftime, localtime, time
from traceback import print_exc,print_stack

from BitTornado.bencode import bencode

from ABC.Torrent.files import TorrentFiles
from ABC.Torrent.connectmanager import TorrentConnections
from ABC.Torrent.actions import TorrentActions
from ABC.Torrent.config import TorrentConfig
from ABC.Torrent.dialogs import TorrentDialogs
from ABC.Torrent.status import TorrentStatus

from Utility.constants import * #IGNORE:W0611
from Tribler.unicode import name2unicode
from Tribler.Category.Category import Category
from Tribler.vwxGUI.torrentManager import TorrentDataManager
from Tribler.Video.VideoPlayer import VideoPlayer,is_vodable

from time import time

try:
    True
except:
    True = 1
    False = 0

DEBUG = False


import threading




################################################################
#
# Class: ABCTorrent
#
# Stores information about a torrent and keeps track of its
# status
#
################################################################
class ABCTorrent:
    def __init__(self, queue, src = None, dest = None, forceasklocation = False, caller = "", caller_data = None):
        self.queue = queue
        self.utility = self.queue.utility
        self.mypref_db = self.utility.mypref_db
        self.torrent_db = self.utility.torrent_db
                
        self.list = self.utility.list
        self.listindex = len(self.utility.torrents["all"])

        self.src = src
        self.caller = caller
        self.caller_data = caller_data

        self.status = TorrentStatus(self)
        self.actions = TorrentActions(self)
        self.dialogs = TorrentDialogs(self)
        self.connection = TorrentConnections(self)

        if DEBUG:
            print >>sys.stderr,"abctorrent: forceask is",forceasklocation

        #########
        self.metainfo = self.getResponse()
        if self.metainfo is None:
            return

        # Get infohash first before doing anything else
        self.infohash = sha(bencode(self.metainfo['info'])).hexdigest()
        self.torrent_hash = sha(bencode(self.metainfo['info'])).digest()
                
        self.torrentconfig = TorrentConfig(self)
             
        # check for unicode name
        self.namekey = name2unicode(self.metainfo)

        # Check for valid windows filename
        if sys.platform == 'win32':
            fixedname = self.utility.fixWindowsName(self.metainfo['info'][self.namekey])
            if fixedname: 
                self.metainfo['info'][self.namekey] = fixedname
                # Arno: see name2unicode
                self.metainfo['info']['name'] = fixedname
        
        self.info = self.metainfo['info']

        self.title = None
        self.newlyadded = False
                      
        # Initialize values to defaults

        self.files = TorrentFiles(self)
        
        # Setup the destination
        self.files.setupDest(dest, forceasklocation, caller)
        
        if self.files.dest is None:
            return
       
        #########

        # Priority "Normal"
        priorities = [ self.utility.lang.get('highest'), 
                       self.utility.lang.get('high'), 
                       self.utility.lang.get('normal'), 
                       self.utility.lang.get('low'), 
                       self.utility.lang.get('lowest') ]
        currentprio = self.utility.config.Read('defaultpriority', "int")
        if currentprio < 0:
            currentprio = 0
        elif currentprio >= len(priorities):
            currentprio = len(priorities) - 1
        self.prio = currentprio
       
        self.color = { 'text': None, 
                       'bgcolor': None } 
        
        # Done flag
        self.messages = { "current": "", 
                          "log": [], 
                          "timer": None }

        self.checkedonce = False
        
        self.totalpeers = "?"
        self.totalseeds = "?"
        
        self.peer_swarm = {}    # swarm of each torrent, used to display peers on map
        self.libraryPanel = None
        

        self.download_on_demand = False
        self.videoinfo = None
        self.progressinf = None
        self.prevactivetorrents = None

        self.vodable = is_vodable(self)


    def addTorrentToDB(self):
        
        # Arno: Checking for presence in the database causes some problems 
        # during testing sometimes, and it makes sense to update the database 
        # to the latest values.
        if self.torrent_db.hasTorrent(self.torrent_hash):
            return
            
        torrent = {}
        torrent['torrent_dir'], torrent['torrent_name'] = os.path.split(self.src)
        #torrent['relevance'] = 100*1000
        
        torrent_info = {}
        torrent_info['name'] = self.info.get(self.namekey, '')
        length = 0
        nf = 0
        if self.info.has_key('length'):
            length = self.info.get('length', 0)
            nf = 1
        elif self.info.has_key('files'):
            for li in self.info['files']:
                nf += 1
                if li.has_key('length'):
                    length += li['length']
        torrent_info['length'] = length
        torrent_info['num_files'] = nf
        torrent_info['announce'] = self.metainfo.get('announce', '')
        torrent_info['announce-list'] = self.metainfo.get('announce-list', '')
        torrent_info['creation date'] = self.metainfo.get('creation date', 0)
        torrent['info'] = torrent_info
        torrent['category'] = Category.getInstance()\
                        .calculateCategory(self.metainfo.get('info', {}), torrent_info['name'])            
        torrent["ignore_number"] = 0
        torrent["last_check_time"] = long(time())
        torrent["retry_number"] = 0
        torrent["seeder"] = -1
        torrent["leecher"] = -1
        torrent["status"] = "unknown"
#        if (torrent['category'] != []):
#            print '### one torrent added from abctorrent '+ str(torrent['category']) + '###'
        
        self.torrent_db.addTorrent(self.torrent_hash, torrent, new_metadata=True)  
        self.torrent_db.sync()
        Category.__reloadFlag = True 
        if DEBUG:
            print >> sys.stderr, "abctorrent: add torrent to db", self.infohash, torrent_info

        
    def addMyPref(self):
        self.addTorrentToDB()
        
        if self.mypref_db.hasPreference(self.torrent_hash):
            return

        mypref = {}
        if self.files.dest:
            mypref['content_dir'] = self.files.dest    #TODO: check
            mypref['content_name'] = self.files.filename

        # If this is a helper torrent, don't add it as my preference
        #if self.caller_data is None:
        self.mypref_db.addPreference(self.torrent_hash, mypref)
        if self.utility.abcfileframe is not None:
            self.utility.abcfileframe.updateMyPref()
            
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.data_manager.addNewPreference(self.torrent_hash)
        self.data_manager.setBelongsToMyDowloadHistory(self.torrent_hash, True)
        
        #if self.caller_data is None:
        self.utility.buddycast.addMyPref(self.torrent_hash)
        if DEBUG:
            print >> sys.stderr, "abctorrent: add mypref to db", self.infohash, mypref
        
    #
    # Tasks to perform when first starting adding this torrent to the display
    #
    def postInitTasks(self,activate=True):        
        self.utility.torrents["all"].append(self)
        self.utility.torrents["inactive"][self] = 1
        
        # Read extra information about the torrent
        self.torrentconfig.readAll()
        
        if not activate:
            self.status.value = STATUS_STOP
    
        # Add a new item to the list
        self.list.InsertStringItem(self.listindex, "")
        
        # Allow updates
        self.status.dontupdate = False
        
        # Add Status info in List
        self.updateColumns(force = True)
        
        self.updateColor()
        
        # Update the size to reflect torrents with pieces set to "download never"
        self.files.updateRealSize()
        
        # Do a quick check to see if it's finished
        self.status.isDoneUploading()

        self.addMyPref()
        

    #
    # As opposed to getColumnText,
    # this will get numbers in their raw form for doing comparisons
    # 
    # default is used when getting values for sorting comparisons
    # (this way an empty string can be treated as less than 0.0)
    #
    def getColumnValue(self, colid = None, default = 0.0):
        if colid is None:
            colid = COL_TITLE
        value = None

        activetorrent = self.status.isActive(checking = False, pause = False)
        
        try:
            if colid == COL_PROGRESS: # Progress
                progress = self.files.progress
                if self.status.isActive(pause = False):
                    progress = self.connection.engine.progress
                value = progress
    
            elif colid == COL_PRIO: # Priority
                value = self.prio
    
            elif colid == COL_ETA: # ETA
                if activetorrent:
                    if self.status.completed:
                        if self.connection.getSeedOption('uploadoption') == '0':
                            value = 999999999999999
                        else:
                            value = self.connection.seedingtimeleft
                    elif self.connection.engine.eta is not None:
                        value = self.connection.engine.eta
    
            elif colid == COL_SIZE: # Size
                value = self.files.floattotalsize
    
            elif colid == COL_DLSPEED: # DL Speed
                if activetorrent and not self.status.completed:
                    if self.connection.engine.hasConnections:
                        value = self.connection.engine.rate['down']
                    else:
                        value = 0.0
    
            elif colid == COL_ULSPEED: # UL Speed
                if activetorrent:
                    if self.connection.engine.hasConnections:
                        value = self.connection.engine.rate['up']
                    else:
                        value = 0.0
    
            elif colid == COL_RATIO: # %U/D Size
                if self.files.downsize == 0.0 : 
                    ratio = ((self.files.upsize/self.files.floattotalsize) * 100)
                else:
                    ratio = ((self.files.upsize/self.files.downsize) * 100)
                value = ratio
    
            elif colid == COL_SEEDS: # #Connected Seed
                if activetorrent:
                    value = self.connection.engine.numseeds
            
            elif colid == COL_PEERS: # #Connected Peer
                if activetorrent:
                    value = self.connection.engine.numpeers
            
            elif colid == COL_COPIES: # #Seeing Copies
                if (activetorrent
                    and self.connection.engine.numcopies is not None):
                    value = float(0.001*int(1000*self.connection.engine.numcopies))
            
            elif colid == COL_PEERPROGRESS: # Peer Avg Progress
                if (self.connection.engine is not None
                    and self.connection.engine.peeravg is not None):
                    value = self.connection.engine.peeravg
            
            elif colid == COL_DLSIZE: # Download Size
                value = self.files.downsize
            
            elif colid == COL_ULSIZE: # Upload Size
                value = self.files.upsize
            
            elif colid == COL_TOTALSPEED: # Total Speed
                if activetorrent:
                    value = self.connection.engine.totalspeed
            
            elif colid == COL_SEEDTIME: # Seeding time
                value = self.connection.seedingtime
            
            elif colid == COL_CONNECTIONS: # Connections
                if activetorrent:
                    value = self.connection.engine.numconnections
            
            elif colid == COL_SEEDOPTION: # Seeding option
                option = int(self.connection.getSeedOption('uploadoption'))
                if option == 0:
                    # Unlimited
                    value = 0.0
                elif option == 1:
                    text = "1." + str(self.connection.getTargetSeedingTime())
                    value = float(text)
                elif option == 2:
                    text = "1." + str(self.connection.getSeedOption('uploadratio'))
                    value = float(text)
            else:
                value = self.getColumnText(colid)
        except:
            value = self.getColumnText(colid)
            
        if value is None or value == "":
            return default
            
        return value
                
    #
    # Get the text representation of a given column's data
    # (used for display)
    #
    def getColumnText(self, colid):
        text = None

        activetorrent = self.status.isActive(checking = False, pause = False)
        
        try:
            if colid == COL_TITLE: # Title
                if self.title is None:
                    text = self.files.filename
                else:
                    text = self.title
                
            elif colid == COL_PROGRESS: # Progress
                progress = self.files.progress
                if self.status.isActive(pause = False):
                    progress = self.connection.engine.progress
                
                # Truncate the progress value rather than round down
                # (will show 99.9% for incomplete torrents rather than 100.0%)
                progress = int(progress * 10)/10.0
                
                text = ('%.1f' % progress) + "%"

            elif colid == COL_BTSTATUS: # BT Status
                text = self.status.getStatusText()

            elif colid == COL_PRIO: # Priority
                priorities = [ self.utility.lang.get('highest'), 
                               self.utility.lang.get('high'), 
                               self.utility.lang.get('normal'), 
                               self.utility.lang.get('low'), 
                               self.utility.lang.get('lowest') ]
                text = priorities[self.prio]

            elif colid == COL_ETA and activetorrent: # ETA
                value = None
                if self.status.completed:
                    if self.connection.getSeedOption('uploadoption') == "0":
                        text = "(oo)"
                    else:
                        value = self.connection.seedingtimeleft
                        text = "(" + self.utility.eta_value(value, truncate=2) + ")"
                elif self.connection.engine.eta is not None:
                    value = self.connection.engine.eta
                    text = self.utility.eta_value(value, truncate=2)

            elif colid == COL_SIZE: # Size                            
                # Some file pieces are set to "download never"
                if self.files.floattotalsize != self.files.realsize:
                    label = self.utility.size_format(self.files.floattotalsize, textonly = True)
                    realsizetext = self.utility.size_format(self.files.realsize, truncate = 1, stopearly = label, applylabel = False)
                    totalsizetext = self.utility.size_format(self.files.floattotalsize, truncate = 1)
                    text = realsizetext + "/" + totalsizetext
                else:
                    text = self.utility.size_format(self.files.floattotalsize)
                    
            elif (colid == COL_DLSPEED
                  and activetorrent
                  and not self.status.completed): # DL Speed
                if self.connection.engine.hasConnections:
                    value = self.connection.engine.rate['down']
                else:
                    value = 0.0
                text = self.utility.speed_format(value)

            elif colid == COL_ULSPEED and activetorrent: # UL Speed
                if self.connection.engine.hasConnections:
                    value = self.connection.engine.rate['up']
                else:
                    value = 0.0
                text = self.utility.speed_format(value)

            elif colid == COL_RATIO: # %U/D Size
                if self.files.downsize == 0.0 : 
                    ratio = ((self.files.upsize/self.files.floattotalsize) * 100)
                else:
                    ratio = ((self.files.upsize/self.files.downsize) * 100)
                text = '%.1f' % (ratio) + "%"

            elif colid == COL_MESSAGE: # Error Message
                text = self.messages["current"]
                # If the error message is a system traceback, write an error
                if text.find("Traceback") != -1:
                    sys.stderr.write(text + "\n")

            elif colid == COL_SEEDS: # #Connected Seed
                seeds = "0"
                if activetorrent:
                    seeds = ('%d' % self.connection.engine.numseeds)

                text = seeds + " (" + str(self.totalseeds) + ")"

            elif colid == COL_PEERS: # #Connected Peer
                peers = "0"
                if activetorrent:
                    peers = ('%d' % self.connection.engine.numpeers)
                    
                text = peers + " (" + str(self.totalpeers) + ")"

            elif (colid == COL_COPIES
                  and activetorrent
                  and self.connection.engine.numcopies is not None): # #Seeing Copies
                text = ('%.3f' % float(0.001*int(1000*self.connection.engine.numcopies)))

            elif (colid == COL_PEERPROGRESS
                  and activetorrent
                  and self.connection.engine.peeravg is not None): # Peer Avg Progress
                text = ('%.1f%%'%self.connection.engine.peeravg)

            elif colid == COL_DLSIZE: # Download Size
                text = self.utility.size_format(self.files.downsize)
                
            elif colid == COL_DLANDTOTALSIZE: # Download Size
                text = self.utility.size_format(self.files.downsize, truncate=1) +'/'+\
                       self.utility.size_format(self.files.floattotalsize, truncate =1)

            elif colid == COL_ULSIZE: # Upload Size
                text = self.utility.size_format(self.files.upsize)

            elif colid == COL_TOTALSPEED and activetorrent: # Total Speed
                text = self.utility.speed_format(self.connection.engine.totalspeed, truncate = 0)

            elif colid == COL_NAME: # Torrent Name
                text = os.path.split(self.src)[1]

            elif colid == COL_DEST: # Destination
                text = self.files.dest

            elif colid == COL_SEEDTIME: # Seeding time
                value = self.connection.seedingtime
                if value > 0:
                    text = self.utility.eta_value(value)

            elif colid == COL_CONNECTIONS and activetorrent: # Connections
                if self.connection.engine is not None:
                    text = ('%d' % self.connection.engine.numconnections)

            elif colid == COL_SEEDOPTION:
                value = self.connection.getSeedOption('uploadoption')
                if value == "0":
                    # Unlimited
                    text = 'oo'
                elif value == "1":
                    targettime = self.connection.getTargetSeedingTime()
                    text = self.utility.eta_value(targettime, 2)
                elif value == "2":
                    text = str(self.connection.getSeedOption('uploadratio')) + "%"
        except:
            nowactive = self.status.isActive(checking = False, pause = False)
            # Just ignore the error if it was caused by the torrent changing
            # from active to inactive
            if activetorrent != nowactive:
                # Note: if we have an error returning the text for
                #       the column used to display errors, just output
                #       to stderr, since we don't want to cause an infinite
                #       loop. 
                data = StringIO()
                print_exc(file = data)
                if colid != 13:
                    self.changeMessage(data.getvalue(), type = "error")
                else:
                    sys.stderr.write(data.getvalue())

        if text is None:
            text = ""
            
        return text

   

    #
    # Update multiple columns in the display
    # if columnlist is None, update all columns
    # (only visible columns will be updated)
    #
    def updateColumns(self, columnlist = None, force = False):

        if DEBUG:
            if threading.currentThread().getName() != "MainThread":
                print >> sys.stderr,"abctorrent: updateColumns thread",threading.currentThread()
                print >> sys.stderr,"abctorrent: NOT MAIN THREAD"
                print_stack()

        if columnlist is None:
            columnlist = range(self.list.columns.minid, self.list.columns.maxid)
            
        try:
            for colid in columnlist:
                #print colid,
                # Don't do anything if ABC is shutting down
                # or minimized
                if self.status.dontupdate or not self.utility.frame.GUIupdate:
                    if DEBUG:
                         print "torrent: update cols: not updating cols, GUIupdate is",self.utility.frame.GUIupdate, time()
                    return

                # Only update if this column is currently shown
                rank = self.list.columns.getRankfromID(colid)
                if (rank == -1):
                    continue
                
                text = self.getColumnText(colid)
                
                if not force:
                    # Only update if the text has changed
                    try:
                        oldtext = self.list.GetItem(self.listindex, rank).GetText()
                    except:
                        oldtext = ""
    
                    if text != oldtext:
                        force = True
                
                if force:
                    self.list.SetStringItem(self.listindex, rank, text)
                    
        except wx.PyDeadObjectError, msg:
            print >> sys.stderr,"abctorrent: error updateColumns:", msg
            pass
               
    #
    # Update the text and background color for the torrent
    # 
    # colorString should be the name of a valid entry in
    #             the config file for a color
    #
    # force allows forcing the color update even if the values
    #       don't appear to have changed
    #       (needed when moving list items, since we're only
    #        comparing the value that we last set the color to
    #        not the acutal color of the list item to save time)
    #
#    def updateColor(self, colorString = None, force = False):
    def updateColor(self, force = False):

        if DEBUG:
            if threading.currentThread().getName() != "MainThread":
                print >> sys.stderr,"abctorrent: updateColour thread",threading.currentThread()
                print >> sys.stderr,"abctorrent: colour NOT MAIN THREAD"
                print_stack()

        # Don't do anything if ABC is shutting down
        if self.status.dontupdate:
            return

        # Don't update display while minimized/shutting down
        if not self.utility.frame.GUIupdate:
            return
        
        colorString = None
        if self.connection.engine is not None:
            colorString = self.connection.engine.color

        if colorString is None:
            colorString = 'color_startup'
        
        color = self.utility.config.Read(colorString, "color")
                    
        # Update color            
        if (self.utility.config.Read('stripedlist', "boolean")) and (self.listindex % 2):
            bgcolor = self.utility.config.Read('color_stripe', "color")
        else:
            # Use system specified background:
            bgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)

        # Only update the color if it has changed
        # (or if the force flag is set to True)
        if (force
            or self.color['bgcolor'] is None
            or bgcolor != self.color['bgcolor']
            or self.color['text'] is None
            or color != self.color['text']):
            
            try:
                item = self.list.GetItem(self.listindex)
                item.SetTextColour(color)
                item.SetBackgroundColour(bgcolor)
                self.list.SetItem(item)
                
                self.color['text'] = color
                self.color['bgcolor'] = bgcolor
            except:
                self.color['text'] = None
                self.color['bgcolor'] = None
                

    #
    # Update the fields that change frequently
    # for active torrents
    #
    def updateSingleItemStatus(self):

        if threading.currentThread().getName() != "MainThread":
            print >> sys.stderr,"abctorrent: updateSingleItem thread",threading.currentThread()
            print >> sys.stderr,"abctorrent: NOT MAIN THREAD"
            print_stack()


        # Ignore 4, 5, 7, 9, 12, 13, 18, 22, 25
        
        # Do check to see if we're done uploading
        self.status.isDoneUploading()
               
        self.updateColumns([COL_PROGRESS, 
                            COL_BTSTATUS, 
                            COL_ETA, 
                            COL_DLSPEED, 
                            COL_ULSPEED, 
                            COL_SEEDS, 
                            COL_PEERS, 
                            COL_COPIES, 
                            COL_PEERPROGRESS, 
                            COL_ULSIZE, 
                            COL_TOTALSPEED, 
                            COL_NAME, 
                            COL_SEEDTIME, 
                            COL_CONNECTIONS])

        self.updateColor('color_startup')
        
    #
    # Get metainfo for the torrent
    #
    def getResponse(self):
        if self.status.isActive():
            #active process
            metainfo = self.connection.engine.dow.getResponse()
        else:
            #not active process
            metainfo = self.utility.getMetainfo(self.src)

        return metainfo

    #
    # Get information about the torrent to return to the webservice
    #
    def getInfo(self, fieldlist = None):
        # Default to returning all fields
        if fieldlist is None:
            fieldlist = range(self.list.columns.minid, self.list.columns.maxid)

        try :
            retmsg = ""

            for colid in fieldlist:
                retmsg += self.getColumnText(colid) + "|"
                       
            retmsg += self.infohash + "\n"
            
            return retmsg
        except:               
            # Should never get to this point
            return "|" * len(fieldlist) + "\n"
              
    #
    # Update the torrent with new scrape information
    #
    def updateScrapeData(self, newpeer, newseed, message = ""):

        if threading.currentThread().getName() != "MainThread":
            print >> sys.stderr,"abctorrent: updateScrapeData thread",threading.currentThread()
            print >> sys.stderr,"abctorrent: NOT MAIN THREAD"
            print_stack()


        self.actions.lastgetscrape = time()
        self.totalpeers = newpeer
        self.totalseeds = newseed
        self.updateColumns([COL_SEEDS, COL_PEERS])
        if message != "":
            if DEBUG:
                print >> sys.stderr,"abctorrent: message: " + message
            
            if message == self.utility.lang.get('scraping'):
                msgtype = "status"
            elif message == self.utility.lang.get('scrapingdone'):
                msgtype = "status"
                message += " (" + \
                           self.utility.lang.get('column14_text') + \
                           ": " + \
                           str(self.totalseeds) + \
                           " / " + \
                           self.utility.lang.get('column15_text') + \
                           ": " + \
                           str(self.totalpeers) + \
                           ")"
            else:
                msgtype = "error"
             
            self.changeMessage(message, msgtype)
        
        # Update detail window
        if self.dialogs.details is not None:
            self.dialogs.details.detailPanel.updateFromABCTorrent()

    def changeMessage(self, message = "", type = "clear"):       

        if threading.currentThread().getName() != "MainThread":
            print >> sys.stderr,"abctorrent: updateScrapeData thread",threading.currentThread()
            print >> sys.stderr,"abctorrent: NOT MAIN THREAD"
            print_stack()


        # Clear the error message
        if type == "clear":
            self.messages["current"] = ""
            self.updateColumns([COL_MESSAGE])
            return
        
        if not message:
            return
        
        now = time()
        self.messages["lasttime"] = now
        
        if type == "error" or type == "status":
            self.messages["current"] = strftime('%H:%M', localtime(now)) + " - " + message
            self.updateColumns([COL_MESSAGE])

        self.messages["log"].append([now, message, type])
        
        if self.dialogs.details is not None:
            self.dialogs.details.messageLogPanel.updateMessageLog()
        
    def makeInactive(self, update = True):          
        self.files.updateProgress()

        if self.status.value == STATUS_HASHCHECK:
            self.status.updateStatus(self.actions.oldstatus)
        elif self.status.value == STATUS_STOP:
            pass
        elif self.connection.engine is not None:
            # Ensure that this part only gets called once
            self.status.updateStatus(STATUS_QUEUE)
           
        # Write out to config
        self.torrentconfig.writeAll()
           
        if update:
            self.updateSingleItemStatus()

    def getTitle(self, kind = "current"):
        title = self.getColumnText(COL_TITLE)
        
        if kind == "original":
            title = self.metainfo['info'][self.namekey]
        elif kind == "torrent":
            torrentfilename = os.path.split(self.src)[1]
            (prefix,ext) = os.path.splitext(torrentfilename)
            title = prefix
        elif kind == "dest":
            if self.files.isFile():
                destloc = self.files.dest
            else:
                destloc = self.files.getProcDest(pathonly = True, checkexists = False)
            title = os.path.split(destloc)[1]
        
        return title

    def changeTitle(self, title):
        if title == self.files.filename:
            self.title = None
        else:
            self.title = title
        
        self.torrentconfig.writeNameParams()
        
        self.updateColumns([COL_TITLE])
            
    # Change the priority for the torrent
    def changePriority(self, prio):
        self.prio = prio
        self.updateColumns([COL_PRIO])
        self.torrentconfig.writePriority()
       

    def remove(self,removefiles):
        # Arno: remove torrentinfo file as well
        try:
            os.remove(self.torrentconfig.filename)
        except:
            pass

        self.connection.deleteTorrentData(self.torrent_hash)
        if removefiles:
            self.files.removeFiles()


    def checkAutoShutdown(self, autoShutdownTime):
        # Check if this torrent is in stop state for more than autoShutdownTime
        
        if self.status.value == STATUS_STOP and self.status.lastStopped != 0:
            return (time() - self.status.lastStopped) > autoShutdownTime
        else:
            return False
        
    # Things to do when shutting down a torrent
    def shutdown(self):
        # Set shutdown flag to true
        self.status.dontupdate = True
        
        self.torrentconfig.writeAll()
        
        if DEBUG:
            print >>sys.stderr,'abctorrent shutdown'
        # Remove abctorrent from librarypanel
        if self.libraryPanel:
            self.libraryPanel.abcTorrentShutdown(self.torrent_hash)
        elif DEBUG:
            print 'abctorrent: has no libraryPanel'
            
        # Delete Detail Window
        ########################
        try:
            if self.dialogs.details is not None:
                self.dialogs.details.killAdv()
        except wx.PyDeadObjectError:
            pass

#        # (if it's currently active, wait for it to stop)
#        self.connection.stopEngine(waitForThread = True)
        self.connection.stopEngine()
        if self.get_on_demand_download():
            # We was VOD-ing
            videoplayer = VideoPlayer.getInstance()
            videoplayer.vod_stopped(self)

        # If this is a helper torrent, remove all traces
        if self.caller_data is not None:
            if DEBUG:
                print >>sys.stderr,"abctorrent: shutdown: Stopping from DOWNLOAD HELP"
            self.mypref_db.deletePreference(self.torrent_hash)
            self.data_manager.setBelongsToMyDowloadHistory(self.torrent_hash, False)
            if self.caller_data.has_key('coordinator_permid'):
                try:
                    os.remove(self.src)
                    os.remove(self.torrentconfig.filename)
                except:
                    pass
                self.files.removeFiles()
                if self.utility.abcquitting:
                    # Normally done in procREMOVE, except when stopping client
                    self.utility.torrents["all"].remove(self)        

        del self.utility.torrents["inactive"][self]
        
        
        
        
    def setLibraryPanel(self, panel):
        self.libraryPanel = panel

    def set_newly_added(self):
        self.newlyadded = True
    
    def clear_newly_added(self):
        ret = self.newlyadded
        self.newlyadded = False
        return ret

    def enable_on_demand_download(self):
        self.download_on_demand = True
        
    def disable_on_demand_download(self):
        self.download_on_demand = False
        
    def get_on_demand_download(self):
        return self.download_on_demand
    
    def set_videoinfo(self,info):
        self.videoinfo = info
        
    def get_videoinfo(self):
        return self.videoinfo
    
    def get_moviestreamtransport(self):
        return self.connection.get_moviestreamtransport()    

    def set_progressinf(self,progressinf):
        self.progressinf = progressinf

    def get_progressinf(self):
        return self.progressinf
    
    def set_previously_active_torrents(self,activetorrents):
        self.prevactivetorrents = activetorrents
        
    def get_previously_active_torrents(self):
        return self.prevactivetorrents

    def is_vodable(self):
        return self.vodable