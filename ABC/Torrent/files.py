import sys
import wx
import os

from cStringIO import StringIO
from threading import Thread,currentThread
from time import sleep
from traceback import print_exc, print_stack
from webbrowser import open_new

from Dialogs.dupfiledialog import DupFileDialog

from Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: TorrentFiles
#
# Keep track of the files associated with a torrent
#
################################################################
class TorrentFiles:
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
              
        self.filename = self.torrent.info['name']
        
        # Array to store file priorities
        # Just using a placeholder of 1 (Normal) for now
        if self.isFile():
            numfiles = 1
        else:
            numfiles = len(self.torrent.info['files'])
        self.filepriorities = [1] * numfiles

        self.floattotalsize = float(self.getSize())
        self.realsize = self.floattotalsize
        
        # This one is to store the download progress ; if it's not stored, the progress
        # of an inactive torrent would stay only in the display of the list, and so it would
        # be lost if the GUI wouldn't display the column "progress". In this case it couldn't
        # be saved in the torrent.lst file.
        self.progress = 0.0
        self.downsize = 0.0
        self.upsize = 0.0
        
        # Progress of individual files within torrent
        self.fileprogress = [""] * numfiles
        
        self.dest = None
        
#        self.skipcheck = False
        
            
    def setupDest(self, dest, forceasklocation, caller):
        self.dest = dest
        
        # Try reading the config file
        if self.dest is None:
            self.dest = self.torrent.torrentconfig.Read("dest")

        # Treat an empty string for dest the same as
        # not having one defined
        if not self.dest:
            self.dest = None

        # For new torrents, get the destination where to save the torrent
        if self.dest is None or forceasklocation:
            self.getDestination(forceasklocation, caller)

        # Treat an empty string for dest the same as
        # not having one defined
        if not self.dest:
            self.dest = None

    def onOpenDest(self, event = None, index = 0):
        return self.onOpenFileDest(index, pathonly = True)

    def onOpenFileDest(self, event = None, index = 0, pathonly = False):
        dest = self.getSingleFileDest(index, pathonly, checkexists = False)
        
        # Check to make sure that what we're trying to get exists
        if dest is None or not os.access(dest, os.R_OK):
            # Error : file not found
            dialog = wx.MessageDialog(None, 
                                      str(dest) + '\n\n' + self.utility.lang.get('filenotfound'), 
                                      self.utility.lang.get('error'), 
                                      wx.ICON_ERROR)
            dialog.ShowModal()
            dialog.Destroy()
            return False
            
        # A file is completed if it either is a single file flagged as completed,
        # or is a file within a multi-file torrent flagged as "Done"
        # (i.e.: file is in-place)
        if self.isFile():
            completed = self.torrent.status.completed
        else:
            completed = (self.fileprogress[index] == self.utility.lang.get('done'))
            
        # Don't need to check if the torrent is complete if we're only
        # opening the path
        if not pathonly and not completed:
            #Display Warning file is not complete yet
            dialog = wx.MessageDialog(None, 
                                      self.torrent.getColumnText(COL_TITLE) + '\n\n'+ self.utility.lang.get('warningopenfile'), 
                                      self.utility.lang.get('warning'), 
                                      wx.YES_NO|wx.ICON_EXCLAMATION)

            result = dialog.ShowModal()
            dialog.Destroy()
            if result != wx.ID_YES:
                return False

        try:
            if pathonly and (sys.platform == 'win32'):
                dest = self.getSingleFileDest(index, pathonly = False, checkexists = False)
                os.popen('explorer.exe /select,"' + dest + '"')
            else:
                Thread(target = open_new(dest)).start()
        except:
            pass
            
        return True
        
    def changeProcDest(self, dest, rentorrent = False):

        self.dest = dest
        self.torrent.updateColumns([COL_DEST])
        self.torrent.torrentconfig.writeBasicInfo()
        
        details = self.torrent.dialogs.details
        if details is not None:
            try:
                details.fileInfoPanel.opendirbtn.SetLabel(self.torrent.files.getProcDest(pathonly = True, checkexists = False))
                details.updateTorrentName()
            except wx.PyDeadObjectError:
                pass
        
        if rentorrent:
            # Update torrent name
            self.torrent.changeTitle(os.path.split(dest)[1])
            
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

        self.changeProcDest(os.path.join(dest, self.filename))
        
        return True
                               
    def moveSingleFile(self, dest):
        if not self.isFile():
            self.moveDir(dest)
            return
        
        filename = os.path.split(self.dest)[1]
        source = os.path.split(self.dest)[0]
        size = int(self.torrent.info['length'])
        
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
                            # Default to "No"
                            result = -1
                            
                            if overwrite == "ask":
                                single = len(filearray) > 1
                                dialog = DupFileDialog(self.torrent, filename, single)
                                result = dialog.ShowModal()
                                dialog.Destroy()
                                if result == 2:
                                    overwrite = "yes"
                                elif result == -2:
                                    overwrite = "no"
                                    
                            if overwrite == "yes" or result > 0:
                                os.remove(newloc)
                            elif overwrite == "no" or result < 0:
                                copyfile = False
                                
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
        
        filearray = {}
        
        movename = os.path.join(dest, self.filename)
        for f in self.torrent.info['files']:
            for item in f['path']:
                size = int(f['length'])
                filearray[item] = size

        self.moveFiles(filearray, destname, movename)

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
                    for x in self.torrent.info['files']:
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
                    
        #TODO: change db
                    
    def getDest(self):
        return self.dest
        
    # Specify where to save the torrent
    def getDestination(self, forceasklocation = False, caller = ""):
        # Set destination location that will be used in next set destination dialog

        # No default directory (or default directory can't be found)
        defaultfolder = self.utility.config.Read('defaultfolder')
        if not os.access(defaultfolder, os.F_OK):
            try:
                os.makedirs(defaultfolder)
            except:
                forceasklocation = True
                
        if ((not self.utility.config.Read('setdefaultfolder', "boolean") or forceasklocation)
            and (caller != "web")):
            success, dest = self.torrent.dialogs.setDestination()
            if not success:
                try:
                    os.remove(dest)
                except:
                    pass
            else:
                if not 'length' in self.torrent.info:     #multi file torrent
                    self.dest = os.path.join(dest, self.filename)
                else:   #1 file for this torrent
                    self.dest = dest
        else:
            self.dest = os.path.join(self.utility.config.Read('defaultfolder'), self.filename)
            
    def getProcDest(self, pathonly = False, checkexists = True):
        # Set it to self.dest (should be fine for files)
        dest = self.dest
        
        # In the case of a multifile torrent, see where we're saving
        if not self.isFile():
            ## see if we're saving to a subdirectory or not
            existing = 0
            if os.path.exists(dest):
                if not os.path.isdir(dest):
                    dest = None
                if os.listdir(dest):  # if it's not empty
                    for x in self.torrent.info['files']:
                        if os.path.exists(os.path.join(dest, x['path'][0])):
                            existing = 1
                    if not existing:
                        dest = os.path.join(dest, self.filename)
        elif pathonly:
            # Strip out just the path for a regular torrent
            dest = os.path.dirname(self.dest)
                        
        if checkexists and dest is not None and not os.access(dest, os.F_OK):
            return None
                        
        return dest
    
    # Used for getting the path for a file in a multi-file torrent
    def getSingleFileDest(self, index = 0, pathonly = False, checkexists = True):
        if self.isFile():
            return self.getProcDest(pathonly, checkexists)
        
        # This isn't a valid file
        if index > len(self.torrent.info['files']):
            return None
            
        fileinfo = self.torrent.info['files'][index]
        dest = self.getProcDest(pathonly = True, checkexists = False)
        for item in fileinfo['path']:
            dest = os.path.join(dest, item)
                        
        if pathonly:
            dest = os.path.dirname(dest)
                   
        if checkexists and dest is not None and not os.access(dest, os.F_OK):
            return None
            
        return dest
        
    def isFile(self):
        return 'length' in self.torrent.info
        
    #
    # Get the total size of all files in the torrent
    #
    # If realsize is True, only return the total size
    # of files that aren't set to "download never"
    #
    def getSize(self, realsize = False):
        if self.isFile():   #1 file for this torrent
            file_length = self.torrent.info['length']
        else:   # Directory torrent
            file_length = 0
            count = 0
            for x in self.torrent.info['files']:
                # If returning the real size, don't include files
                # set to "download never"
                if not realsize or self.filepriorities[count] != -1:
                    file_length += x['length']
                count += 1
        
        return file_length        
        
    def updateRealSize(self):
        self.realsize = self.getSize(realsize = True)
        
        self.torrent.updateColumns([COL_SIZE])
    
    # Set the priorities for all of the files in a multi-file torrent    
    def setFilePriorities(self, priority_array = None):
        if priority_array is not None:
            self.filepriorities = priority_array
            self.torrent.torrentconfig.writeFilePriorities()
            self.updateRealSize()
            self.updateFileProgress()
        
        engine = self.torrent.connection.engine
        if len(self.filepriorities) > 1 and engine is not None and engine.dow is not None:
            engine.dow.fileselector.set_priorities(self.filepriorities)
            
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
        
    def updateProgress(self):

        if currentThread().getName() != "MainThread":
            print "TorrentFiles: updateProgress thread",currentThread()
            print "NOT MAIN THREAD"
            print_stack()
        

        # update the download progress
        if self.torrent.status.isActive():
            engine = self.torrent.connection.engine
            self.downsize = engine.downsize['old'] + engine.downsize['new']
            self.upsize = engine.upsize['old'] + engine.upsize['new']
            
            if self.torrent.status.isActive(checking = False, pause = False):
                self.progress = engine.progress
                
                if self.isFile():
                    details = self.torrent.dialogs.details
                    if details is not None:
                        details.fileInfoPanel.updateColumns([FILEINFO_PROGRESS])
                    
                
    def updateFileProgress(self, statistics = None):
        if self.isFile():
            return
        
        if currentThread().getName() != "MainThread":
            print "TorrentFiles: updateFileProgress thread",currentThread()
            print "NOT MAIN THREAD"
            print_stack()


        # Clear progress for all files that are set to never download
        for i in range(len(self.filepriorities)):
            priority = self.filepriorities[i]
            if priority == -1:
                self.fileprogress[i] = ''
                
        if statistics is not None and statistics.filelistupdated.isSet():
            for i in range(len(statistics.filecomplete)):
                progress = None
                
                if self.filepriorities[i] == -1:
                    # Not download this file
                    progress = ''
                elif statistics.fileinplace[i]:
                    # File is done
                    progress = self.utility.lang.get('done')
                elif statistics.filecomplete[i]:
                    # File is at complete, but not done
                    progress = "100%"
                else:
                    # File isn't complete yet
                    frac = statistics.fileamtdone[i]
                    if frac:
                        progress = '%d%%' % (frac*100)
                    else:
                        progress = ''
                if progress is None:
                    progress = ''
                    
                self.fileprogress[i] = progress
                
            statistics.filelistupdated.clear()
        
        details = self.torrent.dialogs.details
        if details is not None:
            details.fileInfoPanel.updateColumns([FILEINFO_SIZE, FILEINFO_PROGRESS])

    #
    # See how much more space is allocated to this torrent
    #
    def getSpaceAllocated(self):
        allocated = 0L
        if self.isFile():
            if os.path.exists(self.dest):
                allocated = os.path.getsize(self.dest)
        else:
            count = 0
            for f in self.torrent.info['files']:
                # Don't include space taken by disabled files
                if self.filepriorities[count] != -1:
                    filename = self.getProcDest()
                    for item in f['path']:
                        filename = os.path.join(filename, item)
                    if os.path.exists(filename):
                        allocated += os.path.getsize(filename)
                count += 1
                    
        return allocated
    
    #
    # See how much space is needed by this torrent
    #
    def getSpaceNeeded(self, realsize = True):
        # Shouldn't need any more space if the file is complete
        if self.torrent.status.completed:
            return 0L
        
        # See how much space the torrent needs vs. how much is already allocated
        space = self.getSize(realsize = realsize) - self.getSpaceAllocated() 
        if space < 0:
            space = 0L
        return space
        
        