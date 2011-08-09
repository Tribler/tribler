# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information
import wx

#batch size should be a nice divider of max size
LIST_ITEM_BATCH_SIZE = 4
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
CHANNEL_REQ_COLUMNS = ['CollectedTorrent.torrent_id', 'infohash', '""', 'length', 'category_id', 'status_id', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.channel_id', 'ChannelTorrents.name', 'CollectedTorrent.name', 'description', 'time_stamp', 'inserted']
PLAYLIST_REQ_COLUMNS = ['id', 'channel_id', 'name', 'description']
COMMENT_REQ_COLUMNS = ['id', 'dispersy_id', 'playlist_id', 'channeltorrent_id', 'name', 'Peer.peer_id as peer_id', 'comment', 'time_stamp']
MODIFICATION_REQ_COLUMNS = ['id', 'type_id', 'value']

CHANNEL_MAX_NON_FAVORITE = 50

VLC_SUPPORTED_SUBTITLES = ['.cdg', '.idx', '.srt', '.sub', '.utf', '.ass', '.ssa', '.aqt', '.jss', '.psb', '.rt', '.smi']