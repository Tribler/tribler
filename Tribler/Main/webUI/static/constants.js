/*
Copyright (c) 2011 BitTorrent, Inc. All rights reserved.

Use of this source code is governed by a BSD-style that can be
found in the LICENSE file.
*/

var CONST = {
	VERSION: "0.380"
	, BUILD: ""

	//----------------------------------------
	// TORRENT DATA CONSTANTS
	//----------------------------------------

	, "TORRENT_HASH": 0
	, "TORRENT_STATUS": 1
	, "TORRENT_NAME": 2
	, "TORRENT_SIZE": 3
	, "TORRENT_PROGRESS": 4
	, "TORRENT_DOWNLOADED": 5
	, "TORRENT_UPLOADED": 6
	, "TORRENT_RATIO": 7
	, "TORRENT_UPSPEED": 8
	, "TORRENT_DOWNSPEED": 9
	, "TORRENT_ETA": 10
	, "TORRENT_LABEL": 11
	, "TORRENT_PEERS_CONNECTED": 12
	, "TORRENT_PEERS_SWARM": 13
	, "TORRENT_SEEDS_CONNECTED": 14
	, "TORRENT_SEEDS_SWARM": 15
	, "TORRENT_AVAILABILITY": 16
	, "TORRENT_QUEUE_POSITION": 17
	, "TORRENT_REMAINING": 18
	, "TORRENT_DOWNLOAD_URL": 19
	, "TORRENT_RSS_FEED_URL": 20
	, "TORRENT_STATUS_MESSAGE": 21
	, "TORRENT_STREAM_ID": 22
	, "TORRENT_DATE_ADDED": 23
	, "TORRENT_DATE_COMPLETED": 24
	, "TORRENT_APP_UPDATE_URL": 25
	, "TORRENT_SAVE_PATH": 26

	//----------------------------------------
	// TORRENT STATUS CONSTANTS
	//----------------------------------------

	, "STATE_STARTED": 1
	, "STATE_CHECKING": 2
	, "STATE_ERROR": 16
	, "STATE_PAUSED": 32
	, "STATE_QUEUED": 64

	//----------------------------------------
	// FILE DATA CONSTANTS
	//----------------------------------------

	, "FILE_NAME": 0
	, "FILE_SIZE": 1
	, "FILE_DOWNLOADED": 2
	, "FILE_PRIORITY": 3
	, "FILE_FIRST_PIECE": 4
	, "FILE_NUM_PIECES": 5
	, "FILE_STREAMABLE": 6
	, "FILE_ENCODED_RATE": 7
	, "FILE_DURATION": 8
	, "FILE_WIDTH": 9
	, "FILE_HEIGHT": 10
	, "FILE_STREAM_ETA": 11
	, "FILE_STREAMABILITY": 12

	//----------------------------------------
	// FILE PRIORITY CONSTANTS
	//----------------------------------------

	, "FILEPRIORITY_SKIP": 0
	, "FILEPRIORITY_LOW": 1
	, "FILEPRIORITY_NORMAL": 2
	, "FILEPRIORITY_HIGH": 3

	//----------------------------------------
	// PEER DATA CONSTANTS
	//----------------------------------------

	, "PEER_COUNTRY": 0
	, "PEER_IP": 1
	, "PEER_REVDNS": 2
	, "PEER_UTP": 3
	, "PEER_PORT": 4
	, "PEER_CLIENT": 5
	, "PEER_FLAGS": 6
	, "PEER_PROGRESS": 7
	, "PEER_DOWNSPEED": 8
	, "PEER_UPSPEED": 9
	, "PEER_REQS_OUT": 10
	, "PEER_REQS_IN": 11
	, "PEER_WAITED": 12
	, "PEER_UPLOADED": 13
	, "PEER_DOWNLOADED": 14
	, "PEER_HASHERR": 15
	, "PEER_PEERDL": 16
	, "PEER_MAXUP": 17
	, "PEER_MAXDOWN": 18
	, "PEER_QUEUED": 19
	, "PEER_INACTIVE": 20
	, "PEER_RELEVANCE": 21

	//----------------------------------------
	// RSS FEED CONSTANTS
	//----------------------------------------

	, "RSSFEED_ID": 0
	, "RSSFEED_ENABLED": 1
	, "RSSFEED_USE_FEED_TITLE": 2
	, "RSSFEED_USER_SELECTED": 3
	, "RSSFEED_PROGRAMMED": 4
	, "RSSFEED_DOWNLOAD_STATE": 5
	, "RSSFEED_URL": 6
	, "RSSFEED_NEXT_UPDATE": 7
	, "RSSFEED_ITEMS": 8

	//----------------------------------------
	// RSS ITEM CONSTANTS
	//----------------------------------------

	, "RSSITEM_NAME": 0
	, "RSSITEM_NAME_FULL": 1
	, "RSSITEM_URL": 2
	, "RSSITEM_QUALITY": 3
	, "RSSITEM_CODEC": 4
	, "RSSITEM_TIMESTAMP": 5
	, "RSSITEM_SEASON": 6
	, "RSSITEM_EPISODE": 7
	, "RSSITEM_EPISODE_TO": 8
	, "RSSITEM_FEED_ID": 9
	, "RSSITEM_REPACK": 10
	, "RSSITEM_IN_HISTORY": 11

	//----------------------------------------
	// RSS ITEM CODEC CONSTANTS
	//----------------------------------------

	, "RSSITEMCODEC_NONE": 0
	, "RSSITEMCODEC_MPEG": 1
	, "RSSITEMCODEC_MPEG2": 2
	, "RSSITEMCODEC_MPEG4": 3
	, "RSSITEMCODEC_REAL": 4
	, "RSSITEMCODEC_WMV": 5
	, "RSSITEMCODEC_XVID": 6
	, "RSSITEMCODEC_DIVX": 7
	, "RSSITEMCODEC_X264": 8
	, "RSSITEMCODEC_H264": 9
	, "RSSITEMCODEC_WMVHD": 10
	, "RSSITEMCODEC_VC1": 11

	, "RSSITEMCODECMAP": [
		  "?"
		, "MPEG"
		, "MPEG-2"
		, "MPEG-4"
		, "Real"
		, "WMV"
		, "Xvid"
		, "DivX"
		, "X264"
		, "H264"
		, "WMV-HD"
		, "VC1"
	]

	//----------------------------------------
	// RSS ITEM QUALITY CONSTANTS
	//----------------------------------------

	, "RSSITEMQUALITY_ALL": -1
	, "RSSITEMQUALITY_NONE": 0
	, "RSSITEMQUALITY_HDTV": 1
	, "RSSITEMQUALITY_TVRIP": 2
	, "RSSITEMQUALITY_DVDRIP": 4
	, "RSSITEMQUALITY_SVCD": 8
	, "RSSITEMQUALITY_DSRIP": 16
	, "RSSITEMQUALITY_DVBRIP": 32
	, "RSSITEMQUALITY_PDTV": 64
	, "RSSITEMQUALITY_HRHDTV": 128
	, "RSSITEMQUALITY_HRPDTV": 256
	, "RSSITEMQUALITY_DVDR": 512
	, "RSSITEMQUALITY_DVDSCR": 1024
	, "RSSITEMQUALITY_720P": 2048
	, "RSSITEMQUALITY_1080I": 4096
	, "RSSITEMQUALITY_1080P": 8192
	, "RSSITEMQUALITY_WEBRIP": 16384
	, "RSSITEMQUALITY_SATRIP": 32768

	, "RSSITEMQUALITYMAP": [
		  "?"
		, "HDTV"
		, "TVRip"
		, "DVDRip"
		, "SVCD"
		, "DSRip"
		, "DVBRip"
		, "PDTV"
		, "HR.HDTV"
		, "HR.PDTV"
		, "DVDR"
		, "DVDScr"
		, "720p"
		, "1080i"
		, "1080p"
		, "WebRip"
		, "SatRip"
	]

	//----------------------------------------
	// RSS FILTER CONSTANTS
	//----------------------------------------

	, "RSSFILTER_ID": 0
	, "RSSFILTER_FLAGS": 1
	, "RSSFILTER_NAME": 2
	, "RSSFILTER_FILTER": 3
	, "RSSFILTER_NOT_FILTER": 4
	, "RSSFILTER_DIRECTORY": 5
	, "RSSFILTER_FEED": 6
	, "RSSFILTER_QUALITY": 7
	, "RSSFILTER_LABEL": 8
	, "RSSFILTER_POSTPONE_MODE": 9
	, "RSSFILTER_LAST_MATCH": 10
	, "RSSFILTER_SMART_EP_FILTER": 11
	, "RSSFILTER_REPACK_EP_FILTER": 12
	, "RSSFILTER_EPISODE_FILTER_STR": 13
	, "RSSFILTER_EPISODE_FILTER": 14
	, "RSSFILTER_RESOLVING_CANDIDATE": 15

	//----------------------------------------
	// RSS FILTER FLAG CONSTANTS
	//----------------------------------------

	, "RSSFILTERFLAG_ENABLE": 1
	, "RSSFILTERFLAG_ORIG_NAME": 2
	, "RSSFILTERFLAG_HIGH_PRIORITY": 4
	, "RSSFILTERFLAG_SMART_EP_FILTER": 8
	, "RSSFILTERFLAG_ADD_STOPPED": 16

	//----------------------------------------
	// SETTING DATA CONSTANTS
	//----------------------------------------
	, "SETTING_NAME": 0
	, "SETTING_TYPE": 1
	, "SETTING_VALUE": 2
	, "SETTING_PARAMS": 3

	//----------------------------------------
	// SETTING TYPE CONSTANTS
	//----------------------------------------
	, "SETTINGTYPE_INTEGER": 0
	, "SETTINGTYPE_BOOLEAN": 1
	, "SETTINGTYPE_STRING": 2

	//----------------------------------------
	// SETTING PARAM CONSTANTS
	//----------------------------------------
	, "SETTINGPARAM_ACCESS_RO": "R"
	, "SETTINGPARAM_ACCESS_RW": "Y"
	, "SETTINGPARAM_ACCESS_WO": "W"

	//----------------------------------------
	// TORRENT DOUBLE-CLICK ACTION CONSTANTS
	//----------------------------------------

	, "TOR_DBLCLK_SHOW_PROPS": 0
	, "TOR_DBLCLK_START_STOP": 1
	, "TOR_DBLCLK_OPEN_FOLDER": 2
	, "TOR_DBLCLK_SHOW_DL_BAR": 3

	//----------------------------------------
	// TORRENT REMOVAL ACTION CONSTANTS
	//----------------------------------------

	, "TOR_REMOVE": 0
	, "TOR_REMOVE_TORRENT": 1
	, "TOR_REMOVE_DATA": 2
	, "TOR_REMOVE_DATATORRENT": 3

	//----------------------------------------
	// BT.TRANSP_DISPOSITION CONSTANTS
	//----------------------------------------

	, "TRANSDISP_UTP": (2 | 8)
	, "TRANSDISP_OUT_TCP": 1
	, "TRANSDISP_OUT_UTP": 2
	, "TRANSDISP_IN_TCP": 4
	, "TRANSDISP_IN_UTP": 8
	, "TRANSDISP_UTP_NEW_HEADER": 16

};
