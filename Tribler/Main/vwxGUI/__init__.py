# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# ReWritten by Niels Zeilemaker
# see LICENSE.txt for license information
from time import time, sleep
import wx
import inspect
import sys

from datetime import datetime
from Tribler.Main.Utility.GuiDBHandler import onWorkerThread, startWorker,\
    GUI_PRI_DISPERSY
from Tribler.dispersy.dispersy import Dispersy
from threading import Event

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

CHANNEL_REQ_COLUMNS = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', 'swift_hash', 'swift_torrent_hash', '""', 'torrent_file_name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name', 'ChannelTorrents.description', 'ChannelTorrents.time_stamp', 'ChannelTorrents.inserted']
PLAYLIST_REQ_COLUMNS = ['Playlists.id', 'Playlists.dispersy_id', 'Playlists.channel_id', 'Playlists.name', 'Playlists.description']
LIBRARY_REQ_COLUMNS = CHANNEL_REQ_COLUMNS + ['progress']
TORRENT_REQ_COLUMNS = ['T.torrent_id', 'infohash', 'swift_hash', 'swift_torrent_hash', 'T.name', 'torrent_file_name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'C.id', 'T.dispersy_id', 'C.name', 'T.name', 'C.description', 'C.time_stamp', 'C.inserted']

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

def forceAndReturnWxThread(func):
    def invoke_func(*args,**kwargs):
        if wx.Thread_IsMain():
            return func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO GUITHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            
            event = Event()
            
            result = [None]
            def wx_thread():
                try:
                    result[0] = func(*args, **kwargs)
                finally:
                    event.set()
            
            wx.CallAfter(wx_thread)
            if event.wait(15) or event.isSet():
                return result[0]
            
            from traceback import print_stack
            print_stack()
            print >> sys.stderr, "GOT TIMEOUT ON forceAndReturnWxThread", func.__name__
            
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

_register_task = None
def register_task(*args, **kwargs):
    global _register_task
    if not _register_task:
        # 21/11/11 Boudewijn: there are conditions where the Dispersy instance has not yet been
        # created.  In this case we must wait.
        
        dispersy = Dispersy.has_instance()
        while not dispersy:
            sleep(0.1)
            dispersy = Dispersy.has_instance()
        _register_task = dispersy.callback.register
        
    return _register_task(*args, **kwargs)

def forceDBThread(func):
    def invoke_func(*args,**kwargs):
        if onWorkerThread('dbThread'):
            func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            
            def db_thread():
                func(*args, **kwargs)
            register_task(db_thread)
            
    invoke_func.__name__ = func.__name__
    return invoke_func

def forcePrioDBThread(func):
    def invoke_func(*args,**kwargs):
        if onWorkerThread('dbThread'):
            func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            
            def db_thread():
                func(*args, **kwargs)
            register_task(db_thread, priority = GUI_PRI_DISPERSY)
            
    invoke_func.__name__ = func.__name__
    return invoke_func

def forceAndReturnDBThread(func):
    def invoke_func(*args,**kwargs):
        if onWorkerThread('dbThread'):
            return func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
                print >> sys.stderr, long(time()), "SWITCHING TO DBTHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            
            event = Event()
            
            result = [None]
            def db_thread():
                try:
                    result[0] = func(*args, **kwargs)
                finally:
                    event.set()
            
            #Niels: 10-03-2012, setting prio to 1024 because we are actively waiting for this
            db_thread.__name__ = func.__name__
            register_task(db_thread, priority = GUI_PRI_DISPERSY)
            
            if event.wait(15) or event.isSet():
                return result[0]
            
            from traceback import print_stack
            print_stack()
            print >> sys.stderr, "GOT TIMEOUT ON forceAndReturnDBThread", func.__name__
            
    invoke_func.__name__ = func.__name__
    return invoke_func
