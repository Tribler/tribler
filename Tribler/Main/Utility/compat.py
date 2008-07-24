# Written by ABC authors and Arno Bakker 
# see LICENSE.txt for license information

##########################
#
# Things to handle backward compatability for the old-style
# torrent.lst and abc.ini
#
##########################

import os
import sys

from traceback import print_exc
from cStringIO import StringIO

from shutil import move, copy2

from Tribler.Main.Utility.configreader import ConfigReader
from Tribler.Main.Utility.helpers import existsAndIsReadable

def moveOldConfigFiles(utility):
    oldpath = utility.getPath()
    newpath = utility.getConfigPath()

    files = ["torrent.lst",
             "torrent.list",
             "torrent.list.backup1",
             "torrent.list.backup2",
             "torrent.list.backup3",
             "torrent.list.backup4",
             "abc.ini",
             "abc.conf",
             "webservice.conf",
             "maker.conf",
             "torrent",
             "torrentinfo"]
    
    for name in files:
        oldname = os.path.join(oldpath, name)
        if existsAndIsReadable(oldname):
            newname = os.path.join(newpath, name)
            try:
                move(oldname, newname)
            except:
#                data = StringIO()
#                print_exc(file = data)
#                sys.stderr.write(data.getvalue())
                pass
                
    # Special case: move lang\user.lang to configdir\user.lang
    oldname = os.path.join(oldpath, "lang", "user.lang")
    if existsAndIsReadable(oldname):
        newname = os.path.join(newpath, "user.lang")
        try:
            move(oldname, newname)
        except:
            pass

def convertOldList(utility):
    convertOldList1(utility)
    convertOldList2(utility)

#
# Convert the torrent.lst file to the new torrent.list
# format the first time ABC is run (if necessary)
#
def convertOldList1(utility):
    # Only continue if torrent.lst exists
    filename = os.path.join(utility.getConfigPath(), "torrent.lst")
    if not existsAndIsReadable(filename):
        return
    
    torrentconfig = utility.torrentconfig
    
    # Don't continue unless torrent.list is empty
    try:
        if torrentconfig.has_section("0"):
            return
    except:
        return
    
    oldconfig = open(filename, "r+")
    
    configline = oldconfig.readline()
    index = 0
    while configline != "" and configline != "\n":
        try:
            configmap = configline.split('|')
            
            torrentconfig.setSection(str(index))
            
            torrentconfig.Write("src", configmap[1])
            torrentconfig.Write("dest", configmap[2])

            # Write status information
            torrentconfig.Write("status", configmap[3])
            torrentconfig.Write("prio", configmap[4])

            # Write progress information
            torrentconfig.Write("downsize", configmap[5])
            torrentconfig.Write("upsize", configmap[6])
            if (len(configmap) <= 7) or (configmap[7] == '?\n'):
                progress = "0.0"
            else:
                progress = configmap[7]
            torrentconfig.Write("progress", str(progress))
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())   # report exception here too
            pass

        configline = oldconfig.readline()
        index += 1

    oldconfig.close()
    torrentconfig.Flush()
    
    # Rename the old list file
    move(filename, filename + ".old")
    
#
# Convert list to new format
# (only src stored in list, everything else stored in torrentinfo)
#
def convertOldList2(utility):
    index = 0
    while convertOldList2B(utility, index):
        index += 1
    utility.torrentconfig.Flush()
    
def convertOldList2B(utility, indexval):
    torrentconfig = utility.torrentconfig
    
    index = str(indexval)
    
    try:
        if not torrentconfig.has_section(index):
            return False
    except:
        return False
        
    if indexval == 0:
        # backup the old file
        oldconfigname = os.path.join(utility.getConfigPath(), "torrent.list")
        if existsAndIsReadable(oldconfigname):
            try:
                copy2(oldconfigname, oldconfigname + ".old")
            except:
                pass
    
    # Torrent information
    filename = torrentconfig.Read("src", section = index)
    # Format from earlier 2.7.0 test builds:
    if not filename:
        # If the src is missing, then we should not try to add the torrent
        sys.stdout.write("Filename is empty for index: " + str(index) + "!\n")
        return False
    elif filename.startswith(utility.getPath()):
        src = filename
    else:
        src = os.path.join(utility.getConfigPath(), "torrent", filename)
        
    filename = os.path.split(src)[1]
    newsrc = os.path.join(utility.getConfigPath(), "torrent", filename)
        
    configpath = os.path.join(utility.getConfigPath(), "torrentinfo", filename + ".info")
    config = ConfigReader(configpath, "TorrentInfo")
    
    for name, value in torrentconfig.Items(index):
        if name != "src" and value != "":
            config.Write(name, value)
            
    config.Flush()
    
    torrentconfig.DeleteGroup(index)
    torrentconfig.Write(index, newsrc)
    
    return True
    
