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
from threading import currentThread

from BitTornado.bencode import bencode, bdecode
from BitTornado.zurllib import urlopen
from Tribler.Video.VideoPlayer import is_video_torrent

from ABC.Torrent.abctorrent import ABCTorrent

from Utility.compat import convertOldList
from Utility.constants import * #IGNORE:W0611

DEBUG = False

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
            
        destfile = os.path.join(self.utility.getConfigPath(), "torrent", filename)

        destfileexists = os.access(destfile, os.R_OK)

        if not destfileexists:
            f = open(destfile, "wb")
            f.write(btmetafile)
            f.close()
        
        # Torrent either already existed or should exist now
        dotTorrentDuplicate = True
        
        return self.AddTorrentFromFile(destfile, False, dotTorrentDuplicate, caller = caller)
    
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
            print_exc(file=sys.stderr)

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

        for sourcefile in filelocation:
            # Arno: remember last dir
            self.utility.setLastDir("open",os.path.dirname(sourcefile))
            self.AddTorrentFromFile(sourcefile, forceasklocation)
           
    def AddTorrentFromFile(self, sourcefile, forceasklocation = False, dotTorrentDuplicate = False, caller = "", dest = None, caller_data = None):
        if type(sourcefile) is not unicode:
            sourcefile = unicode(sourcefile, sys.getfilesystemencoding())

        # Check to make sure that the source file exists
        sourcefileexists = os.access(sourcefile, os.R_OK)
        if not sourcefileexists:
            if caller != "web":
                dlg = wx.MessageDialog(None, 
                                       sourcefile + '\n' + self.utility.lang.get('failedtorrentmissing'), 
                                       self.utility.lang.get('error'), 
                                       wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
            # What do we do if the source file doesn't exist?
            # Just return if the source file doesn't exist?
            return "Error=The source file for this torrent doesn't exist"

        metainfo = self.utility.getMetainfo(sourcefile)
        if metainfo is None:
            dlg = wx.MessageDialog(None, 
               sourcefile + '\n' + \
               self.utility.lang.get('failedinvalidtorrent') + '\n' + \
               self.utility.lang.get('error'), 
               wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return "Error=Invalid torrent file"
        
        hexinfohash = sha(bencode(metainfo['info'])).hexdigest()

        # Make directory for torrent copies ($HOME/.Tribler/torrent) if necessary
        self.utility.MakeTorrentDir()
      
        torrentdir = os.path.join(self.utility.getConfigPath(), "torrent")    
        filename     = os.path.split(sourcefile)[1]
        destfile   = os.path.join(torrentdir, filename)
        dontremove = False

        destfileexists = os.access(destfile, os.R_OK)
        
        # If the two files are identical, just point to the
        # .torrent file in the /torrent directory
        sametorrent = self.isSameTorrent(sourcefile, destfile)
        if sametorrent:
            sourcefile = destfile
        
        # Is the torrent already present in the list?
        torrentinlist = self.checkForDuplicateInList(infohash = hexinfohash)
        if torrentinlist:
            if DEBUG:
                print >>sys.stderr,"addtorrents: duplicate torrent"
            if True: # is_video_torrent(metainfo):
                for ABCTorrentTemp in self.utility.torrents["all"]:
                    if hexinfohash == ABCTorrentTemp.infohash:
                        if DEBUG:
                            print >>sys.stderr,"addtorrents: trying to reactivate duplicate torrent",hexinfohash
                        self.activate_deactivate(ABCTorrentTemp,True,False)
                        return "OK"
                return "Error=Torrent already loaded, but could not reactivate torrent"
            else:
                if DEBUG:
                    print >>sys.stderr,"addtorrents: duplicate torrent, but not video",hexinfohash
                self.dupFileInList(sourcefile, caller)
                return "Error=This torrent is duplicate"

        if destfileexists and not dotTorrentDuplicate:
            if caller != "web":
                # ignore if the src and dest files are the same
                # this means that files in the torrent directory
                # will only give a duplicate torrent error if
                # they are already loaded in the list
                # (dotTorrentDuplicate stays False and the check to
                #  see if it's in the list is performed in addNewProc)
                ##############################################
                if (sourcefile == destfile):
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
        if (sourcefile != destfile):
            copy2(sourcefile, destfile)
        return self.addNewProc(destfile, 
                             dest = dest,
                             forceasklocation = forceasklocation, 
                             dotTorrentDuplicate = dotTorrentDuplicate, 
                             dontremove = dontremove, 
                             caller = caller,
                             caller_data = caller_data)


    #
    # Add a torrent to the list
    # Torrents can be added from 3 sources:
    #   from file
    #   from URL
    #   autoadd (command line)
    #
    def addNewProc(self, src, dest = None, forceasklocation = False, dotTorrentDuplicate = False, dontremove = False, caller = "", doupdate = True, caller_data = None, newhexinfohash = None):
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
            elif ABCTorrentTemp.infohash == newhexinfohash:
                # This is an attempt to reactivate the new torrent again, ignore
                # This means the torrent was already in the list when the client was
                # started with the same torrent on the cmd line.
                error = "Activating new torrent twice"
                dontremove = True
                    
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

        if DEBUG:
            print >>sys.stderr,"addtorrents: torrent",`ABCTorrentTemp.metainfo['info']['name']`,"caller is",caller
        self.activate_deactivate(ABCTorrentTemp,doupdate,True,caller!=CALLER_ARGV)
        
        return True, self.utility.lang.get('ok'), ABCTorrentTemp
        

    def activate_deactivate(self,ABCTorrentTemp,doupdate,newtorrent,writetorrentlist=True):
        """ If doupdate == True, then we're recreating old ABCTorrents 
            after startup 
        """
        if doupdate and ABCTorrentTemp is not None:
            
            # Arno: 1. Current policy stop all other torrents, except new one if already exists
            if ABCTorrentTemp.get_on_demand_download():
                # Make a copy here, st*pid &#(*&$(%&$
                copyworkinglist = self.utility.torrents["all"][:]
                # Arno: 2007-01-06: User may have closed VideoLan client and reclicks on URL.
                #if ABCTorrentTemp in copyworkinglist:
                #    copyworkinglist.remove(ABCTorrentTemp)
                self.utility.actionhandler.procSTOP(copyworkinglist)

            if DEBUG:
                print >>sys.stderr,"addtorrents: act/deact: thread is",currentThread().getName()

            # 2. Start torrent if new, reactivate if old
            if newtorrent:
                if DEBUG:
                    print >>sys.stderr,"addtorrents: activating new torrent",ABCTorrentTemp.infohash
                if ABCTorrentTemp.get_on_demand_download():
                    ABCTorrentTemp.set_newly_added()
                ABCTorrentTemp.postInitTasks()
                # If info on disk says that torrent was stopped, it now should be
                if ABCTorrentTemp.status.value != STATUS_QUEUE:
                    if DEBUG:
                        print >>sys.stderr,"addtorrents: changing status of new torrent from STOP to QUEUED"
                    ABCTorrentTemp.status.value = STATUS_QUEUE
                
                if DEBUG:
                    print >>sys.stderr,"addtorrents: post init tasks, inactive is",self.utility.torrents["inactive"][ABCTorrentTemp]
            else:
                if DEBUG:
                    print >>sys.stderr,"addtorrents: activating old torrent",ABCTorrentTemp.infohash
                self.utility.actionhandler.procRESUME([ABCTorrentTemp],skipcheck = True)
                
            if writetorrentlist:
                # Update torrent.list
                ABCTorrentTemp.torrentconfig.writeSrc(False)
                self.utility.torrentconfig.Flush()
                
            self.queue.updateAndInvoke()
        
    #
    # Add a torrent that's already been loaded into the list
    #
    def addOldProc(self, src, newisvideo = False, newhexinfohash = None):       
        # Torrent information
        filename = os.path.join(self.utility.getConfigPath(), "torrent", src)

        if DEBUG:
            print >>sys.stderr,"addtorrents: reviving old torrent",filename
        
        success, error, ABCTorrentTemp = self.addNewProc(filename, dest = None, doupdate = False, newhexinfohash = newhexinfohash)
        
        if not success:
            # Didn't get a valid ABCTorrent object
            if DEBUG:
                print >>sys.stderr,"addtorrents: addOldProc: Failure adding",src,"error",error
            return False
        
        if DEBUG:
            print >>sys.stderr,"addtorrents: addOldProc: succesfully added",ABCTorrentTemp.infohash,"newisvideo",newisvideo

        ABCTorrentTemp.postInitTasks(activate=(not newisvideo))
        
        return True
             
    #
    # Load torrents from the torrent.list file
    #
    def readTorrentList(self, argv):
        
        # See if we have a torrent on the command line, and if so, whether
        # it is a video torrent.
        newisvideo = False
        newhexinfohash = None
        if argv[0] != "":
            metainfo = self.utility.getMetainfo(argv[0])
            if metainfo is not None and True: # is_video_torrent(metainfo):
                # So we're being started with a video torrent 
                newisvideo = True
                newhexinfohash = sha(bencode(metainfo['info'])).hexdigest()
        
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
            #print >>sys.stderr,"Addtorrents: Items(): adding",index,src
            try:
                index = int(index)
                oldprocs.append((index, src))
            except:
                pass
        oldprocs.sort()
        
        for index, src in oldprocs:
            #print >>sys.stderr,"Addtorrents: readTorrentList: adding",index,src
            self.addOldProc(src,newisvideo,newhexinfohash)
            
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
