# Written by Arno Bakker 
# see LICENSE.txt for license information
import os

DLSTATUS_ALLOCATING_DISKSPACE = 0 # TODO: make sure this get set when in this alloc mode
DLSTATUS_WAITING4HASHCHECK = 1
DLSTATUS_HASHCHECKING = 2
DLSTATUS_DOWNLOADING = 3
DLSTATUS_SEEDING = 4
DLSTATUS_STOPPED = 5
DLSTATUS_STOPPED_ON_ERROR = 6

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
'DLSTATUS_WAITING4HASHCHECK', 
'DLSTATUS_HASHCHECKING',
'DLSTATUS_DOWNLOADING',
'DLSTATUS_SEEDING',
'DLSTATUS_STOPPED',
'DLSTATUS_STOPPED_ON_ERROR']

UPLOAD = 'up'
DOWNLOAD = 'down'

DLMODE_NORMAL = 0
DLMODE_VOD = 1

PERSISTENTSTATE_CURRENTVERSION = 1

def pathlist2filename(pathlist):
    fullpath = ''
    for elem in pathlist:
        fullpath = os.path.join(fullpath,elem)
    return fullpath
