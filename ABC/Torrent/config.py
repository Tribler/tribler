import sys
import os

#from cStringIO import StringIO
#from traceback import print_exc

from Utility.configreader import ConfigReader
from Utility.constants import * #IGNORE:W0611

################################################################
#
# Class: TorrentConfig
#
# Handles reading and writing information about this torrent
# to the torrent.list file.
#
################################################################
class TorrentConfig(ConfigReader):
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        basepath = os.path.join(self.utility.getConfigPath(), "torrentinfo")
        self.filename = os.path.split(self.torrent.src)[1] + ".info"
        configpath = os.path.join(basepath, self.filename)
        ConfigReader.__init__(self, configpath, "TorrentInfo")
        
        self.writeflags = { "src": False, 
                            "basicinfo": False, 
                            "status": False, 
                            "priority": False, 
                            "filepriorities": False, 
                            "fileprogress": False,
                            "progress": False, 
                            "uploadparams": False, 
                            "nameparams": False, 
                            "seedtime": False }
    
    def writeAll(self):
        for key in self.writeflags:
            self.writeflags[key] = True

        self.DeleteGroup()
        
        self.writeSrc(False)
        self.writeBasicInfo(False)
        self.writeStatus(False)
        self.writePriority(False)
        self.writeFilePriorities(False)
        self.writeProgress(False)
        self.writeUploadParams(False)
        self.writeNameParams(False)
        self.writeSeedTime(False)
        self.writeFileProgress(False)
        
        self.Flush()
        
    def writeSrc(self, clearOld = True):
        if clearOld:
            if self.writeflags["src"]:
                return
                
        torrent = self.torrent
        overallchange = False

        # Write torrent information
        filename = os.path.split(torrent.src)[1]
        index = str(self.torrent.listindex)
        change = self.utility.torrentconfig.Write(index, "\"" + filename + "\"")
        if change:
            overallchange = True
        
        if clearOld and overallchange:
            self.utility.torrentconfig.Flush()
        
        self.writeflags["src"] = False
        return overallchange
        
    def writeBasicInfo(self, clearOld = True):
        if clearOld:
            if self.writeflags["basicinfo"]:
                return
        
        torrent = self.torrent
        
        overallchange = False
        
        change = self.Write("dest", torrent.files.dest)
        if change:
            overallchange = True

        if clearOld and overallchange:
            self.Flush()
        
        self.writeflags["basicinfo"] = False
        return overallchange
    
    def writeNameParams(self, clearOld = True):        
        if clearOld:
            if self.writeflags["nameparams"]:
                return
        
        torrent = self.torrent
        overallchange = False
        
        # Write settings for name if available
        title = torrent.title
        if title is not None:
            if title == "":
                title = " "
            change = self.Write("title", title)
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("title")
            if change:
                overallchange = True

        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["nameparams"] = False
        return overallchange

    def writeUploadParams(self, clearOld = True):        
        if clearOld:
            if self.writeflags["uploadparams"]:
                return
        
        torrent = self.torrent
        
        overallchange = False
        
        # Write settings for local upload rate if available
        localmax = torrent.connection.getLocalRate("up")
        if localmax != 0:
            change = self.Write("localmax", localmax)
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("localmax")
            if change:
                overallchange = True

        localmaxdown = torrent.connection.getLocalRate("down")
        if localmaxdown != 0:
            change = self.Write("localmaxdown", localmaxdown)
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("localmaxdown")
            if change:
                overallchange = True

        maxupload = torrent.connection.getMaxUpload(localonly = True)
        if maxupload is not None:
            change = self.Write("maxupload", maxupload)
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("maxupload")
            if change:
                overallchange = True

        for param in torrent.connection.seedoptions:
            value = torrent.connection.getSeedOption(param, localonly = True)
            if value is not None:
                change = self.Write(param, value)
                if change:
                    overallchange = True
            elif clearOld:
                change = self.DeleteEntry(param)
                if change:
                    overallchange = True
                
        if not torrent.connection.timeout:
            change = self.Write("timeout", "0")
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("timeout")
            if change:
                overallchange = True

        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["uploadparams"] = False
        return overallchange
            
    def writeProgress(self, clearOld = True):
        if clearOld:
            if self.writeflags["progress"]:
                return
            
        torrent = self.torrent
        overallchange = False
        
        change = self.Write("downsize", ('%.0f' % torrent.files.downsize))
        if change:
            overallchange = True
        change = self.Write("upsize", ('%.0f' % torrent.files.upsize))
        if change:
            overallchange = True
        change = self.Write("progress", ('%.1f' % torrent.files.progress))
        if change:
            overallchange = True
        
        if clearOld and overallchange:
            self.Flush()
        
        self.writeflags["progress"] = False
        return overallchange
        
    def writeStatus(self, clearOld = True):
        if clearOld:
            if self.writeflags["status"]:
                return

        torrent = self.torrent
        overallchange = False
               
        value = torrent.status.value
        oldvalue = torrent.actions.oldstatus
        if oldvalue is None:
            oldvalue = 0
       
        if (value == STATUS_FINISHED
            or (value == STATUS_HASHCHECK and oldvalue == STATUS_FINISHED)):
            status = 2    # Torrent is finished
        elif value == STATUS_STOP:
            status = 1    # Torrent is stopped
        else:
            status = 0    # Torrent is queued
        
        if status != 0:
            change = self.Write("statusvalue", status)
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("statusvalue")
            if change:
                overallchange = True
            
        if torrent.status.completed:
            change = self.Write("complete", "1")
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("complete")
            if change:
                overallchange = True

        if clearOld and overallchange:
            self.Flush()
        
        self.writeflags["status"] = False
        return overallchange
        
    def writePriority(self, clearOld = True):
        if clearOld:
            if self.writeflags["priority"]:
                return
            
        torrent = self.torrent
        overallchange = False
        
        change = self.Write("prio", torrent.prio)
        if change:
            overallchange = True

        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["priority"] = False
        return overallchange
        
    def writeSeedTime(self, clearOld = True):
        if clearOld:
            if self.writeflags["seedtime"]:
                return
        
        torrent = self.torrent
        overallchange = False
        
        if torrent.connection.seedingtime > 0:
            change = self.Write("seedtime", int(torrent.connection.seedingtime))
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("seedtime")
            if change:
                overallchange = True

        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["seedtime"] = False
        return overallchange
        
    def writeFilePriorities(self, clearOld = True):
        if clearOld:
            if self.writeflags["filepriorities"]:
                return
        
        torrent = self.torrent
        overallchange = False
        
        if not self.torrent.files.isFile():
            notdefault, text = torrent.files.getFilePrioritiesAsString()
            if notdefault:
                change = self.Write("fileprio", text)
                if change:
                    overallchange = True
            elif clearOld:
                change = self.DeleteEntry("fileprio")
                if change:
                    overallchange = True
        elif clearOld:
            change = self.DeleteEntry("fileprio")
            if change:
                overallchange = True
            
        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["filepriorities"] = False
        return overallchange
        
    def writeFileProgress(self, clearOld = True):
        if clearOld:
            if self.writeflags["fileprogress"]:
                return
                
        torrent = self.torrent
        
        overallchange = False
        
        if not torrent.files.isFile():
            change = self.Write("fileprogress", torrent.files.fileprogress, "bencode-list")
            if change:
                overallchange = True
        elif clearOld:
            change = self.DeleteEntry("fileprogress")
            if change:
                overallchange = True
            
        if clearOld and overallchange:
            self.Flush()
            
        self.writeflags["fileprogress"] = False
        return overallchange
            
    def readAll(self):
        torrent = self.torrent
        
        # Download size
        downsize = self.Read("downsize")
        if downsize != "":
            try:
                torrent.files.downsize = float(downsize)
            except:
                pass
        
        # Upload size
        upsize = self.Read("upsize")
        if upsize != "":
            try:
                torrent.files.upsize = float(upsize)
            except:
                pass
        
        # Status
        # Format from earlier 2.7.0 builds:
        status = self.Read("status")
        if status == "completed":
            torrent.status.completed = True
        elif status == "pause":
            torrent.status.value = STATUS_STOP

        status = self.Read("statusvalue")
        if status == "2":
            torrent.status.value = STATUS_FINISHED
        elif status == "1":
            torrent.status.value = STATUS_STOP
            
        complete = self.Read("complete", "boolean")
        if complete:
            torrent.status.completed = True
       
        # Priority
        prio = self.Read("prio")
        if prio != "":
            try:
                torrent.prio = int(prio)
            except:
                pass

        # File priorities
        fileprio = self.Read("fileprio")
        if fileprio != "":
            filepriorities = fileprio.split(",")
            
            # Just in case there's a mismatch in sizes,
            # don't try to get more values than exist
            # in the source or destination arrays
            len1 = len(filepriorities)
            len2 = len(torrent.files.filepriorities)
            rangeEnd = min(len1, len2)
            for i in range(rangeEnd):
                try:
                    torrent.files.filepriorities[i] = int(filepriorities[i])
                except:
                    pass

        # File progress
        fileprogress = self.Read("fileprogress", "bencode-list")
        if fileprogress != []:
            self.torrent.files.fileprogress = fileprogress

        #name
        title = self.Read("title")
        if title != "":
            torrent.title = title
            
        # Progress
        if torrent.status.completed or torrent.status.value == STATUS_FINISHED:
            torrent.files.progress = 100.0
        else:
            progress = self.Read("progress")
            if progress != "":
                try:
                    torrent.files.progress = float(progress)
                except:
                    pass
                
        # Local upload options
        localmax = self.Read("localmax", "int")
        if localmax != 0:
            torrent.connection.maxlocalrate['up'] = localmax

        localmaxdown = self.Read("localmaxdown", "int")
        if localmaxdown != 0:
            torrent.connection.maxlocalrate['down'] = localmaxdown

        maxupload = self.Read("maxupload", "int")
        torrent.connection.setMaxUpload(maxupload)

        for param in torrent.connection.seedoptions:
            value = self.Read(param)
            if value != "":
                torrent.connection.seedoptions[param] = value
                
        timeout = self.Read("timeout")
        if timeout == "0":
            torrent.connection.timeout = False
            
        seedtime = self.Read("seedtime")
        if seedtime != "":
            try:
                torrent.connection.seedingtime = int(seedtime)
                torrent.connection.seedingtimeleft -= torrent.connection.seedingtime
            except:
                pass
                