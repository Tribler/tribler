import sys
import wx
import os

from string import find
from threading import Event, Thread, Semaphore
from time import strftime, localtime, time, sleep
from traceback import print_exc
from cStringIO import StringIO

from BitTornado.ConfigDir import *
from BitTornado.bencode import *
from BitTornado.download_bt1 import *
from BitTornado.natpunch import UPnP_test

from abcengine import ABCEngine

from Dialogs.dupfiledialog import DupFileDialog

from Utility.getscrapedata import ScrapeThread
from Utility.constants import *

def runBT(ABCTorrentTemp):
    ABCTorrentTemp.status['hasthread'] = True
    
    utility = ABCTorrentTemp.utility

    doneflag = ABCTorrentTemp.doneflag = Event()
    
    d = ABCTorrentTemp.abcengine_adr
    if d is None:
        ABCTorrentTemp.makeInactive()
        return
    
    params = ABCTorrentTemp.getBTParams()

    filesem = ABCTorrentTemp.utility.FILESEM
       
    filefunc = d.chooseFile
    statusfunc = d.updateStatus
    finfunc = d.finished
    errorfunc = d.error
    presets = {}
    exchandler = d.error
    failed = d.error
    appdataobj = None
    listen_port = None
    
    Read = utility.config.Read
    
    try:
        while True:
            try:
                config = parse_params(params, presets)
            except ValueError, e:
                failed('error: ' + str(e) + '\nrun with no args for parameter explanations')
                break
            if not config:
                errorfunc(get_usage())
                break
                               
            myid = createPeerID()
            seed(myid)
        
            rawserver = RawServer(doneflag, config['timeout_check_interval'], 
                                  config['timeout'], ipv6_enable = config['ipv6_enabled'], 
                                  failfunc = failed, errorfunc = exchandler)
        
            upnp_type = UPnP_test(config['upnp_nat_access'])

            tries = 0
            
            while (listen_port is None
                   and tries < 20
                   and len(ABCTorrentTemp.queue.availableports) > 0):
                testport = ABCTorrentTemp.queue.availableports.pop(0)
                try:
                    listen_port = rawserver.find_and_bind(testport, testport, 
                                    config['bind'], ipv6_socket_style = config['ipv6_binds_v4'], 
                                    upnp = upnp_type, randomizer = config['random_port'])
                    ABCTorrentTemp.listen_port = listen_port
                except socketerror:
                    # Even if the port wasn't available for use now,
                    # it might be available later
                    ABCTorrentTemp.queue.availableports.append(testport)
                    pass
                tries += 1
                
            if listen_port is None:
                failed(d.utility.lang.get('noportavailable'))
                break
        
            response = get_response(config['responsefile'], config['url'], failed)
            if not response:
                break

            infohash = sha(bencode(response['info'])).digest()
        
            dow = BT1Download(statusfunc, finfunc, errorfunc, exchandler, doneflag, 
                            config, response, infohash, myid, rawserver, listen_port, appdataobj)
            d.dow = dow
            
            # Delete the cache information if doing a hashcheck
            # (only necessary to delete the cache if fastresume is enabled)
            if (ABCTorrentTemp.status['value'] == STATUS_HASHCHECK and
                utility.config.Read('fastresume', "boolean")):
                dow.appdataobj.deleteTorrentData(dow.infohash)
        
            forcenewdir = Read('forcenewdir', "boolean")
            savedas = dow.saveAs(filefunc, forcenewdir = forcenewdir)
            if not savedas:
                break

            filesem.acquire()
            
            initSuccess = False
            while not initSuccess:
                try:
#                    if dow.initFiles(old_style = True, sem = filesem):
                    if dow.initFiles(old_style = True):
                        initSuccess = True
                    break
                except:
                    dow.appdataobj.deleteTorrentData(dow.infohash)
            
            filesem.release()
            
            if not initSuccess:
                break

            if not dow.startEngine():
                dow.shutdown()
                break
            dow.startRerequester()
            dow.autoStats()
        
            if not dow.am_I_finished():
                d.updateStatus(activity = 'connecting to peers')
           
            # Note that we've checked the file at least once
            ABCTorrentTemp.checkedonce = True
            
            # Skip on ahead to the normal procedure if the torrent was active
            # before doing the hashcheck
            if (ABCTorrentTemp.status['value'] == STATUS_HASHCHECK
                and not ABCTorrentTemp.actions.oldstatus['hasthread']):
                d.fin = True
                d.done(None)
            else:
                ABCTorrentTemp.status['value'] = STATUS_ACTIVE
                
                # Set the spew flag if the detail window is shown
                if ABCTorrentTemp.detail_adr is not None:
                    dow.spewflag.set()
    
                rawserver.listen_forever(dow.getPortHandler())

            dow.shutdown()
            
            break
    except:
        data = StringIO()
        print_exc(file = data)
        d.error(data.getvalue())
#        sys.stderr.write(data.getvalue())

    try:
        rawserver.shutdown()
    except:
#        data = StringIO()
#        print_exc(file = data)
#        d.error(data.getvalue())
#        sys.stderr.write(data.getvalue())
        pass

    if not d.fin:
        d.failed()
        
    if listen_port is not None:
        try:
            # Only add it back to the pool of available ports
            # if it's between the min and max ports
            # (this is so we don't add the port back if the user
            #  changed the port range after this download started)
            minport = Read('minport', "int")
            maxport = Read('maxport', "int")
            if (listen_port >= minport) and (listen_port <= maxport):
                if Read('randomport') == '1':
                    utility.queue.availableports.append(listen_port)
                else:
                    # Return the port to the beginning of the stack
                    utility.queue.availableports.insert(0, listen_port)
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

    ABCTorrentTemp.doneflag = None
    
    ABCTorrentTemp.status['hasthread'] = False

    ABCTorrentTemp.makeInactive()

class TorrentConfig:
    def __init__(self, ABCTorrent):
        self.ABCTorrent = ABCTorrent
        self.utility = ABCTorrent.utility
        
        self.writeflags = { "basicinfo": False,
                            "status": False,
                            "priority": False,
                            "filepriorities": False,
                            "progress": False,
                            "uploadparams": False,
                            "seedtime": False }
        
#        self.writeflag = Event()
#        self.writeflag.set()
    
    def writeAll(self):
#        self.writeflag.wait()
#        self.writeflag.clear()
        
        for key in self.writeflags:
            self.writeflags[key] = True
                
        index = str(self.ABCTorrent.listindex)
        torrentconfig = self.utility.torrentconfig
        
        torrentconfig.DeleteGroup(index)
        
        self.writeBasicInfo(False)
        self.writeStatus(False)
        self.writePriority(False)
        self.writeFilePriorities(False)
        self.writeProgress(False)
        self.writeUploadParams(False)
        self.writeSeedTime(False)
        
