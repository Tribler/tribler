import sys
import wx
import os

from shutil import copy2
from string import join as stjoin
from urlparse import urlsplit, urlunsplit
from urllib import quote, unquote
from sha import sha
from traceback import print_exc, print_stack
#from cStringIO import StringIO

from BitTornado.bencode import bencode, bdecode
from BitTornado.zurllib import urlopen

from ABC.Torrent.abctorrent import ABCTorrent

from Utility.compat import convertOldList
from Utility.constants import * #IGNORE:W0611

#
# Get a .torrent file from a url
#
def getTorrentFromURL(url):
    # Copy file from web and call addnewproc
    #########################################
    btmetafile = None
    try:
        url_splitted = urlsplit(url)
        h = urlopen(urlunsplit([url_splitted[0], url_splitted[1], quote(unquote(url_splitted[2])), url_splitted[3], url_splitted[4]]))
        
        btmetafile = h.read()
        h.close()
    except:
        try:
            h.close()
        except:
            pass

    return btmetafile


################################################################
#
# Class: AddTorrents
#
# Deal with adding torrents to the list
#
################################################################
class AddTorrents:
    def __init__(self, queue):
        self.queue = queue
        self.utility = queue.utility
                  
    def AddTorrentURL(self, url, caller=""):
        # Strip any leading/trailing spaces from the URL
        url = url.strip()
        
        # Copy file from web and call addnewproc
        #########################################
        btmetafile = getTorrentFromURL(url)
        if btmetafile is None:
            if caller != "web":
                #display error can't connect to server
                dialog = wx.MessageDialog(None, self.utility.lang.get('cantgettorrentfromurl') + ":\n" + url, 
                                      self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return
            return "Error=Can't get torrent from URL"

        # Backup metainfo from URL to local directory
        url_splitted = urlsplit(url)
        filename = os.path.split(stjoin([unquote(url_splitted[2]), url_splitted[3]], ''))[1]
        # If the filename is blank, then don't continue
        if not filename:
            if caller != "web":
                dialog = wx.MessageDialog(None, self.utility.lang.get('failedinvalidtorrent') + ":\n" + url, 
                                      self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return
            else:
                return "Error=Invalid torrent file"
            
        torrentsrc = os.path.join(self.utility.getConfigPath(), "torrent", filename)

        fileexists = os.access(torrentsrc, os.R_OK)

        if not fileexists:
            f = open(torrentsrc, "wb")
            f.write(btmetafile)
            f.close()
        
        # Torrent either already existed or should exist now
        dotTorrentDuplicate = True
        
        return self.AddTorrentFromFile(torrentsrc, False, dotTorrentDuplicate, caller = caller)
    
    def AddTorrentLink(self, event = None):
        starturl = ""
        try:
            # See if there's a url in the clipboard
            # If there is, use that as the default for the dialog
            text = None
            if wx.TheClipboard.Open():
                data = wx.TextDataObject()
                gotdata = wx.TheClipboard.GetData(data)
                wx.TheClipboard.Close()
                if gotdata:
                    text = data.GetText()
            if text is not None:
                if text.startswith("http://") and text.endswith(".torrent"):
                    starturl = text
        
            dialog = wx.TextEntryDialog(None, 
                                        self.utility.lang.get('enterurl'), 
                                        self.utility.lang.get('addtorrenturl_short'),
                                        starturl)

            result = dialog.ShowModal()
            btlink = dialog.GetValue()
            dialog.Destroy()

            if result != wx.ID_OK:
                return

            if btlink != "":
                self.AddTorrentURL(btlink)
        except:
            print_exc()

    def AddTorrentNoneDefault(self, event = None):
        self.AddTorrentFile(event, True)
            
    def AddTorrentFile(self, event = None, forceasklocation = False):
        dialog = wx.FileDialog(None, 
                               self.utility.lang.get('choosetorrentfile'), 
                               self.utility.getLastDir("open"), 
                               '', 
                               self.utility.lang.get('torrentfileswildcard') + ' (*.torrent)|*.torrent', 
                               wx.OPEN|wx.MULTIPLE)
        result = dialog.ShowModal()
        dialog.Destroy()
        if result != wx.ID_OK:
            return
        
        filelocation = dialog.GetPaths()

        for filepath in filelocation:
            # Arno: remember last dir
            self.utility.setLastDir("open",os.path.dirname(filepath))
            self.AddTorrentFromFile(filepath, forceasklocation)
           
    def AddTorrentFromFile(self, filepath, forceasklocation = False, dotTorrentDuplicate = False, caller = "", dest = None, caller_data = None):
        if type(filepath) is not unicode:
            filepath = unicode(filepath, sys.getfilesystemencoding())

        # Check to make sure that the source file exists
        sourcefileexists = os.access(filepath, os.R_OK)
        
        
        if not sourcefileexists:
            if caller != "web":
                dlg = wx.MessageDialog(None, 
                                       filepath + '\n' + self.utility.lang.get('failedtorrentmissing'), 
                                       self.utility.lang.get('error'), 
                                       wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
            # What do we do if the source file doesn't exist?
            # Just return if the source file doesn't exist?
            return "Error=The source file for this torrent doesn't exist"

        # Make torrent directory if necessary
        self.utility.MakeTorrentDir()
      
        torrentpath = os.path.join(self.utility.getConfigPath(), "torrent")    
        filename     = os.path.split(filepath)[1]
        torrentsrc   = os.path.join(torrentpath, filename)
        dontremove = False

        fileexists = os.access(torrentsrc, os.R_OK)
        
        # If the two files are identical, just point to the
        # .torrent file in the /torrent directory
        sametorrent = self.isSameTorrent(filepath, torrentsrc)
        if sametorrent:
            filepath = torrentsrc
        
        # Is the torrent already present in the list?
        torrentinlist = self.checkForDuplicateInList(src = filepath)
        if torrentinlist:
            self.dupFileInList(filepath, caller)
            return "Error=This torrent is duplicate"
        
        if fileexists and not dotTorrentDuplicate:
            if caller != "web":
                # ignore if the src and dest files are the same
                # this means that files in the torrent directory
                # will only give a duplicate torrent error if
                # they are already loaded in the list
                # (dotTorrentDuplicate stays False and the check to
                #  see if it's in the list is performed in addNewProc)
                ##############################################
                if (filepath == torrentsrc):
                    # If addNewProc finds that the torrent is already in the proctab,
                    # we don't want to remove it otherwise the torrent that is running
                    # will be in trouble
                    dontremove = True
                else:
                    # There is a duplicate .torrent file in /torrent
                    dialog = wx.MessageDialog(None, 
                                              self.utility.lang.get('duplicatetorrentmsg'), 
                                              self.utility.lang.get('duplicatetorrent'), 
                                              wx.YES_NO|wx.ICON_EXCLAMATION)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if(result == wx.ID_NO):
                        return "Error=This torrent is duplicate"
                    else:
                        dotTorrentDuplicate = True
            else:
                return "Error=This torrent is duplicate"
        else:
            # Either:
            # dotTorrentDuplicate was False and the file didn't exist (no change)
            # dotTorrentDuplicate was True before when coming from AddTorrentURL (still need to check the list)
            dotTorrentDuplicate = False

        # No need to copy if we're just copying the file onto itself
        if (filepath != torrentsrc):
            copy2(filepath, torrentsrc)
        success, mesg, torrent = self.addNewProc(torrentsrc, 
                                                 dest = dest,
                                                 forceasklocation = forceasklocation, 
                                                 dotTorrentDuplicate = dotTorrentDuplicate, 
                                                 dontremove = dontremove, 
                                                 caller = caller,
                                                 caller_data = caller_data)
        if success:
            return "OK"
        else:
            return "Error=" + mesg


    #
    # Add a torrent to the list
    # Torrents can be added from 3 sources:
    #   from file
    #   from URL
    #   autoadd (command line)
    #
    def addNewProc(self, src, dest = None, forceasklocation = False, dotTorrentDuplicate = False, dontremove = False, caller = "", doupdate = True, caller_data = None):
        #from file, URL maybe down torrent.lst from addProc
        # change at onChooseFile make sure they choose dest
        # dotTorrentDuplicate : To avoid asking the user twice about duplicate (for torrent file name and torrent name)
        #                       True if .torrent is duplicate ; not used if caller==web"

        # Did we succeed in adding the torrent?
        error = None
        ABCTorrentTemp = None
        
        # Check to see the the src file actually exists:
        try:
            os_access = os.access(src, os.R_OK)
        except UnicodeEncodeError:
            src = src.encode(sys.getfilesystemencoding())
            os_access = os.access(src, os.R_OK)
        if not os_access:
            if caller != "web":
                dlg = wx.MessageDialog(None, 
                                       src + '\n' + self.utility.lang.get('failedtorrentmissing'), 
                                       self.utility.lang.get('error'), 
                                       wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
                dontremove = True
            error = ".torrent file doesn't exist or can't be read"
        else:
            ABCTorrentTemp = ABCTorrent(self.queue, src, dest = dest, forceasklocation = forceasklocation, caller = caller, caller_data = caller_data )       
            
            if ABCTorrentTemp.metainfo is None:
                if caller != "web":
                    dlg = wx.MessageDialog(None, 
                                           src + '\n' + \
                                           self.utility.lang.get('failedinvalidtorrent') + '\n' + \
                                           self.utility.lang.get('removetorrent'), 
                                           self.utility.lang.get('error'), 
                                           wx.YES_NO|wx.ICON_ERROR)
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if (result == wx.ID_NO):
                        dontremove = True
                error = "Invalid torrent file"
                    
            # If the torrent doesn't have anywhere to save to, return with an error
            elif ABCTorrentTemp.files.dest is None:
                error = "No destination to save to"
    
            # Search for duplicate torrent name (inside .torrent file) and hash info
            # only if the .torrent is not already a duplicate
            elif not dotTorrentDuplicate:
                torrentInList = self.checkForDuplicateInList(ABCTorrentTemp.infohash, ABCTorrentTemp.src)
                if torrentInList:
                    self.dupFileInList(src, caller)
#                    if caller != "web":
#                        message = src + '\n\n' + self.utility.lang.get('duplicatetorrentinlist')
#                        dlg = wx.MessageDialog(None, 
#                                               message, 
#                                               self.utility.lang.get('duplicatetorrent'), 
#                                               wx.OK|wx.ICON_ERROR)
#                        dlg.ShowModal()
#                        dlg.Destroy()
                    error = "Duplicate torrent"

        # We encountered an error somewhere in the process
        if error is not None:
            # Don't remove if the torrent file is already being used by an existing process
            # Removing will cause problems with the other process
            if not dontremove:
                try:
                    os.remove(src)
                except:
                    pass
            ABCTorrentTemp = None
            return False, error, ABCTorrentTemp
       
        if doupdate and ABCTorrentTemp is not None:
            ABCTorrentTemp.postInitTasks()
            
            # Update torrent.list
            ABCTorrentTemp.torrentconfig.writeSrc(False)
            self.utility.torrentconfig.Flush()
            
            self.queue.updateAndInvoke()
        
        return True, self.utility.lang.get('ok'), ABCTorrentTemp
        
    #
    # Add a torrent that's already been loaded into the list
    #
    def addOldProc(self, src):       
        # Torrent information
        filename = os.path.join(self.utility.getConfigPath(), "torrent", src)
        
        success, error, ABCTorrentTemp = self.addNewProc(filename, dest = None, doupdate = False)
        
        if not success:
            # Didn't get a valid ABCTorrent object
            return False
        
        ABCTorrentTemp.postInitTasks()
        
        return True
             
    #
    # Load torrents from the torrent.list file
    #
    def readTorrentList(self):
        # Convert list in older format if necessary
        convertOldList(self.utility)
        
        numbackups = 3
        
        # Manage backups
        filenames = [ os.path.join(self.utility.getConfigPath(), "torrent.list") ]
        for i in range(1, numbackups + 1):
            filenames.append(filenames[0] + ".backup" + str(i))
            
        for i in range (numbackups, 0, -1):
            if os.access(filenames[i-1], os.R_OK):
                copy2(filenames[i-1], filenames[i])
        
        oldprocs = []
        for index, src in self.utility.torrentconfig.Items():
            try:
                index = int(index)
                oldprocs.append((index, src))
            except:
                pass
        oldprocs.sort()
        
        for index, src in oldprocs:
            self.addOldProc(src)
            
        self.queue.updateAndInvoke()

    #
    # Compare two torrents to see if they are the same
    #
    def isSameTorrent(self, torrent1src, torrent2src):
        # Same location
        if torrent1src == torrent2src:
            return True

        metainfo1 = self.utility.getMetainfo(torrent1src)
        if metainfo1 is None:
            return False
        
        metainfo2 = self.utility.getMetainfo(torrent2src)
        if metainfo2 is None:
            return False
        
        metainfo_hash1 = sha(bencode(metainfo1)).hexdigest()
        metainfo_hash2 = sha(bencode(metainfo2)).hexdigest()
        
        # Hash values for both torrents are the same
        if metainfo_hash1 == metainfo_hash2:
            return True
            
        return False

    #
    # Duplicate file error
    #
    def dupFileInList(self, src, caller = ""):
        if caller != "web":
            message = src + '\n\n' + self.utility.lang.get('duplicatetorrentinlist')
            dlg = wx.MessageDialog(None, 
                                   message, 
                                   self.utility.lang.get('duplicatetorrent'), 
                                   wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    #
    # See if a torrent already in the list has the same infohash
    #
    def checkForDuplicateInList(self, infohash = None, src = None):
        for torrent in self.utility.torrents["all"]:
            if (src is not None and src == torrent.src) or \
               (infohash is not None and infohash == torrent.infohash):
                return True
        return False
