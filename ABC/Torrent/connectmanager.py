import sys
import wx

from time import sleep, time

from Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: TorrentConnections
#
# Keep track of seeding options, upload/download
# Options
#
################################################################        
class TorrentConnections:
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        self.engine = None
        
        self.maxupload = None

        self.maxrate = {}

        # upload rate bandwidth reserved for this torrent
        self.maxrate['up'] = 0.0
        self.maxrate['down'] = 0.0

        self.maxlocalrate = {}

        # Maximum upload rate not to be exceeded, defined in local settings
        self.maxlocalrate['up'] = 0
        self.maxlocalrate['down'] = 0
        
        # What is the current rate set at?
        self.ratesetting = {}
        self.ratesetting['up'] = 0.0
        self.ratesetting['down'] = 0.0
        
        # Snapshot of current rate
        # (taken during each pass through CyclicalTasks)
        self.rate = {}
        self.rate['up'] = 0.0
        self.rate['down'] = 0.0

        self.seedoptions = { 'uploadoption': None, 
                             'uploadtimeh': None, 
                             'uploadtimem': None, 
                             'uploadratio': None }
        
        self.seedingtime = 0
        self.seedingtimeleft = self.getTargetSeedingTime()
        
        self.updynstatus = [0] * 5
        
        self.timeout = True
        
    def changeLocalInfo(self, info):
        # 0 = auto rate
        self.maxlocalrate['up'] = int(info['uploadrate'])
        if self.maxlocalrate['up'] != 0:
            self.maxrate['up'] = float(info['uploadrate'])

        self.maxlocalrate['down'] = int(info['downloadrate'])
        if self.maxlocalrate['down'] != 0:
            self.maxrate['down'] = float(info['downloadrate'])

        self.setMaxUpload(info['maxupload'])

        #active process
        self.setMaxInitiate()

        for param in self.seedoptions:
            self.setSeedOption(param, info[param])
        
        self.timeout = info['timeout']
        
        self.torrent.torrentconfig.writeUploadParams()
        
        # Double-check to see if we're still done uploading
        self.torrent.status.isDoneUploading()
                          
    def superSeed(self):
        # Don't do anything if superseed is already enabled
        if self.torrent.status.value == STATUS_SUPERSEED:
            return
        
        if self.torrent.status.isActive():
            if not self.torrent.status.completed:
                #dialog your file is not completed don't use SUPERSEED
                dlg = wx.MessageDialog(None, self.utility.lang.get('superseederrornotcompleted')  , self.utility.lang.get('error'), wx.ICON_ERROR)
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

                if (self.engine.dow is not None):
                    #Enter super-seed mode
                    self.torrent.status.updateStatus(STATUS_SUPERSEED)
                    # one way change, don't go back
                    self.engine.dow.set_super_seed()
                    # change BTstatus to super-seeding
                    self.torrent.updateColumns([COL_BTSTATUS])
        else:
            #dialogbox running torrent before using super-seed mode
            dlg = wx.MessageDialog(None, self.utility.lang.get('superseedmustruntorrentbefore'), self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            
    def startEngine(self, status = STATUS_ACTIVE):
        self.torrent.status.updateStatus(status)

        self.torrent.updateSingleItemStatus() # BT Status

        self.utility.controller.addDownload(self.torrent)

#    def stopEngine(self, waitForThread = False, update = True):
    def stopEngine(self, update = True):
        if self.torrent.dialogs.details is not None:
            self.torrent.dialogs.details.onStop()

        if self.engine is not None:
            self.engine.shutdown()
#            self.utility.controller.remove(self.torrent)
            
#        # Wait for thread to terminate
#        while waitForThread and self.engine is not None:
#            sleep(0.2)
#
#        self.torrent.makeInactive(update)

    def resetUploadParams(self):
        self.setMaxInitiate()
        
        self.torrent.torrentconfig.writeUploadParams()

        # Double-check to see if we're still done uploading
        self.torrent.status.isDoneUploading()

    def setRate(self, speed = None, dir = "up"):       
        if speed is None:
            speed = self.getLocalRate(dir)
            if speed == 0:
                speed = self.maxrate[dir]
        speed = float(speed)
                
        # Speed is unchanged, shouldn't need to do anything
        if self.ratesetting[dir] == speed:
            return
                
        try:
            if self.engine is not None and self.engine.working:
                if dir == "up":
                    # Set upload rate
                    self.engine.dow.setUploadRate(speed)
                elif not self.torrent.status.completed:
                    # Set download rate
                    # (only makes sense if not complete)
                    self.engine.dow.setDownloadRate(speed)
            self.ratesetting[dir] = speed
        except:
            pass
        
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

    def setMaxInitiate(self):
        if self.torrent.status.isActive():
            self.engine.dow.setConns(self.getMaxUpload())

            max_initiate = self.getMaxInitiate()
            if max_initiate is not None:
                self.engine.dow.setInitiate(max_initiate)
        
    def setMaxUpload(self, value = None):
        if value is None:
            value = self.maxupload
        
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
            
        self.torrent.updateColumns([COL_SEEDOPTION])
        
    def getTargetSeedingTime(self):
        uploadtimeh = self.getSeedOption('uploadtimeh')
        uploadtimem = self.getSeedOption('uploadtimem')
        uploadtimes = (int(uploadtimeh)*3600) + (int(uploadtimem)*60)
            
        return uploadtimes  
        
        
    def reannounce(self, event = None, arg = ""):
        # if torrent is not running.. can't reannounce
        if not self.torrent.status.isActive():
            return

        if (time() - self.engine.reannouncelast > 60):
            self.engine.reannouncelast = time()
            if (self.engine.dow is not None):
                if not arg:
                    self.engine.dow.reannounce()
                else:
                    self.engine.dow.reannounce(arg)
                    
    def getlastexternalannounce(self):
        if not self.torrent.status.isActive():
            return ''
        return self.engine.lastexternalannounce

    def setlastexternalannounce(self, exannounce):
        if not self.torrent.status.isActive():
            return
        self.engine.lastexternalannounce = exannounce
                
    def reannounce_external(self, event = None, parent = None):
        dialog = wx.TextEntryDialog(parent, 
                                    self.utility.lang.get('entertrackerannounceurl'), 
                                    self.utility.lang.get('externalannounce'))

        result = dialog.ShowModal()
        externalurl = dialog.GetValue()
        dialog.Destroy()
        
        if result != wx.ID_OK or not externalurl:
            return
            
        self.setlastexternalannounce(externalurl)
        self.reannounce(arg = "special")