# Get settings from the old abc.ini file
def convertINI(utility):
    # Only continue if abc.ini exists
    filename = os.path.join(utility.getConfigPath(), "abc.ini")
    if not existsAndIsReadable(filename):
        return

    config = utility.config
    lang = utility.lang
    
    # We'll ignore anything that was set to the defaults
    # from the previous version
    olddefaults = { 0: [-1, "abc_width", 710], 
                    1: [-1, "abc_height", 400], 
                    2: [-1, "detailwin_width", 610], 
                    3: [-1, "detailwin_height", 500], 
                    4: [0, "Title", 150], 
                    5: [1, "Progress", 60], 
                    6: [2, "BT Status", 100], 
                    7: [8, "Priority", 50], 
                    8: [5, "ETA", 85], 
                    9: [6, "Size", 75], 
                    10: [3, "DL Speed", 65], 
                    11: [4, "UL Speed", 60], 
                    12: [7, "%U/D Size", 65], 
                    13: [9, "Error Message", 200], 
                    14: [-1, "#Connected Seed", 60], 
                    15: [-1, "#Connected Peer", 60], 
                    16: [-1, "#Seeing Copies", 60], 
                    17: [-1, "Peer Avg Progress", 60], 
                    18: [-1, "Download Size", 75], 
                    19: [-1, "Upload Size", 75], 
                    20: [-1, "Total Speed", 80], 
                    21: [-1, "Torrent Name", 150] }
        
    oldconfig = open(filename, "r+")
    
    configline = oldconfig.readline()
    while configline != "" and configline != "\n":
        try:
            configmap = configline.split("|")
            
            colid = int(configmap[0])
            
            # Main window - width
            if colid == 0:
                if not config.Exists("window_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            config.Write("window_width", width)
                    except:
                        pass

            # Main window - height
            elif colid == 1:
                if not config.Exists("window_height"):
                    try:
                        height = int(configmap[3])
                        if height != olddefaults[colid][2]:
                            config.Write("window_height", height)
                    except:
                        pass

            # Advanced details - width
            elif colid == 2:
                if not config.Exists("detailwindow_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            config.Write("detailwindow_width", width)
                    except:
                        pass

            # Advanced details - height
            elif colid == 3:
                if not config.Exists("detailwindow_height"):
                    try:
                        height = int(configmap[3])
                        if height != olddefaults[colid][2]:
                            config.Write("detailwindow_height", height)
                    except:
                        pass

            # Column information
            elif colid >= utility.list.columns.minid and colid < utility.list.columns.maxid:
                # Column RankQ
                if not config.Exists("column" + colid + "_rank"):
                    try:
                        rank = int(configmap[1])
                        if rank != olddefaults[colid][0]:
                            config.Write("column" + colid + "_rank", rank)
                    except:
                        pass

                # Column title
                if not lang.user_lang.Exists("column" + colid + "_text"):
                    try:
                        title = configmap[2]
                        if title != olddefaults[colid][1]:
                            lang.writeUser("column" + colid + "_text", title)
                    except:
                        pass

                # Column width
                if not config.Exists("column" + colid + "_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            config.Write("column" + colid + "_width", width)
                    except:
                        pass
        except:
            pass
        
        configline = oldconfig.readline()
    
    oldconfig.close()

    # Add in code to process things later
        
    lang.flush()
    config.Flush()
    
    # Rename the old ini file
    # (uncomment this out after we actually include something to process things)
    move(filename, filename + ".old")
        