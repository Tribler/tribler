# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker
# ReWritten by Niels Zeilemaker
# see LICENSE.txt for license information
from time import time
import wx
import inspect
import logging

from datetime import datetime

from threading import Event
from Tribler.Core.CacheDB.sqlitecachedb import TRHEADING_DEBUG

logger = logging.getLogger(__name__)

# batch size should be a nice divider of max size
LIST_ITEM_BATCH_SIZE = 5
LIST_ITEM_MAX_SIZE = 50
LIST_RATE_LIMIT = 1

THUMBNAIL_FILETYPES = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')

DEFAULT_BACKGROUND = wx.Colour(255, 255, 255)
LIST_LIGHTBLUE = wx.Colour(240, 248, 255)
LIST_BLUE = wx.Colour(216, 237, 255)
LIST_DARKBLUE = wx.Colour(191, 226, 255)
LIST_GREY = wx.Colour(240, 240, 240)
LIST_SELECTED = LIST_LIGHTBLUE
LIST_EXPANDED = LIST_BLUE
LIST_DESELECTED = wx.Colour(255, 255, 255)
LIST_HIGHTLIGHT = wx.Colour(255, 255, 153)
LIST_AT_HIGHLIST = wx.Colour(255, 242, 255)

LIST_ORANGE = wx.Colour(255, 209, 126)
LIST_GREEN = wx.Colour(176, 255, 150)

TRIBLER_RED = wx.Colour(255, 51, 0)

SEEDING_COLOUR = wx.Colour(129, 255, 129)
COMPLETED_COLOUR = wx.Colour(129, 255, 129)
DOWNLOADING_COLOUR = wx.Colour(50, 100, 255)
STOPPED_COLOUR = TRIBLER_RED

GRADIENT_LRED = wx.Colour(255, 125, 93)
GRADIENT_DRED = wx.Colour(255, 51, 0)
GRADIENT_LGREY = wx.Colour(254, 254, 254)
GRADIENT_DGREY = wx.Colour(235, 235, 235)
SEPARATOR_GREY = wx.Colour(210, 210, 210)
FILTER_GREY = wx.Colour(240, 240, 240)

LIST_RADIUS = 7
LIST_AUTOSIZEHEADER = -2

CHANNEL_REQ_COLUMNS = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name', 'ChannelTorrents.description', 'ChannelTorrents.time_stamp', 'ChannelTorrents.inserted']
PLAYLIST_REQ_COLUMNS = ['Playlists.id', 'Playlists.dispersy_id', 'Playlists.channel_id', 'Playlists.name', 'Playlists.description']
TORRENT_REQ_COLUMNS = ['T.torrent_id', 'infohash', 'T.name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'C.id', 'T.dispersy_id', 'C.name', 'T.name', 'C.description', 'C.time_stamp', 'C.inserted']
TUMBNAILTORRENT_REQ_COLUMNS = ['torrent_id', 'MetadataMessage.infohash', 'name', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers']

COMMENT_REQ_COLUMNS = ['Comments.id', 'Comments.dispersy_id', 'CommentTorrent.channeltorrent_id', 'name', 'Peer.peer_id', 'comment', 'reply_to_id', 'inserted', 'time_stamp']

MODERATION_REQ_COLUMNS = ['Moderations.id', 'Moderations.channel_id', 'Moderations.peer_id', 'Moderations.by_peer_id', 'Moderations.severity', 'Moderations.message', 'Moderations.time_stamp', 'Moderations.inserted']
MODIFICATION_REQ_COLUMNS = ['ChannelMetaData.id', 'ChannelMetaData.dispersy_id', 'ChannelMetaData.peer_id', 'ChannelMetaData.type_id', 'ChannelMetaData.value', 'ChannelMetaData.time_stamp', 'ChannelMetaData.inserted', 'MetaDataTorrent.channeltorrent_id']
MARKING_REQ_COLUMNS = ['TorrentMarkings.dispersy_id', 'TorrentMarkings.channeltorrent_id', 'TorrentMarkings.peer_id', 'TorrentMarkings.type', 'TorrentMarkings.time_stamp']

tmp = MODERATION_REQ_COLUMNS + MODIFICATION_REQ_COLUMNS
MODIFICATION_REQ_COLUMNS += MODERATION_REQ_COLUMNS
MODERATION_REQ_COLUMNS = tmp

CHANNEL_MAX_NON_FAVORITE = 50

VLC_SUPPORTED_SUBTITLES = ['.cdg', '.idx', '.srt', '.sub', '.utf', '.ass',
                           '.ssa', '.aqt', '.jss', '.psb', '.rt', '.smi']


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
    size = (val / 1048576.0)
    return "%.0f MB" % size


def showError(textCtrl):
    def setColours(ctrl, fore, back):
        ctrl.SetForegroundColour(fore)
        ctrl.SetBackgroundColour(back)
        ctrl.Refresh()

    curFore = textCtrl.GetForegroundColour()
    curBack = textCtrl.GetBackgroundColour()
    setColours(textCtrl, wx.WHITE, wx.RED)
    wx.CallLater(2000, setColours, textCtrl, curFore, curBack)


def warnWxThread(func):
    def invoke_func(*args, **kwargs):
        if not wx.Thread_IsMain():
            caller = inspect.stack()[1]
            callerstr = "%s %s:%s" % (caller[3], caller[1], caller[2])
            logger.warn("%s NOT ON GUITHREAD %s %s:%s called by %s", long(time()),
                        func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

        return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


def forceWxThread(func):
    def invoke_func(*args, **kwargs):
        if wx.Thread_IsMain():
            func(*args, **kwargs)
        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s" % (caller[3], caller[1], caller[2])
                logger.debug("%s SWITCHING TO GUITHREAD %s %s:%s called by %s", long(time()),
                             func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            wx.CallAfter(func, *args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


def forceAndReturnWxThread(func):
    def invoke_func(*args, **kwargs):
        if wx.Thread_IsMain():
            return func(*args, **kwargs)

        else:
            if TRHEADING_DEBUG:
                caller = inspect.stack()[1]
                callerstr = "%s %s:%s" % (caller[3], caller[1], caller[2])
                logger.debug("%s SWITCHING TO GUITHREAD %s %s:%s called by %s", long(time()),
                             func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)

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
            logger.warn("GOT TIMEOUT ON forceAndReturnWxThread %s", func.__name__)

    invoke_func.__name__ = func.__name__
    return invoke_func
