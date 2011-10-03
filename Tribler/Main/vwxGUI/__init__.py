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
LIST_AUTOSIZEHEADER = -2

TORRENT_COLUMNS = ['infohash', 'name', 'length']
CHANNEL_REQ_COLUMNS = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name', 'description', 'time_stamp', 'inserted']
PLAYLIST_REQ_COLUMNS = ['id', 'channel_id', 'name', 'description']

COMMENT_REQ_COLUMNS = ['id', 'Comments.dispersy_id', 'CommentTorrent.channeltorrent_id', 'name', 'Peer.peer_id', 'comment', 'reply_to_id', 'inserted', 'time_stamp']

MODERATION_REQ_COLUMNS = ['Moderations.id', 'Moderations.channel_id', 'Moderations.peer_id', 'Moderations.by_peer_id', 'Moderations.severity', 'Moderations.message', 'Moderations.time_stamp', 'Moderations.inserted']
MODIFICATION_REQ_COLUMNS = ['ChannelMetaData.id', 'ChannelMetaData.dispersy_id', 'ChannelMetaData.peer_id', 'ChannelMetaData.type_id', 'ChannelMetaData.value', 'ChannelMetaData.time_stamp', 'ChannelMetaData.inserted', 'MetaDataTorrent.channeltorrent_id']

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