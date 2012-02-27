# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# ReWritten by Niels Zeilemaker
# see LICENSE.txt for license information
import wx
import inspect
from time import time
import sys

from datetime import datetime
from Tribler.Main.Utility.GuiDBHandler import onWorkerThread, startWorker

#batch size should be a nice divider of max size
LIST_ITEM_BATCH_SIZE = 5
LIST_ITEM_MAX_SIZE = 250
LIST_RATE_LIMIT = 1

DEFAULT_BACKGROUND = wx.Colour(255,255,255)
LIST_BLUE = wx.Colour(216,233,240)
LIST_GREY = wx.Colour(230,230,230)
LIST_SELECTED = LIST_BLUE
LIST_DESELECTED = wx.Colour(255,255,255)
LIST_HIGHTLIGHT = wx.Colour(255,255,153)

LIST_ORANGE = wx.Colour(255,209,126)
LIST_GREEN = wx.Colour(176,255,150)

TRIBLER_RED = wx.Colour(255, 51, 0)

LIST_RADIUS = 7
LIST_AUTOSIZEHEADER = -2

TORRENT_COLUMNS = ['infohash', 'name', 'length']
CHANNEL_REQ_COLUMNS = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name', 'description', 'time_stamp', 'inserted']
PLAYLIST_REQ_COLUMNS = ['Playlists.id', 'Playlists.dispersy_id', 'Playlists.channel_id', 'Playlists.name', 'Playlists.description']

COMMENT_REQ_COLUMNS = ['Comments.id', 'Comments.dispersy_id', 'CommentTorrent.channeltorrent_id', 'name', 'Peer.peer_id', 'comment', 'reply_to_id', 'inserted', 'time_stamp']

MODERATION_REQ_COLUMNS = ['Moderations.id', 'Moderations.channel_id', 'Moderations.peer_id', 'Moderations.by_peer_id', 'Moderations.severity', 'Moderations.message', 'Moderations.time_stamp', 'Moderations.inserted']
MODIFICATION_REQ_COLUMNS = ['ChannelMetaData.id', 'ChannelMetaData.dispersy_id', 'ChannelMetaData.peer_id', 'ChannelMetaData.type_id', 'ChannelMetaData.value', 'ChannelMetaData.time_stamp', 'ChannelMetaData.inserted', 'MetaDataTorrent.channeltorrent_id']
MARKING_REQ_COLUMNS = ['TorrentMarkings.dispersy_id', 'TorrentMarkings.channeltorrent_id', 'TorrentMarkings.peer_id', 'TorrentMarkings.type', 'TorrentMarkings.time_stamp']

tmp = MODERATION_REQ_COLUMNS + MODIFICATION_REQ_COLUMNS
MODIFICATION_REQ_COLUMNS += MODERATION_REQ_COLUMNS
MODERATION_REQ_COLUMNS = tmp

CHANNEL_MAX_NON_FAVORITE = 50

VLC_SUPPORTED_SUBTITLES = ['.cdg', '.idx', '.srt', '.sub', '.utf', '.ass', '.ssa', '.aqt', '.jss', '.psb', '.rt', '.smi']


def format_time(val):
    try:
        today = datetime.today()
        discovered = datetime.fromtimestamp(val)
        
        diff = today - discovered
        if diff.days > 0 or today.day != discovered.day:
            return discovered.strftime('%d-%m-%Y')
        return discovered.strftime('Today %H:%M')
    
    except:
        return 'Unknown'

def format_size(val):
    size = (val/1048576.0)
    return "%.0f MB"%size

TRHEADING_DEBUG = False

def forceWxThread(func):
    def invoke_func(*args,**kwargs):
        if wx.Thread_IsMain():
            func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO GUITHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            wx.CallAfter(func, *args, **kwargs)
            
    invoke_func.__name__ = func.__name__
    return invoke_func

def warnWxThread(func):
    def invoke_func(*args,**kwargs):
        if not wx.Thread_IsMain():
            caller = inspect.stack()[1]
            callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
            print >> sys.stderr, long(time()), "NOT ON GUITHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
        
        return func(*args, **kwargs)
    
    invoke_func.__name__ = func.__name__
    return invoke_func

def forceDBThread(func):
    def invoke_func(*args,**kwargs):
        if onWorkerThread():
            func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            startWorker(None, func, wargs=args, wkwargs=kwargs)
            
    invoke_func.__name__ = func.__name__
    return invoke_func