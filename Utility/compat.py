##########################
#
# Things to handle backward compatability for the old-style
# torrent.lst and abc.ini
#
##########################

import os
import wx
import sys

from shutil import move

# Convert the list to the new format the first time ABC is run
def convertOldList(utility):
    # Only continue if torrent.lst exists
    filename = os.path.join(utility.getPath(), "torrent.lst")
    if not (os.access(filename, os.F_OK) and os.access(filename, os.R_OK)):
        return
    
    torrentconfig = utility.torrentconfig
    
    # Don't continue unless torrent.list is empty
    try:
        if torrentconfig.has_section("0"):
            return
    except:
        return
    
    oldconfig = open("torrent.lst", "r+")
    
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
    
# Get settings from the old abc.ini file
def convertINI(utility):
    # Only continue if abc.ini exists
    filename = os.path.join(utility.getPath(), "abc.ini")
    if not (os.access(filename, os.F_OK) and os.access(filename, os.R_OK)):
        return

    torrentconfig = utility.torrentconfig
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
                if not torrentconfig.Exists("window_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            torrentconfig.Write("window_width", width)
                    except:
                        pass

            # Main window - height
            elif colid == 1:
                if not torrentconfig.Exists("window_height"):
                    try:
                        height = int(configmap[3])
                        if height != olddefaults[colid][2]:
                            torrentconfig.Write("window_height", height)
                    except:
                        pass

            # Advanced details - width
            elif colid == 2:
                if not torrentconfig.Exists("detailwindow_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            torrentconfig.Write("detailwindow_width", width)
                    except:
                        pass

            # Advanced details - height
            elif colid == 3:
                if not torrentconfig.Exists("detailwindow_height"):
                    try:
                        height = int(configmap[3])
                        if height != olddefaults[colid][2]:
                            torrentconfig.Write("detailwindow_height", height)
                    except:
                        pass

            # Column information
            elif colid >= 4 and colid < utility.guiman.maxid:
                # Column RankQ
                if not torrentconfig.Exists("column" + colid + "_rank"):
                    try:
                        rank = int(configmap[1])
                        if rank != olddefaults[colid][0]:
                            torrentconfig.Write("column" + colid + "_rank", rank)
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
                if not torrentconfig.Exists("column" + colid + "_width"):
                    try:
                        width = int(configmap[3])
                        if width != olddefaults[colid][2]:
                            torrentconfig.Write("column" + colid + "_width", width)
                    except:
                        pass
        except:
            pass
        
        configline = oldconfig.readline()
    
    oldconfig.close()

    # Add in code to process things later
        
    lang.flush()
    torrentconfig.Flush()
    
    # Rename the old ini file
    # (uncomment this out after we actually include something to process things)
    move(filename, filename + ".old")
        