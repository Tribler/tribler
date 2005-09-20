import wx
import sys

from operator import itemgetter
from threading import Event
from time import strftime, time, sleep
from traceback import print_exc
from cStringIO import StringIO
    
from Utility.constants import *
    
wxEVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)
    
def DELEVT_INVOKE(win):
    win.Disconnect(-1, -1, wxEVT_INVOKE)
   
class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        wx.PyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs

class ABCEngine(wx.EvtHandler):
    def __init__(self, ABCTorrent):   #pos = map position of thread in CtrlList
        wx.EvtHandler.__init__(self)
        self.torrent = ABCTorrent
        self.queue = ABCTorrent.queue
        self.utility = ABCTorrent.utility

        self.downsize = { 'old' : ABCTorrent.downsize, 
                          'new' : 0.0 }
        self.upsize = { 'old' : ABCTorrent.upsize, 
                        'new' : 0.0 }
        
        self.fin = False
        self.spewwait = time()

        self.reannouncelast = 0
        self.lastexternalannounce = ''

        self.timers = { 'lastupload': time(), 
                        'lastdownload': time() }

        self.btstatus = self.utility.lang.get('waiting')
        self.progress = ABCTorrent.progress
        self.eta = None
        self.rate = { "down" : 0.0, 
                      "up" : 0.0 }

        self.numpeers = 0
        self.numseeds = 0

        self.numconnections = 0
        self.numcopies = None
        self.peeravg = None
        self.totalspeed = 0.0
        self.numerrortracker=0
        self.lasterrortracker=0
        
        self.current_ratesetting = None
        
        self.seedingtimelastcheck = None

        # To compute mean over 5 last values of uprate/downrate        
        self.pastrate = { "down" : [], 
                          "up" : [] }
        self.meanrate = { "down" : 0.0, 
                          "up" : 0.0 }
                     
        # Keep track of if we have any connections
        self.hasConnections = False
        
        self.dow = None

        EVT_INVOKE(self, self.onInvoke)

    def onInvoke(self, event):
        if ((self.torrent.doneflag is not None)
            and (not self.torrent.doneflag.isSet())):
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if ((self.torrent.doneflag is not None)
            and (not self.torrent.doneflag.isSet())):
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))

    def updateStatus(self, dpflag = Event(), fractionDone = None, 
            timeEst = None, downRate = None, upRate = None, 
            activity = None, statistics = None, spew = None, sizeDone = None, 
            **kws):

        self.setActivity(activity)

        self.invokeLater(self.onUpdateStatus, [dpflag, fractionDone, timeEst, downRate, upRate, activity, statistics, spew, sizeDone])
#        self.onUpdateStatus(dpflag, fractionDone, timeEst, downRate, upRate, activity, statistics, spew, sizeDone)
        
    def setActivity(self, activity):
        if activity is not None:
            activities = { "connecting to peers": self.utility.lang.get('connectingtopeers'),
                           "checking existing data": self.utility.lang.get('checkingdata'),
                           "allocating disk space": self.utility.lang.get('allocatingspace'),
                           "moving data": self.utility.lang.get('movingdata') }
            try:
                self.btstatus = activities[activity]
            except:
                self.btstatus = activity
        
    def onUpdateStatus(self, dpflag, fractionDone, timeEst, downRate, upRate, activity, statistics, spew, sizeDone):
        if self.torrent.status['value'] != STATUS_PAUSE:
            # Recheck Upload Rate
            ############################
            if (self.dow is not None):
                if float(self.torrent.maxrate['up']) != (self.dow.config['max_upload_rate']):
                    self.dow.setUploadRate(float(self.torrent.maxrate['up']))
            
        # Get scrape data every 20 minutes
        #############################################
        if self.utility.config.Read('scrape', "boolean"):
            self.torrent.actions.scrape()
       
        # Get Display Data
        #############################################
        if fractionDone is not None and not self.fin:
            self.progress = (float(fractionDone) * 100)

        if timeEst is not None and not self.fin:
            self.btstatus = self.utility.lang.get('working')

            self.eta = timeEst
        else:
            if activity is not None and not self.fin:
                self.setActivity(activity)
