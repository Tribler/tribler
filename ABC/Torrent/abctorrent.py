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
        self.list = self.utility.list
        self.listindex = len(self.utility.torrents["all"])

        self.src = src
        self.caller = caller
        self.caller_data = caller_data

        self.status = TorrentStatus(self)
        self.actions = TorrentActions(self)
        self.dialogs = TorrentDialogs(self)
        self.connection = TorrentConnections(self)

        #########
        self.metainfo = self.getResponse()
        if self.metainfo is None:
            return

        # Get infohash first before doing anything else
        self.infohash = sha(bencode(self.metainfo['info'])).hexdigest()
        self.torrent_hash = sha(bencode(self.metainfo['info'])).digest()
                
        self.torrentconfig = TorrentConfig(self)
             
        # Check for valid windows filename
        if sys.platform == 'win32':
            fixedname = self.utility.fixWindowsName(self.metainfo['info']['name'])
            if fixedname:
                self.metainfo['info']['name'] = fixedname
        
        self.info = self.metainfo['info']

        self.title = None
                      
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
        self.addTorrent(self.utility.all_files_cache)
        
    def addTorrent(self, FileCacheHandler):
        torrent = {}
        torrent['file'] = os.path.split(self.src)[1]
        torrent['path'] = self.src
        info = self.metainfo['info']
        torrent['name'] = info.get('name', '')
        length = 0
        nf = 0
        if info.has_key('length'):
            length = info.get('length', 0)
            nf = 1
        elif info.has_key('files'):
            for li in info['files']:
                nf += 1
                if li.has_key('length'):
                    length += li['length']
        torrent['length'] = length
        torrent['numfiles'] = nf
        FileCacheHandler.addTorrent(self.torrent_hash, torrent)
             
    #
    # Tasks to perform when first starting adding this torrent to the display
    #
    def postInitTasks(self):        
        self.utility.torrents["all"].append(self)
        self.utility.torrents["inactive"][self] = 1
        
        # Read extra information about the torrent
        self.torrentconfig.readAll()
    
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
                        text = "(" + self.utility.eta_value(value) + ")"
                elif self.connection.engine.eta is not None:
                    value = self.connection.engine.eta
                    text = self.utility.eta_value(value)

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
            print "updateColumns thread",threading.currentThread()
            if threading.currentThread().getName() != "MainThread":
                print "NOT MAIN THREAD"
                print_stack()
                return

        if columnlist is None:
            columnlist = range(self.list.columns.minid, self.list.columns.maxid)
            
        try:
            for colid in columnlist:
                #print colid,
                # Don't do anything if ABC is shutting down
                # or minimized
                if self.status.dontupdate or not self.utility.frame.GUIupdate:
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
                    #print "<< enter self.list.SetStringItem", self.listindex, "|", rank, "|", text
                    self.list.SetStringItem(self.listindex, rank, text)
                    #print ">> leave list.SetStringItem"
                    pass
                    
        except wx.PyDeadObjectError, msg:
            print "error updateColumns:", msg
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
            print "updateColour thread",threading.currentThread()
            if threading.currentThread().getName() != "MainThread":
                print "colour NOT MAIN THREAD"
                return


#        print "<<< enter updateColor"
        # Don't do anything if ABC is shutting down
        if self.status.dontupdate:
            return

        # Don't update display while minimized/shutting down
        if not self.utility.frame.GUIupdate:
            return
        
#        print "updateColor 1"
        
        colorString = None
        if self.connection.engine is not None:
            colorString = self.connection.engine.color

        if colorString is None:
            colorString = 'color_startup'
        
        color = self.utility.config.Read(colorString, "color")
                    
#        print "updateColor 2"
        
        # Update color            
        if (self.utility.config.Read('stripedlist', "boolean")) and (self.listindex % 2):
            bgcolor = self.utility.config.Read('color_stripe', "color")
        else:
            # Use system specified background:
            bgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)

 #       print "updateColor 3"
        
        # Only update the color if it has changed
        # (or if the force flag is set to True)
        if (force
            or self.color['bgcolor'] is None
            or bgcolor != self.color['bgcolor']
            or self.color['text'] is None
            or color != self.color['text']):
            
            try:
#                print "updateColor 4"
                item = self.list.GetItem(self.listindex)
#                print "updateColor 5"
                item.SetTextColour(color)
#                print "updateColor 6"
                item.SetBackgroundColour(bgcolor)
#                print "updateColor 7"
                self.list.SetItem(item)
#                print "updateColor 8"
                
                self.color['text'] = color
                self.color['bgcolor'] = bgcolor
            except:
#                print "updateColor except error"
                self.color['text'] = None
                self.color['bgcolor'] = None
                
#        print ">>> leave updateColor"

    #
    # Update the fields that change frequently
    # for active torrents
    #
    def updateSingleItemStatus(self):

        print "updateSingleItem thread",threading.currentThread()
        if threading.currentThread().getName() != "MainThread":
            print "item NOT MAIN THREAD"
            return


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

        print "updateScrapeData thread",threading.currentThread()
        if threading.currentThread().getName() != "MainThread":
            print "scrape NOT MAIN THREAD"
            return


        self.actions.lastgetscrape = time()
        self.totalpeers = newpeer
        self.totalseeds = newseed
        self.updateColumns([COL_SEEDS, COL_PEERS])
        if message != "":
            print "message: " + message
            
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

        print "changeMesage thread",threading.currentThread()
        if threading.currentThread().getName() != "MainThread":
            print "message NOT MAIN THREAD"
            ##return


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
            title = self.metainfo['info']['name']
        elif kind == "torrent":
            torrentfilename = os.path.split(self.src)[1]
            torrentfilename = torrentfilename[:torrentfilename.rfind('.torrent')]
            title = torrentfilename
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
       
    # Things to do when shutting down a torrent
    def shutdown(self):
        # Set shutdown flag to true
        self.status.dontupdate = True
        
        self.torrentconfig.writeAll()
        
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
        
        del self.utility.torrents["inactive"][self]