#        self.writeflag.set()

    def readParam(self, param, type = "string"):
        index = str(self.ABCTorrent.listindex)
        return self.utility.torrentconfig.Read(param, type, section = index)
        
    def writeParam(self, param, value, type = "string"):
        index = str(self.ABCTorrent.listindex)
        return self.utility.torrentconfig.Write(param, value, type, section = index)
        
    def deleteParam(self, param):
        index = str(self.ABCTorrent.listindex)
        return self.utility.torrentconfig.DeleteEntry(param, section = index)
        
    def writeBasicInfo(self, clearOld = True):
        if clearOld:
            if self.writeflags["basicinfo"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
        
        torrent = self.ABCTorrent

        # Write torrent information
        filename = os.path.split(torrent.src)[1]
        self.writeParam("src", filename)
        self.writeParam("dest", torrent.dest)
        
#        if clearOld:
#            self.writeflag.set()
        
        self.writeflags["basicinfo"] = False
    
    def writeUploadParams(self, clearOld = True):        
        if clearOld:
            if self.writeflags["uploadparams"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
        
        torrent = self.ABCTorrent
        
        # Write settings for local upload rate if available
        localmax = torrent.getLocalRate("up")
        if localmax != 0:
            self.writeParam("localmax", str(localmax))
        elif clearOld:
            self.deleteParam("localmax")

        localmaxdown = torrent.getLocalRate("down")
        if localmaxdown != 0:
            self.writeParam("localmaxdown", str(localmaxdown))
        elif clearOld:
            self.deleteParam("localmaxdown")

        maxupload = torrent.getMaxUpload(localonly = True)
        if maxupload is not None:
            self.writeParam("maxupload", str(maxupload))
        elif clearOld:
            self.deleteParam("maxupload")            

        for param in torrent.seedoptions:
            value = torrent.getSeedOption(param, localonly = True)
            if value is not None:
                self.writeParam(param, value)
            elif clearOld:
                self.deleteParam(param)
                
        if not torrent.timeout:
            self.writeParam("timeout", "0")
        elif clearOld:
            self.deleteParam("timeout")
            
#        if clearOld:
#            self.writeflag.set()
            
        self.writeflags["uploadparams"] = False
            
    def writeProgress(self, clearOld = True):
        if clearOld:
            if self.writeflags["progress"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
            
        torrent = self.ABCTorrent
        
        self.writeParam("downsize", str(torrent.downsize))
        self.writeParam("upsize", str(torrent.upsize))
        self.writeParam("progress", str(torrent.progress))
        
#        if clearOld:
#            self.writeflag.set()
        
        self.writeflags["progress"] = False
        
    def writeStatus(self, clearOld = True):
        if clearOld:
            if self.writeflags["status"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()

        torrent = self.ABCTorrent
               
        value = torrent.status['value']
        oldvalue = torrent.actions.oldstatus['value']
       
        if (value == STATUS_FINISHED
            or (value == STATUS_HASHCHECK and oldvalue == STATUS_FINISHED)):
            status = 2    # Torrent is finished
        elif value == STATUS_STOP:
            status = 1    # Torrent is stopped
        else:
            status = 0    # Torrent is queued
        
        if status != 0:
            self.writeParam("statusvalue", str(status))
        elif clearOld:
            self.deleteParam("statusvalue")
            
        if torrent.status['completed']:
            self.writeParam("complete", "1")
        elif clearOld:
            self.deleteParam("complete")
        
#        if clearOld:
#            self.writeflag.set()
        
        self.writeflags["status"] = False
        
    def writePriority(self, clearOld = True):
        if clearOld:
            if self.writeflags["priority"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
            
        torrent = self.ABCTorrent
        
        self.writeParam("prio", str(torrent.prio))
        
#        if clearOld:
#            self.writeflag.set()
            
        self.writeflags["priority"] = False
        
    def writeSeedTime(self, clearOld = True):
        if clearOld:
            if self.writeflags["seedtime"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
        
        torrent = self.ABCTorrent
        
        if torrent.seedingtime > 0:
            self.writeParam("seedtime", str(int(torrent.seedingtime)))
        elif clearOld:
            self.deleteParam("seedtime")
            
#        if clearOld:
#            self.writeflag.set()
            
        self.writeflags["seedtime"] = False
        
    def writeFilePriorities(self, clearOld = True):
        if clearOld:
            if self.writeflags["filepriorities"]:
                return
            
#            self.writeflag.wait()
#            self.writeflag.clear()
        
        torrent = self.ABCTorrent
        
        notdefault, text = torrent.getFilePrioritiesAsString()
        if notdefault:
            self.writeParam("fileprio", text)
        elif clearOld:
            self.deleteParam("fileprio")
            
#        if clearOld:
#            self.writeflag.set()
            
        self.writeflags["filepriorities"] = False
            
    def readAll(self):
        torrent = self.ABCTorrent
        
        # Download size
        downsize = self.readParam("downsize")
        if downsize != "":
            try:
                torrent.downsize = float(downsize)
            except:
                pass
        
        # Upload size
        upsize = self.readParam("upsize")
        if upsize != "":
            try:
                torrent.upsize = float(upsize)
            except:
                pass
        
        # Status
        # Format from earlier 2.7.0 builds:
        status = self.readParam("status")
        if status == "completed":
            torrent.status['completed'] = True
        elif status == "pause":
            torrent.status['value'] = STATUS_STOP

        status = self.readParam("statusvalue")
        if status == "2":
            torrent.status['value'] = STATUS_FINISHED
        elif status == "1":
            torrent.status['value'] = STATUS_STOP
            
        complete = self.readParam("complete", "boolean")
        if complete:
            torrent.status['completed'] = True
       
        # Priority
        prio = self.readParam("prio")
        if prio != "":
            try:
                torrent.prio = int(prio)
            except:
                pass
            
        # File priorities
        fileprio = self.readParam("fileprio")
        if fileprio != "":
            filepriorities = fileprio.split(",")
            
            # Just in case there's a mismatch in sizes,
            # don't try to get more values than exist
            # in the source or destination arrays
            len1 = len(filepriorities)
            len2 = len(torrent.filepriorities)
            rangeEnd = min(len1, len2)
            for i in range(0, rangeEnd):
                try:
                    torrent.filepriorities[i] = int(filepriorities[i])
                except:
                    pass

        # Progress
        if torrent.status['completed'] or torrent.status['value'] == STATUS_FINISHED:
            torrent.progress = 100.0
        else:
            progress = self.readParam("progress")
            if progress != "":
                try:
                    torrent.progress = float(progress)
                except:
                    pass
                
        # Local upload options
        localmax = self.readParam("localmax", "int")
        if localmax != 0:
            torrent.maxlocalrate['up'] = str(localmax)

        localmaxdown = self.readParam("localmaxdown", "int")
        if localmaxdown != 0:
            torrent.maxlocalrate['down'] = str(localmaxdown)

        maxupload = self.readParam("maxupload", "int")
        torrent.setMaxUpload(maxupload)

        for param in torrent.seedoptions:
            value = self.readParam(param)
            if value != "":
                torrent.seedoptions[param] = value
                
        timeout = self.readParam("timeout")
        if timeout == "0":
            torrent.timeout = False
            
        seedtime = self.readParam("seedtime")
        if seedtime != "":
            try:
                torrent.seedingtime = int(seedtime)
                torrent.seedingtimeleft -= torrent.seedingtime
            except:
                pass
        
class TorrentActions:
    def __init__(self, ABCTorrent):
        self.ABCTorrent = ABCTorrent
        self.utility = ABCTorrent.utility
        
        self.lastgetscrape = 0
        
        self.oldstatus = self.ABCTorrent.status.copy()

    def scrape(self, faildialog = False, manualscrape = False):
        # Manual Scraping should be done no more than once per minute
        if (manualscrape):
            if (time() - self.lastgetscrape < 60):
                if faildialog:
                    dlg = wx.MessageDialog(None, self.utility.lang.get('warningscrapelessthanmin'), self.utility.lang.get('error'), wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                return
        # Automatic Scraping can be done as often as once an hour
        elif (self.lastgetscrape != 0) and ((time() - self.lastgetscrape) < 1200):
            # Scraping again too soon
            return

        ScrapeThread(self.utility, self.ABCTorrent).start()
        self.lastgetscrape = time()
    
    # pause a torrent or release it,
    # returns True if we actually did something
    def pause(self, release = False):
        torrent = self.ABCTorrent
        
        # We need to release the torrent
        if release:
            return self.pauseResume()
        
        # Pause the torrent if it isn't already paused or queued
        if torrent.status['value'] == STATUS_PAUSE or not torrent.isActive():
            return False

        self.oldstatus = torrent.status.copy()

        torrent.status['value'] = STATUS_PAUSE

        if torrent.abcengine_adr is not None and torrent.abcengine_adr.dow is not None:
            torrent.abcengine_adr.dow.Pause()

        torrent.updateSingleItemStatus()
        return True
        
    def pauseResume(self):
        torrent = self.ABCTorrent
        
        if torrent.status['value'] != STATUS_PAUSE:
            return False

        torrent.status['value'] = self.oldstatus['value']

        # pause an active process
        ###########################################
        if torrent.abcengine_adr is not None and torrent.abcengine_adr.dow is not None:
            torrent.abcengine_adr.dow.Unpause()
            return True

        return False

    # stop a single torrent, returns True if we actually did something
    def stop(self):
        torrent = self.ABCTorrent

        if torrent.isDoneUploading():
            return True
        
        if torrent.status['value'] == STATUS_STOP:
            return False
        
        torrent.stopABCEngine(update = False)
        
        torrent.status['value'] = STATUS_STOP
        
        torrent.updateSingleItemStatus()
        
        return True
        
    # Return True if we put something into queue
    def queue(self):
        torrent = self.ABCTorrent
        
        if torrent.isDoneUploading():
            # Might need to return True to show something happened
            return True

        # Do nothing if already queued, stopped, or done uploading
        if torrent.status['value'] == STATUS_QUEUE:
            return False

        torrent.stopABCEngine(update = False)
        
        torrent.status['value'] = STATUS_QUEUE
        
        torrent.updateSingleItemStatus()
        
        return True

    def resume(self):
        torrent = self.ABCTorrent
        
        ################### Resume for On-Hold State ###########################
        if torrent.status['value'] == STATUS_PAUSE:
            return self.pauseResume()

        ################## Resume for Other inactive States ##############################
        
        # Don't resume if done uploading or currently active
        if torrent.isDoneUploading():
            return True
        
        if torrent.status['hasthread']:
            return False

        # If there's no more reserved ports available,
        # only on-hold torrents may start
        if (len(self.utility.queue.availableports) == 0):
            return False
            
        # If the file is complete and it's finished uploading,
        # don't need to resume
        if self.ABCTorrent.isDoneUploading():
            self.ABCTorrent.updateSingleItemStatus()
            # This may indicate that something has changed, so return True
            return True

        torrent.status['value'] = STATUS_QUEUE
        
        torrent.maxrate['up'] = "0"
        
        torrent.startABCEngine()
        
        return True

    def hashCheck(self):
        torrent = self.ABCTorrent

        self.oldstatus = torrent.status.copy()
        
        # (if it's currently active, wait for it to stop)
        torrent.stopABCEngine(True)
        
        torrent.startABCEngine(STATUS_HASHCHECK)

        return True

class ABCTorrent:
    def __init__(self, queue, src = None, dest = None, forceasklocation = False, caller = ""):
        self.queue = queue
        self.utility = self.queue.utility
        self.list = self.utility.list
        self.listindex = len(self.queue.proctab)

        # set queue status
        self.status = { 'value' : STATUS_QUEUE, 
                        'completed': False, 
                        'dontupdate': True,  # Don't update until the list item is created
                        'hasthread': False }

        self.torrentconfig = TorrentConfig(self)
        self.actions = TorrentActions(self)

        self.src = src
        
        #########
        
        self.abcengine_adr = None
        
        self.metainfo = self.getResponse()
        if self.metainfo is None:
            return

        self.info = self.metainfo['info']
        self.filename = self.info['name']
        self.infohash = sha(bencode(self.info)).hexdigest()
                      
        # Initialize values to defaults
        
        # Array to store file priorities
        self.filepriorities = []
        
        if self.info.has_key('length'):   #1 file for this torrent
            file_length = self.info['length']
            self.filepriorities.append(1)
        else:   # Directory torrent
            file_length = 0
            for x in self.info['files']:
                file_length += x['length']
                # Append the priority for each file...
                # Just using a placeholder of 1 (Normal) for now
                self.filepriorities.append(1)

        #########

        self.floattotalsize = float(file_length)
        self.realsize = self.floattotalsize

        self.dest = dest
        
        # Treat an empty string for dest the same as
        # not having one defined
        if self.dest == "":
            self.dest = None

        # For new torrents, get the destination where to save the torrent
        if self.dest is None:
            self.getDestination(forceasklocation, caller)

        # Treat an empty string for dest the same as
        # not having one defined
        if self.dest == "":
            self.dest = None

        # If we still don't have a destination, return
        if self.dest is None:
            return

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

        # This one is to store the download progress ; if it's not stored, the progress
        # of an inactive torrent would stay only in the display of the list, and so it would
        # be lost if the GUI wouldn't display the column "progress". In this case it couldn't
        # be saved in the torrent.lst file.
        self.progress = 0.0
        self.downsize = 0.0
        self.upsize = 0.0
        
        self.detail_adr = None

        self.maxupload = None

        self.maxrate = {}

        # upload rate bandwidth reserved for this torrent
        self.maxrate['up'] = "0"
        self.maxrate['down'] = "0"

        self.maxlocalrate = {}

        # Maximum upload rate not to be exceeded, defined in local settings
        self.maxlocalrate['up'] = "0"
        self.maxlocalrate['down'] = "0"

        self.seedoptions = { 'uploadoption': None, 
                             'uploadtimeh': None, 
                             'uploadtimem': None, 
                             'uploadratio': None }
        
        self.color = { 'text': wx.Colour(0, 0, 0), 
                       'bgcolor': wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW) }
        
        self.totalpeers = "?"
        self.totalseeds = "?"
        
        # Done flag
        self.doneflag = None
        self.errormsg = ""
        self.messagelog = []
#        self.scrapedlg_adr = None
        
        self.listen_port = None

        self.seedingtime = 0
        self.seedingtimeleft = self.getTargetSeedingTime()

        self.checkedonce = False
        
        self.timeout = True
        
    # Tasks to perform when first starting adding this torrent to the display
    def postInitTasks(self):        
        # Read extra information about the torrent
        self.torrentconfig.readAll()
    
        # Add a new item to the list
        self.list.InsertStringItem(self.listindex, "")
        
        # Allow updates
        self.status['dontupdate'] = False
        
        # Add Status info in List
        self.updateColumns()
        
        self.updateColor()
        
        # Update the size to reflect torrents with pieces set to "download never"
        self.updateRealSize()
        
        # Do a quick check to see if it's finished
        self.isDoneUploading()
        
    # Specify where to save the torrent
    def getDestination(self, forceasklocation = False, caller = ""):
        # No default directory (or default directory can't be found)
        defaultfolder = self.utility.config.Read('defaultfolder')
        if not os.access(defaultfolder, os.F_OK):
            try:
                os.makedirs(defaultfolder)
            except:
                forceasklocation = True
                
        if ((self.utility.config.Read('setdefaultfolder') == '0' or forceasklocation)
            and (caller != "web")):
            success, dest = self.setDestination()
            if not success:
                try:
                    os.remove(dest)
                except:
                    pass
            else:
                self.dest = dest
        else:
            if self.info.has_key('length'):   #1 file for this torrent
                self.dest = os.path.join(self.utility.config.Read('defaultfolder'), self.filename)
            else:
                self.dest = self.utility.config.Read('defaultfolder')
                
    def setDestination(self):
        dest = self.dest

        if self.dest is None:
            # Use one set of strings if setting a location to start
            filetext = self.utility.lang.get('choosefiletosaveas') + '(' + self.getColumnText(9) +')'
            dirtext = self.utility.lang.get('choosedirtosaveto') + '(' + self.getColumnText(9) +')'
        else:
            # Use a different set of strings if we're setting a new location
            filetext = self.utility.lang.get('choosenewlocation') + '(' + self.getColumnText(9) +')'
            dirtext = self.utility.lang.get('choosenewlocation') + '(' + self.getColumnText(9) +')'
        
        defaultdir = self.utility.getLastDir("save")

        # What do we do if we don't have a default download location specified
        # and we call this from the webservice?
        ####################################################
        if self.info.has_key('length'):   #1 file for this torrent
            dlg = wx.FileDialog(None, filetext, defaultdir, self.filename, '*.*', wx.SAVE)
        else:   # Directory torrent
            dlg = wx.DirDialog(None, dirtext, defaultdir, style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        dlg.Raise()
        result = dlg.ShowModal()
        dlg.Destroy()
        if result != wx.ID_OK:
            return False, dest
        dest = dlg.GetPath()
        
        self.utility.lastdir['save'] = os.path.dirname(dest)
        
        self.dest = dest
        self.torrentconfig.writeBasicInfo()
        
        self.updateColumns([22])
        
        return True, dest
            
    def getProcDest(self, pathonly = False):
        # Set it to self.dest (should be fine for files)
        dest = self.dest
        
        # In the case of a multifile torrent, see where we're saving
        if not self.isFile():
            ## see if we're saving to a subdirectory or not
            existing = 0
            if os.path.exists(dest):
                if not os.path.isdir(dest):
                    dest = None
                if len(os.listdir(dest)) > 0:  # if it's not empty
                    for x in self.info['files']:
                        if os.path.exists(path.join(dest, x['path'][0])):
                            existing = 1
                    if not existing or self.utility.config.Read('forcenewdir', "boolean"):
                        dest = os.path.join(dest, self.info['name'])
        elif pathonly:
            # Strip out just the path for a regular torrent
            dest = os.path.dirname(self.dest)
                        
        if dest is not None and not os.access(dest, os.F_OK):
            return None
                        
        return dest

    def isFile(self):
        try:
            if self.info.has_key('length'):
                return True
            else:
                return False
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue()) # report exception here too
            return True, "whatwhereisyourdottorrent"
            
    def move(self, dest = None):
        if dest is None:
            dest = self.utility.config.Read('defaultmovedir')
        
        if not os.access(dest, os.F_OK):
            try:
                os.makedirs(dest)
            except:
                return False
       
        #Wait thread a little bit for returning resource
        ##################################################
        sleep(0.5)

        if self.isFile():
            self.moveSingleFile(dest)
        else:
            self.moveDir(dest)

        self.dest = os.path.join(dest, self.filename)
        
        return True
                                
    def moveSingleFile(self, dest):
        if not self.isFile():
            self.moveDir(dest)
            return

        done = False
        firsttime = True
        
        filename = os.path.split(self.dest)[1]
        source = os.path.split(self.dest)[0]
        size = int(self.info['length'])
        
        self.moveFiles({filename: size}, source, dest)
            
    def moveFiles(self, filearray, source, dest):
        dummyname = os.path.join(os.path.split(self.dest)[0], 'dummy')
        try:
            file(dummyname, 'w').close()
        except:
            pass
       
        overwrite = "ask"
       
        for filename in filearray:
            oldloc = os.path.join(source, filename)
            newloc = os.path.join(dest, filename)
            size = filearray[filename]

            done = False
            firsttime = True
                
            while not done:
                try:
                    # File exists
                    if os.access(oldloc, os.R_OK):
                        copyfile = True
                        
                        # Something already exists where we're trying to copy:
                        if os.access(newloc, os.F_OK):
                            delete = False
                            
                            # Default to "No"
                            result = -1
                            
                            if overwrite == "ask":
                                single = len(filearray) > 1
                                dialog = DupFileDialog(self, filename, single)
                                result = dialog.ShowModal()
                                if result == 2:
                                    overwrite = "yes"
                                elif result == -2:
                                    overwrite = "no"
                                    
                            if overwrite == "yes" or result > 0:
                                os.remove(newloc)
                            elif overwrite == "no" or result < 0:
                                copyfile = False
#                            message = "File : " + filename + "\n" + self.utility.lang.get('extracterrorduplicatemsg')
#                            dialog = wx.MessageDialog(None,
#                                                      message,
#                                                      self.utility.lang.get('extracterrorduplicate'),
#                                                      wx.YES_NO|wx.ICON_EXCLAMATION)
#                            result = dialog.ShowModal()
#
#                            if result == wx.ID_YES:
#                                # Delete the old file
#                                os.remove(newloc)
#                            else:
#                                # Don't delete it
#                                copyfile = False
                                
                        if copyfile:
                            os.renames(oldloc, newloc)
                    done = True
                except:
                    # There's a very special case for a file with a null size referenced in the torrent
                    # but not retrieved just because of this null size : It can't be renamed so we
                    # just skip it.
                    if size == 0:
                        done = True
                    else:
                        #retry >_<;
                        if firsttime:
                            firsttime = False
                            sleep(0.1)
                        else:
                            done = True
                            
                            data = StringIO()
                            print_exc(file = data)
                            
                            dialog = wx.MessageDialog(None, self.utility.lang.get('errormovefile') + "\n" + data.getvalue(), self.utility.lang.get('error'), wx.ICON_ERROR)
                            dialog.ShowModal()
                            dialog.Destroy()
                            
        try:
            os.remove(dummyname)
        except:
            pass
        
    def moveDir(self, dest):
        if self.isFile():
            self.moveSingleFile(dest)
            return
           
        destname = self.getProcDest()
       
        if destname is None:
            return
           
#        # Folder
#        dummyname = os.path.join(destname, 'dummy')
#        try:
#            file(dummyname, 'w').close()
#        except:
#            pass
#        
#        firstfile = True
        
        filearray = {}
        
        movename = os.path.join(dest, self.filename)
        for f in self.info['files']:
            for item in f['path']:
                size = int(f['length'])
                filearray[item] = size

        self.moveFiles(filearray, destname, movename)
#                firstfile = False
#                destname2 = os.path.join(destname, item)
#                movename2 = os.path.join(movename, item)
#                
#                done = False
#                firsttime = True
#                
#                while not done:
#                    try:
#                        if os.access(destname2, os.R_OK):
#                            os.renames(destname2, movename2)
#                        done = True
#                    except:
#                        # Special case for a file with a null size
#                        if int(f['length']) == 0:
#                            continue
#                        elif firsttime:
#                            #retry >_<;
#                            firsttime = False
#                            sleep(0.1)
#                        else:
#                            data = StringIO()
#                            print_exc(file = data)
#                            
#                            dialog = wx.MessageDialog(None, self.utility.lang.get('errormovefile') + "\n" + data.getvalue(), self.utility.lang.get('error'), wx.ICON_ERROR)
#                            dialog.ShowModal()
#                            dialog.Destroy()
#                            done = True            
#        try:
#            os.remove(dummyname)
#        except:
#            pass
        self.utility.RemoveEmptyDir(destname, True)
        
            
    def removeFiles(self):
        destination = self.getProcDest()
        
        if destination is None:
            return
      
        # Remove File
        ##################################################        
        done = False
        firsttime = True
        while not done:
            #Wait thread a little bit for returning resource
            ##################################################
            sleep(0.5)
            try:
                if self.isFile():
                    #remove file
                    if os.access(destination, os.F_OK):
                        os.remove(destination)
                else:                  
                    # Only delete files from this torrent
                    # (should be safer this way)
                    subdirs = 0
                    for x in self.info['files']:
                        filename = destination
                        subdirs = max(subdirs, len(x['path']) - 1)
                        for i in x['path']:
                            filename = os.path.join(filename, i)
                        if os.access(filename, os.F_OK):
                            os.remove(filename)
                    
                    self.utility.RemoveEmptyDir(destination, (subdirs > 0))
                done = True
            except:
                #retry >_<;
                if firsttime:
                    firsttime = False
                    sleep(0.1)
                else:
                    done = True
                    
                    data = StringIO()
                    print_exc(file = data)
                    
                    dialog = wx.MessageDialog(None, self.utility.lang.get('errordeletefile') + "\n" + data.getvalue(), self.utility.lang.get('error'), wx.ICON_ERROR)
                    dialog.ShowModal()
                    dialog.Destroy()


    # As opposed to getColumnText,
    # this will get numbers in their raw form for doing comparisons
    def getColumnValue(self, colid = None):
        if colid is None:
            colid = COL_TITLE
        value = None
        
        activetorrent = (self.abcengine_adr is not None
                         and self.status['value'] != STATUS_PAUSE
                         and not self.isCheckingOrAllocating())
        
        try:
            if colid == COL_PROGRESS: # Progress
                progress = self.progress
                if (self.abcengine_adr is not None) and self.status['value'] != STATUS_PAUSE:
                    progress = self.abcengine_adr.progress
                value = progress
    
            elif colid == COL_PRIO: # Priority
                value = self.prio
    
            elif colid == COL_ETA: # ETA
                if activetorrent:
                    if self.status['completed']:
                        if self.getSeedOption('uploadoption') == '0':
                            value = 999999999999999
                        else:
                            value = self.seedingtimeleft
                    elif self.abcengine_adr.eta is not None:
                        value = self.abcengine_adr.eta
    
            elif colid == COL_SIZE: # Size
                value = self.floattotalsize
    
            elif colid == COL_DLSPEED: # DL Speed
                if activetorrent and self.progress < 100.0:
                    value = self.abcengine_adr.rate['down']
    
            elif colid == COL_ULSPEED: # UL Speed
                if activetorrent:
                    value = self.abcengine_adr.rate['up']
    
            elif colid == COL_RATIO: # %U/D Size
                if self.downsize == 0.0 : 
                    ratio = ((self.upsize/self.floattotalsize) * 100)
                else:
                    ratio = ((self.upsize/self.downsize) * 100)
                value = ratio
    
            elif colid == COL_SEEDS: # #Connected Seed
                if activetorrent:
                    value = self.abcengine_adr.numseeds
            
            elif colid == COL_PEERS: # #Connected Peer
                if activetorrent:
                    value = self.abcengine_adr.numpeers
            
            elif colid == COL_COPIES: # #Seeing Copies
                if (activetorrent
                    and self.abcengine_adr.numcopies is not None):
                    value = float(0.001*int(1000*self.abcengine_adr.numcopies))
            
            elif colid == COL_PEERPROGRESS: # Peer Avg Progress
                if (self.abcengine_adr is not None
                    and self.abcengine_adr.peeravg is not None): 
                    value = self.abcengine_adr.peeravg
            
            elif colid == COL_DLSIZE: # Download Size
                value = self.downsize
            
            elif colid == COL_ULSIZE: # Upload Size
                value = self.upsize
            
            elif colid == COL_TOTALSPEED: # Total Speed
                if activetorrent:
                    value = self.abcengine_adr.totalspeed
            
            elif colid == COL_SEEDTIME: # Seeding time
                value = self.seedingtime
            
            elif colid == COL_CONNECTIONS: # Connections
                if activetorrent:
                    value = self.abcengine_adr.numconnections
            
            elif colid == COL_SEEDOPTION: # Seeding option
                option = int(self.getSeedOption('uploadoption'))
                if option == 0:
                    # Unlimited
                    value = 0.0
                elif option == 1:
                    text = "1." + str(self.getTargetSeedingTime())
                    value = float(text)
                elif option == 2:
                    text = "1." + str(self.getSeedOption('uploadratio'))
                    value = float(text)
            else:
                value = self.getColumnText(colid)
        except:
            value = self.getColumnText(colid)
            
        if value is None or value == "":
            return 0.0
            
        return value
                
    def getColumnText(self, colid):
        text = None
        
        activetorrent = (self.abcengine_adr is not None
                         and self.status['value'] != STATUS_PAUSE
                         and not self.isCheckingOrAllocating())
        
        try:
            if colid == COL_TITLE: # Title
                text = self.filename

            elif colid == COL_PROGRESS: # Progress
                progress = self.progress
                if (self.abcengine_adr is not None) and self.status['value'] != STATUS_PAUSE:
                    progress = self.abcengine_adr.progress
                    
                text = ('%.1f' % progress) + "%"

            elif colid == COL_BTSTATUS: # BT Status
                text = self.getStatusText()

            elif colid == COL_PRIO: # Priority
                priorities = [ self.utility.lang.get('highest'), 
                               self.utility.lang.get('high'), 
                               self.utility.lang.get('normal'), 
                               self.utility.lang.get('low'), 
                               self.utility.lang.get('lowest') ]
                text = priorities[self.prio]

            elif colid == COL_ETA and activetorrent: # ETA
                value = None
                if self.status['completed']:
                    if self.getSeedOption('uploadoption') == "0":
                        text = "(oo)"
                    else:
                        value = self.seedingtimeleft
                        text = "(" + self.utility.eta_value(value) + ")"
                elif self.abcengine_adr.eta is not None:
                    value = self.abcengine_adr.eta
                    text = self.utility.eta_value(value)

            elif colid == COL_SIZE: # Size                            
                # Some file pieces are set to "download never"
                if self.floattotalsize != self.realsize:
                    label = self.utility.size_format(self.floattotalsize, textonly = True)
                    realsizetext = self.utility.size_format(self.realsize, truncate = 1, stopearly = label, applylabel = False)
                    totalsizetext = self.utility.size_format(self.floattotalsize, truncate = 1)
                    text = realsizetext + "/" + totalsizetext
                else:
                    text = self.utility.size_format(self.floattotalsize)
                    
            elif (colid == COL_DLSPEED
                  and activetorrent
                  and self.progress < 100.0): # DL Speed
                text = self.utility.speed_format(self.abcengine_adr.rate['down'])

            elif colid == COL_ULSPEED and activetorrent: # UL Speed
                text = self.utility.speed_format(self.abcengine_adr.rate['up'])

            elif colid == COL_RATIO: # %U/D Size
                if self.downsize == 0.0 : 
                    ratio = ((self.upsize/self.floattotalsize) * 100)
                else:
                    ratio = ((self.upsize/self.downsize) * 100)
                text = '%.1f' % (ratio) + "%"

            elif colid == COL_MESSAGE: # Error Message
                text = self.errormsg
                # If the error message is a system traceback, write an error
                if find(text, "Traceback") != -1:
                    sys.stderr.write(text + "\n")

            elif colid == COL_SEEDS: # #Connected Seed
                seeds = "0"
                if activetorrent:
                    seeds = ('%d' % self.abcengine_adr.numseeds)
                    
                text = seeds + " (" + self.totalseeds + ")"

            elif colid == COL_PEERS: # #Connected Peer
                peers = "0"
                if activetorrent:
                    peers = ('%d' % self.abcengine_adr.numpeers)
                    
                text = peers + " (" + self.totalpeers + ")"

            elif (colid == COL_COPIES
                  and activetorrent
                  and self.abcengine_adr.numcopies is not None): # #Seeing Copies
                text = ('%.3f' % float(0.001*int(1000*self.abcengine_adr.numcopies)))

            elif (colid == COL_PEERPROGRESS
                  and activetorrent
                  and self.abcengine_adr.peeravg is not None): # Peer Avg Progress
                text = ('%.1f%%'%self.abcengine_adr.peeravg)

            elif colid == COL_DLSIZE: # Download Size
                text = self.utility.size_format(self.downsize)

            elif colid == COL_ULSIZE: # Upload Size
                text = self.utility.size_format(self.upsize)

            elif colid == COL_TOTALSPEED and activetorrent: # Total Speed
                text = self.utility.speed_format(self.abcengine_adr.totalspeed, truncate = 0)

            elif colid == COL_NAME: # Torrent Name
                text = os.path.split(self.src)[1]

            elif colid == COL_DEST: # Destination
                text = self.dest

            elif colid == COL_SEEDTIME: # Seeding time
                value = self.seedingtime
                if value > 0:
                    text = self.utility.eta_value(value)

            elif colid == COL_CONNECTIONS and activetorrent: # Connections
                if self.abcengine_adr is not None:
                    text = ('%d' % self.abcengine_adr.numconnections)

            elif colid == COL_SEEDOPTION:
                value = self.getSeedOption('uploadoption')
                if value == "0":
                    # Unlimited
                    text = 'oo'
                elif value == "1":
                    targettime = self.getTargetSeedingTime()
                    text = self.utility.eta_value(targettime, 2)
                elif value == "2":
                    text = str(self.getSeedOption('uploadratio')) + "%"
        except:
            nowactive = (self.abcengine_adr is not None
                         and self.status['value'] != STATUS_PAUSE
                         and not self.isCheckingOrAllocating())
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
        
    def getStatusText(self):       
        value = self.status['value']
        
        if self.isActive():
            if value == STATUS_PAUSE:
                status = self.utility.lang.get('pause')
            elif value == STATUS_SUPERSEED:
                status = status = self.utility.lang.get('superseeding')
            elif self.abcengine_adr is not None:
                status = self.abcengine_adr.btstatus
            else:
                status = self.utility.lang.get('stopping')
        elif value == STATUS_FINISHED:
            status = self.utility.lang.get('completed')
        elif value == STATUS_STOP:
            status = self.utility.lang.get('stop')
        elif value == STATUS_QUEUE:
            status = self.utility.lang.get('queue')
        else:
            status = "<unknown>"
        
        return status

    def updateColumns(self, columnlist = None):
        # Don't do anything if ABC is shutting down
        if self.utility.abcquitting or self.status['dontupdate']:
            return

        if columnlist is None:
            columnlist = range(4, self.utility.guiman.maxid)
            
        try:
            for colid in columnlist:
                if colid == 6: # BT Status
                    self.torrentconfig.writeStatus()
                elif colid == 7: # Priority
                    self.torrentconfig.writePriority()
        
                rank = self.utility.config.Read("column" + str(colid) + "_rank", "int")
                if (rank == -1):
                    continue
                
                text = self.getColumnText(colid)
        
                self.list.SetStringItem(self.listindex, rank, str(text))
        except:
            pass
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue()) # report exception here too                
               
    def updateColor(self, color = None, force = False):
        # Don't do anything if ABC is shutting down
        if self.utility.abcquitting or self.status['dontupdate']:
            return
        
        if color is None:
            color = self.color['text']
            
            # If the value was none
            if self.color['text'] is None:
                color = wx.Colour(0, 0, 0)
                
                    
        # Update color            
        if (self.utility.config.Read('stripedlist') == '1') and (self.listindex % 2):
            bgcolor = wx.Colour(245, 245, 245)
        else:
            # Use system specified background:
            bgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)

        # Only update the color if it has changed
        if (force
            or bgcolor != self.color['bgcolor']
            or self.color['text'] is None
            or color != self.color['text']):
            self.color['bgcolor'] = bgcolor
            try:
                item = self.list.GetItem(self.listindex)
                item.SetTextColour(color)
                item.SetBackgroundColour(bgcolor)
                self.list.SetItem(item)
                
                self.color['text'] = color
            except:
                self.color['text'] = None

    def updateSingleItemStatus(self):
        # Ignore 4, 5, 7, 9, 12, 13, 18, 22, 25
        
        # Do check to see if we're done uploading
        self.isDoneUploading()
               
        self.updateColumns([5, 6, 8, 10, 11, 14, 15, 16, 17, 19, 20, 21, 23, 24])
            
        self.updateColor(wx.Colour(0, 0, 0))
        
    def getResponse(self):
        if (self.abcengine_adr is not None) and (self.abcengine_adr.dow is not None):
            #active process
            metainfo = self.abcengine_adr.dow.getResponse()
        else:
            #not active process
            metainfo = self.utility.getMetainfo(self.src)

        return metainfo

    def getInfo(self, fieldlist = None):
        # Default to returning all fields
        if fieldlist is None:
            fieldlist = range(4, self.utility.guiman.maxid)

        try :
            retmsg = ""

            for colid in fieldlist:
                retmsg += self.getColumnText(colid) + "|"
                       
            retmsg += self.infohash + "\n"
            
            return retmsg
        except:               
            # Should never get to this point
            return "|" * (self.utility.guiman.maxid - 1) + "\n"
              
    def updateScrapeData(self, newpeer, newseed, message = ""):
        self.actions.lastgetscrape = time()
        self.totalpeers = newpeer
        self.totalseeds = newseed
        self.updateColumns([14, 15])
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
            
        self.updateColumns()
        
        # Update detail window
        if self.detail_adr is not None:
            self.detail_adr.detailPanel.updateFromABCTorrent()
    
    def changeMessage(self, message, type = ""):
        if message == "":
            return
        
        now = time()
        
        if type == "error" or type == "status":
            self.errormsg = strftime('%H:%M', localtime(now)) + " - " + message
            self.updateColumns([13])

        self.messagelog.append([now, message, type])
        
        if self.detail_adr is not None:
            self.detail_adr.messageLogPanel.updateMessageLog()

    def updateProgress(self):
        # update the download progress
        if self.abcengine_adr is not None:
            self.downsize = self.abcengine_adr.downsize['old'] + self.abcengine_adr.downsize['new']
            self.upsize = self.abcengine_adr.upsize['old'] + self.abcengine_adr.upsize['new']
            
            if (self.status['value'] != STATUS_PAUSE
                and not self.isCheckingOrAllocating()
                and self.abcengine_adr is not None):
                self.progress = self.abcengine_adr.progress
        
#        self.torrentconfig.writeProgress()
    
    # Is the torrent active?
    def isActive(self):
        value = self.status['value']
        activevalues = [ STATUS_ACTIVE, STATUS_PAUSE, STATUS_HASHCHECK, STATUS_SUPERSEED ]
        
        return (self.abcengine_adr is not None
                or self.status['hasthread']
                or value in activevalues)
    
    # See if the torrent is checking existing data or allocating
    def isCheckingOrAllocating(self):
        # If the torrent is in its initialization stage, the progress value
        # we get from ABCEngine won't reflect the download progress
        # 
        # Note: "moving data" is a third initialization status that is listed
        #       in the BitTornado source
        ######################################################################
        if not self.utility.abcquitting and self.status['hasthread']:
            status = self.getStatusText()
            statuslist = [ self.utility.lang.get('waiting'), 
                           self.utility.lang.get('checkingdata'),
                           self.utility.lang.get('allocatingspace'),
                           self.utility.lang.get('movingdata') ]
            if (status in statuslist):
                return True
        return False
                   
    def stopABCEngine(self, waitForThread = False, update = True):
        if self.detail_adr is not None:
            self.detail_adr.onStop()

        if self.abcengine_adr is not None:
            if self.status['value'] == STATUS_PAUSE:
                if self.abcengine_adr.dow is not None:
                    self.abcengine_adr.dow.Unpause()
            self.abcengine_adr.fin = True
            self.abcengine_adr.done(None)

        self.makeInactive(update)

        # Wait for the bittornado thread to finish
        if waitForThread:
            while self.status['hasthread']:
                sleep(0.5)
        
    def makeInactive(self, update = True):
        try:
            # Remove from the list of active torrents
            self.queue.activetorrents.remove(self)
        except:
            pass
           
        self.updateProgress()

        if self.status['value'] == STATUS_HASHCHECK:
            self.status['value'] = self.actions.oldstatus['value']
        elif self.abcengine_adr is not None:
            # Ensure that this part only gets called once
            self.status['value'] = STATUS_QUEUE
            
#        self.doneflag = None
        self.abcengine_adr = None
           
        if update:
            self.updateSingleItemStatus()
                
    def startABCEngine(self, status = STATUS_ACTIVE):
        # Wait for previous thread to finish
        # (just in case)
        while self.status['hasthread']:
            sleep(0.2)

        self.status['value'] = status

#        self.doneflag = Event()

        # Add to the list of active torrents
        self.queue.activetorrents.append(self)
        
        self.abcengine_adr = ABCEngine(self)

        self.updateSingleItemStatus() # BT Status

        thread = Thread(target = runBT, args = [self])
        thread.setDaemon(False)
        thread.start()
        
    def changeMaxInitiate(self):
        if (self.abcengine_adr is not None) and (self.abcengine_adr.dow is not None):
            self.abcengine_adr.dow.setConns(self.getMaxUpload())

            max_initiate = self.getMaxInitiate()
            if max_initiate is not None:
                self.abcengine_adr.dow.setInitiate(max_initiate)

    def resetUploadParams(self):
        self.changeMaxInitiate()
        
        self.torrentconfig.writeUploadParams()

        # Double-check to see if we're still done uploading
        self.isDoneUploading()
        
    def getLocalRate(self, dir, boolean = False):
        try:
            value = int(self.maxlocalrate[dir])
        except:
            value = 0
        
        if boolean:
            return value > 0
        else:
            return value
        
    def getMaxUpload(self, localonly = False):
        value = self.maxupload
        if value is None and not localonly:
            value = self.utility.config.Read('maxupload', "int")
        
        return value
        
    def getMaxInitiate(self):
        maxupload = self.getMaxUpload()
        max_initiate = self.utility.config.Read('max_initiate', "int")
        
        if max_initiate == 0:
            return None
        if maxupload < 4:
            max_initiate = min(12, max_initiate)
        elif maxupload < 30:
            max_initiate = min(40, max_initiate)
        else:
            max_initiate = min(maxupload + 10, max_initiate)
            
        return max_initiate
        
    def setMaxUpload(self, value):
        try:
            value = int(value)
        except:
            value = 0
        
        default = self.utility.config.Read('maxupload', "int")
        if value == default or value == 0:
            self.maxupload = None
        else:
            self.maxupload = value
        
    def getSeedOption(self, param, localonly = False):
        value = self.seedoptions[param]
        if value is None and not localonly:
            value = self.utility.config.Read(param)

        return value
        
    def setSeedOption(self, param, value):
        default = self.utility.config.Read(param)
        if value == default:
            self.seedoptions[param] = None
        else:
            self.seedoptions[param] = value
            
        self.updateColumns([25])

    def changeLocalInfo(self, info):
        # 0 = auto rate
        self.maxlocalrate['up'] = info['uploadrate']
        if self.maxlocalrate['up'] != "0":
            self.maxrate['up'] = info['uploadrate']

        self.maxlocalrate['down'] = info['downloadrate']
        if self.maxlocalrate['down'] != "0":
            self.maxrate['down'] = info['downloadrate']

        self.setMaxUpload(info['maxupload'])

        #active process
        self.changeMaxInitiate()

        for param in self.seedoptions:
            self.setSeedOption(param, info[param])
        
        self.timeout = info['timeout']
        
        self.torrentconfig.writeUploadParams()
        
        # Double-check to see if we're still done uploading
        self.isDoneUploading()
        
    def setRate(self, speed = None, dir = "up"):
        if speed is None:
            speed = self.getLocalRate(dir)
            if speed == 0:
                speed = float(self.maxrate[dir])
                
        try:
            if self.abcengine_adr is not None and self.abcengine_adr.dow is not None:
                if dir == "up":
                    # Set upload rate
                    self.abcengine_adr.dow.setUploadRate(float(speed))
                elif not self.status['completed']:
                    # Set download rate
                    # (only makes sense if not complete)
                    self.abcengine_adr.dow.setDownloadRate(float(speed))
        except:
            pass
                          
    def superSeed(self):
        if self.isActive():
            if self.progress != 100.0:
                #dialog your file is not completed don't use SUPERSEED
                dlg = wx.MessageDialog(None, self.utility.lang.get('superseederrornotcompleted')  , self.utility.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
            elif self.status['value'] == STATUS_SUPERSEED:
                #check if super seed already run
                dlg = wx.MessageDialog(None, self.utility.lang.get('superseedisalreadyenable')  , self.utility.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
            else:
                #dialogbox warning after use this mode can't go back
                dlg = wx.MessageDialog(None, self.utility.lang.get('superwarningmsg'), self.utility.lang.get('warning'), wx.OK|wx.CANCEL)
                # (Modify to destroy dialog)
                result = dlg.ShowModal()
                dlg.Destroy()
                if result != wx.ID_OK:
                    return

                if (self.abcengine_adr.dow is not None):
                    #Enter super-seed mode
                    self.status['value'] = STATUS_SUPERSEED
                    # one way change, don't go back
                    self.abcengine_adr.dow.set_super_seed()
                    # change BTstatus to super-seeding
                    self.updateColumns([6])
        else:
            #dialogbox running torrent before using super-seed mode
            dlg = wx.MessageDialog(None, self.utility.lang.get('superseedmustruntorrentbefore'), self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
                       
    def getBTParams(self):
        # Construct BT params
        ###########################
        btparams = []
        
        btparams.append("--display_interval")
        btparams.append("0.8")
        
        btparams.append("--responsefile")
        btparams.append(self.src)
        btparams.append("--max_uploads")
        btparams.append(str(self.getMaxUpload()))
        btparams.append("--min_uploads")
        btparams.append(str(self.getMaxUpload()))

        #if self.utility.config.Read('ipv6') == "1":
        #    btparams.append("--ipv6_enable")
        #    btparams.append(self.utility.config.Read('ipv6'))
        #    btparams.append("--ipv6_binds_v4")
        #    btparams.append(self.utility.config.Read('ipv6_binds_v4'))
        
        # Fast resume
        btparams.append("--selector_enabled")
        btparams.append(self.utility.config.Read('fastresume'))
        
        btparams.append("--auto_kick")
        btparams.append(self.utility.config.Read('kickban'))
        btparams.append("--security")
        btparams.append(self.utility.config.Read('notsameip'))
        
        # Set the file priorities if necessary
        notdefault, text = self.getFilePrioritiesAsString()
        if notdefault:
            btparams.append("--priority")
            btparams.append(text)

        btparams.append("--max_upload_rate")
        btparams.append("0")
        
        paramlist = [ "ip", 
                      "bind", 
                      "alloc_rate", 
                      "alloc_type", 
                      "double_check", 
                      "triple_check", 
                      "lock_while_reading", 
                      "lock_files", 
                      "min_peers", 
                      "max_files_open", 
                      "max_connections", 
                      "upnp_nat_access", 
                      "auto_flush" ]
        for param in paramlist:
            value = self.utility.config.Read(param)
            if value != "":
                btparams.append("--" + param)
                btparams.append(self.utility.config.Read(param))
               
        max_initiate = self.getMaxInitiate()
        if max_initiate is not None:
            btparams.append("--max_initiate")
            btparams.append(str(max_initiate))            
        
        if self.dest != "":
            btparams.append("--saveas")
            btparams.append(self.dest)
            
        return btparams           
            
    def changePriority(self, prio):
        self.prio = prio
        self.updateColumns([7])
        
    def updateRealSize(self):
        if self.info.has_key('length'):   #1 file for this torrent
            file_length = self.info['length']
        else:   # Directory torrent
            file_length = 0
            count = 0
            for x in self.info['files']:
                # Add up the length of files not set to "download never"
                if self.filepriorities[count] != -1:
                    file_length += x['length']
                count += 1
                
        self.realsize = float(file_length)
        
        self.updateColumns([COL_SIZE])
    
    # Set the priorities for all of the files in a multi-file torrent    
    def setFilePriorities(self, priority_array = None):       
        if priority_array is not None:
            self.filepriorities = priority_array
            self.torrentconfig.writeFilePriorities()
            self.updateRealSize()
        
        if self.abcengine_adr is not None and self.abcengine_adr.dow is not None:
            self.abcengine_adr.dow.fileselector.set_priorities(self.filepriorities)
            
    def getFilePrioritiesAsString(self):
        notdefault = False
        text = ""
        if len(self.filepriorities) > 1:
            for entry in self.filepriorities:
                if entry != 1:
                    notdefault = True
                text += ('%d,' % entry)
            # Remove the trailing ","
            text = text[:-1]

        return notdefault, text
               
    def getTargetSeedingTime(self):
        uploadtimeh = self.getSeedOption('uploadtimeh')
        uploadtimem = self.getSeedOption('uploadtimem')
        uploadtimes = (int(uploadtimeh)*3600) + (int(uploadtimem)*60)
            
        return uploadtimes            
    
    def isDoneUploading(self):        
        finished = False
        
        # If the file isn't finished, or it's set to unlimited upload
        if self.progress != 100.0:
            pass

        elif (self.getSeedOption('uploadoption') == "1"):
            uploadtimes = self.getTargetSeedingTime()
            
            if uploadtimes < 1800: #Cheat people edit config file..unlimited upload!
                pass
            elif self.seedingtime >= uploadtimes:
                finished = True
        
        elif (self.getSeedOption('uploadoption') == "2"
            and self.getColumnValue(12) >= float(self.getSeedOption('uploadratio'))):
            finished = True
            
        # Also mark as completed in case it wasn't for some reason
        if finished:
            self.status['value'] = STATUS_FINISHED
            self.status['completed'] = True
        elif self.status['value'] == STATUS_FINISHED:
            # Was finished before, but isn't now
            self.status['value'] = STATUS_QUEUE
            
        self.updateColumns([6])

        return finished
       
    # Things to do when shutting down a torrent
    def shutdown(self):
        # Set shutdown flag to true
        self.status['dontupdate'] = True
        
        # Delete Detail Window
        ########################
        try:
            if self.detail_adr is not None:
                self.detail_adr.killAdv()
        except wx.PyDeadObjectError:
            pass

        self.stopABCEngine(True)