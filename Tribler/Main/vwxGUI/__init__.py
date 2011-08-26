# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# ReWritten by Niels Zeilemaker
# see LICENSE.txt for license information
import wx
from datetime import datetime

#batch size should be a nice divider of max size
LIST_ITEM_BATCH_SIZE = 5
LIST_ITEM_MAX_SIZE = 250
LIST_RATE_LIMIT = 1

LIST_BLUE = wx.Colour(216,233,240)
LIST_GREY = wx.Colour(230,230,230)
LIST_SELECTED = LIST_BLUE
LIST_DESELECTED = wx.Colour(255,255,255)
LIST_HIGHTLIGHT = wx.Colour(255,255,153)
TRIBLER_RED = wx.Colour(255, 51, 0)

LIST_RADIUS = 7

TORRENT_COLUMNS = ['infohash', 'name', 'length']
CHANNEL_REQ_COLUMNS = ['Torrent.torrent_id', 'infohash', '""', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.channel_id', 'ChannelTorrents.name', 'Torrent.name', 'description', 'time_stamp', 'inserted']
PLAYLIST_REQ_COLUMNS = ['id', 'channel_id', 'name', 'description']

COMMENT_REQ_COLUMNS = ['id', 'dispersy_id', "''", 'channeltorrent_id', 'name', 'Peer.peer_id as peer_id', 'comment', 'time_stamp']
COMMENTPLAY_REQ_COLUMNS = ['id', 'dispersy_id', 'playlist_id', 'channeltorrent_id', 'name', 'Peer.peer_id as peer_id', 'comment', 'time_stamp']
MODIFICATION_REQ_COLUMNS = ['id', 'type_id', 'value', 'inserted']

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