#                self.btstatus = activity

            self.eta = None
        
        if self.torrent.status['value'] != STATUS_PAUSE:
            if not self.fin and downRate is not None:
                self.rate['down'] = float(downRate)
                if self.rate['down'] != 0.0:
                    self.timers['lastdownload'] = time()
            else:
                self.rate['down'] = 0.0
                       
            if upRate is not None:
                self.rate['up'] = float(upRate)
                if self.rate['up'] != 0.0:
                    self.timers['lastupload'] = time()

                # Compute mean uprate

                self.pastrate['up'].append(self.rate['up'])
                if len(self.pastrate['up']) > 20:
                    self.pastrate['up'].pop(0)
                total = 0.0
                for i in self.pastrate['up']:
                    total += i
                self.meanrate['up'] = total / len(self.pastrate['up'])
            else:
                self.rate['up'] = 0.0

        if statistics is not None:
            self.numpeers = statistics.numPeers
            self.numcopies  = statistics.numCopies
            self.peeravg    = statistics.percentDone

            # Update download, upload, and progress
            self.downsize['new'] = float(statistics.downTotal)
            self.upsize['new'] = float(statistics.upTotal)
            self.torrent.updateProgress()
            self.totalspeed = float(statistics.torrentRate)
            self.numconnections = statistics.numPeers

            if not self.fin:
                self.numseeds = statistics.numSeeds
                self.numconnections += statistics.numSeeds
            else:
                self.numseeds = statistics.numOldSeeds
        else:
            self.peeravg = None
            self.numcopies = None
        
        ##################################################
        # Set colour :
        ##################################################
        color = None
        
        if statistics is None: 
            color = wx.Colour(0, 0, 0) #Start up
            self.hasConnections = False
        elif statistics.numPeers + statistics.numSeeds + statistics.numOldSeeds == 0:
            if statistics.last_failed:
                color = wx.Colour(100, 100, 100)    #Disconnected
            else:
                color = wx.Colour(200, 0, 0)    #No connections
            self.hasConnections = False
        elif (not statistics.external_connection_made):
            color = wx.Colour(150, 150, 0)    #No incoming
            self.hasConnections = True
        elif ((statistics.numSeeds + statistics.numOldSeeds == 0)
               and ((self.fin and statistics.numCopies < 1)
                or (not self.fin and statistics.numCopies2 < 1))):
            color = wx.Colour(0, 0, 150)    #No completes
            self.hasConnections = True
        else:
            color = wx.Colour(0, 150, 0)   #All Good
            self.hasConnections = True

        self.torrent.updateColor(color)

        if self.fin:
            self.countSeedingTime()
            if self.torrent.isDoneUploading():
                self.invokeLater(self.TerminateUpload)

        # Update text strings
        self.torrent.updateColumns([5, 6, 8, 10, 11, 13])
        if statistics is not None:
            # Share Ratio, #Seed, #Peer, #Copies, #Peer Avg Progress,
            # Download Size, Upload Size, Total Speed
            self.torrent.updateColumns([12, 14, 15, 16, 17, 18, 19, 20, 23, 24])

        self.updateDetailWindow(statistics, spew)
        self.updateInfoWindow(statistics)

        self.CheckTimeouts()

        dpflag.set()
    
    # See if there's been a timeout
    def CheckTimeouts(self):
        # Check to see if we need to check for timeouts
        if not self.torrent.timeout or self.torrent.status['value'] == STATUS_PAUSE:
            return
        
        # Check no download transfer in 30 mins
        # (when this torrent is leeching torrent)
        ##########################################
        if not self.fin:
            timeoutdownload = self.utility.config.Read('timeoutdownload')
            if (timeoutdownload != 'oo'
                and (time() - self.timers['lastdownload']) > (float(timeoutdownload)*60)):
                self.ReducePrioandForceQueue()
                return

        # Check no upload transfer in 1 hour
        # (when this torrent is seeding torrent)
        ##########################################
        else:
            timeoutupload = self.utility.config.Read('timeoutupload')
            if ((timeoutupload != 'oo')
                and (time() - self.timers['lastupload']) > (float(timeoutupload)*3600)):
                self.ReducePrioandForceQueue()
                return

    def updateDetailWindow(self, statistics, spew):
        #####################################################
        # Detail Window display part
        #####################################################
        detailwin = self.torrent.detail_adr
        if detailwin is None:
            return
        detailpanel = detailwin.detailPanel
        
        if statistics is not None:
            detailpanel.updateFromABCTorrent()
                      
        if spew is not None and (time() - self.spewwait > 1):
            self.updateSpewList(statistics, spew)

        if statistics is not None:
            detailpanel.storagestats1.SetLabel("          " + self.utility.lang.get('detailline1')
                             % (statistics.storage_active, 
                                 statistics.storage_new, 
                                 statistics.storage_dirty))
            detailpanel.storagestats2.SetLabel("          "+ self.utility.lang.get('detailline2')
                             % (statistics.storage_numcomplete, 
                                 statistics.storage_totalpieces, 
                                 statistics.storage_justdownloaded, 
                                 statistics.storage_numflunked))


    def updateSpewList(self, statistics, spew):
        detailwin = self.torrent.detail_adr
        if detailwin is None:
            return
        
        self.spewwait = time()
        spewList = detailwin.detailPanel.spewList
        spewlen = len(spew)+2

        if statistics is not None:
           kickbanlen = len(statistics.peers_kicked)+len(statistics.peers_banned)
           if kickbanlen:
               spewlen += kickbanlen + 1
        else:
            kickbanlen = 0
        try:
            for x in range(spewlen-spewList.GetItemCount()):
                i = wx.ListItem()
                spewList.InsertItem(i)
            for x in range(spewlen, spewList.GetItemCount()):
                spewList.DeleteItem(len(spew)+1)
    
            tot_uprate = 0.0
            tot_downrate = 0.0
            
            starflag = { True : '*', False : ' ' }
    
            # Sort by uprate first
            spew.sort(key=itemgetter('uprate'), reverse = True)
            if self.torrent.progress < 100.0:
                # Then sort by downrate if not complete
                spew.sort(key=itemgetter('downrate'), reverse = True)
    
            for x in range(len(spew)):
                spewList.SetStringItem(x, 0, starflag[spew[x]['optimistic']])
                spewList.SetStringItem(x, 1, spew[x]['ip'])
                spewList.SetStringItem(x, 2, spew[x]['direction'])
    
                if spew[x]['uprate'] > 100:
                    spewList.SetStringItem(x, 3, self.utility.speed_format(spew[x]['uprate'], truncate = 0))
                else:
                    spewList.SetStringItem(x, 3, ' ')
                tot_uprate += spew[x]['uprate']
    
                spewList.SetStringItem(x, 4, starflag[spew[x]['uinterested']])
                spewList.SetStringItem(x, 5, starflag[spew[x]['uchoked']])
    
                if spew[x]['downrate'] > 100:
                    spewList.SetStringItem(x, 6, self.utility.speed_format(spew[x]['downrate'], truncate = 0))
                else:
                    spewList.SetStringItem(x, 6, ' ')
                tot_downrate += spew[x]['downrate']
    
                spewList.SetStringItem(x, 7, starflag[spew[x]['dinterested']])
                spewList.SetStringItem(x, 8, starflag[spew[x]['dchoked']])
                spewList.SetStringItem(x, 9, starflag[spew[x]['snubbed']])
                spewList.SetStringItem(x, 10, self.utility.size_format(float(spew[x]['dtotal'])))
    
                if spew[x]['utotal'] is not None:
                    utotal = self.utility.size_format(float(spew[x]['utotal']))
                else:
                    utotal = ''
                spewList.SetStringItem(x, 11, utotal)
    
                spewList.SetStringItem(x, 12, '%.1f%%' % (float(int(spew[x]['completed']*1000))/10))
    
                if spew[x]['speed'] is not None:
                    a = self.utility.speed_format(spew[x]['speed'], truncate = 0)
                else:
                    a = ''
                spewList.SetStringItem(x, 13, a)
    
            x = len(spew)
            for i in range(14):
                spewList.SetStringItem(x, i, '')
     
            x += 1
            spewList.SetStringItem(x, 1, '         '+ self.utility.lang.get('TOTALS'))
    
            spewList.SetStringItem(x, 3, self.utility.speed_format(tot_uprate, truncate = 0))
            spewList.SetStringItem(x, 6, self.utility.speed_format(tot_downrate, truncate = 0))
    
            if statistics is not None:
                spewList.SetStringItem(x, 10, self.utility.size_format(float(statistics.downTotal)))
                spewList.SetStringItem(x, 11, self.utility.size_format(float(statistics.upTotal)))
            else:
                spewList.SetStringItem(x, 10, '')
                spewList.SetStringItem(x, 11, '')
    
            for i in [0, 2, 4, 5, 7, 8, 9, 12, 13]:
                spewList.SetStringItem(x, i, '')
     
            if kickbanlen:
                x += 1
                for i in range(14):
                    spewList.SetStringItem(x, i, '')
     
                for ip in statistics.peers_kicked:
                    x += 1
                    spewList.SetStringItem(x, 1, ip[1])
                    spewList.SetStringItem(x, 3, self.utility.lang.get('KICKED'))
                    for i in [0, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
                        spewList.SetStringItem(x, i, '')
     
                for ip in statistics.peers_banned:
                    x += 1
                    spewList.SetStringItem(x, 1, ip[1])
                    spewList.SetStringItem(x, 3, self.utility.lang.get('BANNED'))
                    for i in [0, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
                        spewList.SetStringItem(x, i, '')
        except wx.PyDeadObjectError:
            pass
  
    def updateInfoWindow(self, statistics):
        infowin = self.torrent.detail_adr
        if infowin is None:
            return
            
        infopanel = infowin.fileInfoPanel

        if (infopanel.fileList is not None
            and statistics is not None
            and (statistics.filelistupdated.isSet()
                 or infopanel.refresh_details)):
            for i in range(len(statistics.filecomplete)):
                if self.torrent.filepriorities[i] == -1:
                    # Not download this file
                    infopanel.fileList.SetStringItem(i, 1, '')
                elif statistics.fileinplace[i]:
                    # File is done
                    infopanel.fileList.SetStringItem(i, 2, self.utility.lang.get('done'))
                elif statistics.filecomplete[i]:
                    # File is at complete, but not done
                    infopanel.fileList.SetStringItem(i, 2, "100%")
                else:
                    # File isn't complete yet
                    frac = statistics.fileamtdone[i]
                    if frac:
                        infopanel.fileList.SetStringItem(i, 2, '%d%%' % (frac*100))
                    else:
                        infopanel.fileList.SetStringItem(i, 2, '')
            infopanel.refresh_details = False
            statistics.filelistupdated.clear()

    def finished(self):        
        self.fin = True
        self.invokeLater(self.onFinishEvent)
        
    def failed(self):
        self.fin = True
        if self.torrent.doneflag is None or self.torrent.doneflag.isSet():
            self.onFailEvent()
        else:
            self.invokeLater(self.onFailEvent)

    def error(self, errormsg):
        try:
            if errormsg[0:29] == "Problem connecting to tracker" or \
               errormsg[0:19] == "rejected by tracker" or \
               errormsg[0:21] == "bad data from tracker":
                currenttime = time()
                if self.lasterrortracker == 0:
                    self.lasterrortracker = currenttime

                if (currenttime - self.lasterrortracker) < 120: #error with in 2 mins
                    self.numerrortracker += 1
                else:
                    self.numerrortracker = 0
                self.lasterrortracker = currenttime
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())   # report exception here too
            pass
        
        self.torrent.changeMessage(errormsg, "error")

        # If failed connecting tracker in parameter 'timeouttracker' mins
        # reduce its priority and force to queue
        ################################################################
        if self.torrent.timeout and self.utility.config.Read('timeouttracker') != "oo":
            try:
                if self.numerrortracker > self.utility.config.Read('timeouttracker', "int"):
                    self.ReducePrioandForceQueue()
            except:
#                data = StringIO()
#                print_exc(file = data)
#                sys.stderr.write(data.getvalue())   # report exception here too
                pass

    def ReducePrioandForceQueue(self):
        currentprio = self.torrent.prio
        if currentprio < 4:      #prio is not lowest
            self.torrent.changePriority(currentprio + 1)     #lower 1 prio

        self.utility.actionhandler.procQUEUE([self.torrent])

    def countSeedingTime(self):
        now = time()
        if self.seedingtimelastcheck is None:
            lastcheck = now
        else:
            lastcheck = self.seedingtimelastcheck
        timelapse = now - lastcheck
        
        self.torrent.seedingtime += timelapse
        
        if self.torrent.getSeedOption('uploadoption') == "1":
            self.torrent.seedingtimeleft = self.torrent.getTargetSeedingTime() - self.torrent.seedingtime
        elif self.torrent.getSeedOption('uploadoption') == "2":
            if self.meanrate['up'] > 0:
                if self.torrent.downsize == 0.0 : 
                    down = self.torrent.floattotalsize
                else:
                    down = self.torrent.downsize
                up = self.torrent.upsize
                ratio = float(self.torrent.getSeedOption('uploadratio'))
                required = ((ratio / 100.0) * down) - up
                newseedingtimeleft = required / self.meanrate['up']
                delta = max(newseedingtimeleft/10, 2)
                if abs(self.torrent.seedingtimeleft - newseedingtimeleft) > delta:
                    # If timer value deviates from theoretical value by more then 10%, reset it to theoretical value
                    self.torrent.seedingtimeleft = newseedingtimeleft
                else:
                    # Keep on timing
                    self.torrent.seedingtimeleft -= timelapse
                if self.torrent.seedingtimeleft < 0.1:
                    self.torrent.seedingtimeleft = 0.1
            else:
                # Set to 366 days (= infinite)
                self.torrent.seedingtimeleft = 999999999999999

        self.seedingtimelastcheck = now

    def TerminateUpload(self):
        # Terminate process
        ####################################################
        # change:   5:Progress  6:BT Status
        # untouch:  4:Title 7:Priority 9:Size 12:%U/DSize
        #           18:DownloadSize 19:UploadSize 21:torretname
        # clear : 8:ETA 10:DLSpeed 11:ULspeed
        #         14:#seed 15:#peer 16:#copie 17:peer avg
        #         20:total speed
        #####################################################
        self.torrent.status['completed'] = True
        self.progress = 100.0
        
        self.torrent.stopABCEngine()
        
        self.queue.updateAndInvoke()

    def onFinishEvent(self):
        # seeding process
        ####################################################
        # change:   5:Progress  6:BT Status
        # untouch:  4:Title 7:Priority 9:Size 12:%U/DSize
        #           18:DownloadSize 19:UploadSize 11:ULspeed
        #           13:Error message
        #           14:#seed 15:#peer 16:#copie 17:peer avg
        #           20:total speed 21:torrentname
        #
        # clear : 8:ETA 10:DLSpeed  
        #         
        #####################################################
        self.btstatus = self.utility.lang.get('completedseeding')
        self.torrent.status['completed'] = True
        self.progress = 100.0
        self.torrent.updateProgress()

        if self.torrent.isDoneUploading():
            self.invokeLater(self.TerminateUpload)
        
        # Update cols 8, 10, 5, 6
        self.torrent.updateColumns([5, 6, 8, 10])
        self.torrent.updateColor()

        self.queue.updateAndInvoke()
            
    def onFailEvent(self):
        if self.utility.config.Read('failbehavior') == '0':
           # Stop      
           self.btstatus = self.utility.lang.get('stop')
           self.utility.actionhandler.procSTOP([self.torrent])
        else:
            # Queue
            self.btstatus = self.utility.lang.get('queue')
            self.utility.actionhandler.procQUEUE([self.torrent])

    def chooseFile(self, default, size, saveas, dir):
        return self.torrent.dest
#        if saveas != '':
#            self.torrent.filename = default
#            self.torrent.float_totalsize = float(size)
#        return saveas
    
#    def newpath(self, path):
#        self.fileDestPath = path
        
    def done(self, event):
        if (self.torrent.doneflag is not None):
            self.torrent.doneflag.set()

        DELEVT_INVOKE(self)