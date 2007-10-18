# Written by Arno Bakker and Bram Cohen 
# see LICENSE.txt for license information

DEFAULTPORT=7762  # Arno: see Utility/configreader.py and Utility/utility.py

DLMODE_NORMAL = 0
DLMODE_VOD = 1

sessdefaults = [
    ('ip', '',
        "ip to report you have to the tracker."),
    ('minport', DEFAULTPORT, 'minimum port to listen on, counts up if unavailable'),
    ('maxport', DEFAULTPORT, 'maximum port to listen on'),
    ('random_port', 1, 'whether to choose randomly inside the port range ' +
        'instead of counting up linearly'),
    ('bind', '', 
        'comma-separated list of ips/hostnames to bind to locally'),
#    ('ipv6_enabled', autodetect_ipv6(),
    ('ipv6_enabled', 0,
         'allow the client to connect to peers via IPv6'),
    ('ipv6_binds_v4', None,
        "set if an IPv6 server socket won't also field IPv4 connections"),
    ('upnp_nat_access', 3,         # If you change this, look at BitTornado/launchmany/UPnPThread
        'attempt to autoconfigure a UPnP router to forward a server port ' +
        '(0 = disabled, 1 = mode 1 [fast,win32], 2 = mode 2 [slow,win32], 3 = mode 3 [any platform])'),
    ('timeout', 300.0,
        'time to wait between closing sockets which nothing has been received on'),
    ('timeout_check_interval', 60.0,
        'time to wait between checking if any connections have timed out'),

# Tribler session opts
    ('eckeypair', None, "keypair to use for session"),
    ('cache', 1,
        "use bsddb to cache peers and preferences"),
    ('overlay', 1,
        "create overlay swarm to transfer special messages"),
    ('buddycast', 1,
        "run buddycast recommendation system"),
    ('start_recommender', 1,
        "buddycast can be temp. disabled via this flag"),
    ('download_help', 1,
        "accept download help request"),
    ('torrent_collecting', 1,
        "automatically collect torrents"),
    ('superpeer', 0,
        "run in super peer mode (0 = disabled)"),
    ('overlay_log', '',
        "log on super peer mode ('' = disabled)"),
    ('buddycast_interval', 15,
        "number of seconds to pause between exchanging preference with a peer in buddycast"),
    ('max_torrents', 5000,
        "max number of torrents to collect"),
    ('max_peers', 2000,
        "max number of peers to use for recommender"),
    ('torrent_collecting_rate', 5,
        "max rate of torrent collecting (Kbps)"),
    ('torrent_checking', 1,
        "automatically check the health of torrents"),
    ('torrent_checking_period', 60, 
        "period for auto torrent checking"),
    ('dialback', 1,
        "use other peers to determine external IP address (0 = disabled)"),
    ('dialback_active', 1,
        "do active discovery (needed to disable for testing only) (0 = disabled)"),
    ('dialback_trust_superpeers', 1,
        "trust superpeer replies (needed to disable for testing only) (0 = disabled)"),
    ('dialback_interval', 30,
        "number of seconds to wait for consensus"),
    ('socnet', 1,
        "enable social networking (0 = disabled)"),
    ('rquery', 1,
        "enable remote query (0 = disabled)"),
    ('stop_collecting_threshold', 200,
        "stop collecting more torrents if the disk has less than this size (MB)"),
    ('internaltracker', 1,
        "enable internal tracker (0 = disabled)"),
    ('nickname', '__default_name__',
        'the nickname you want to show to others'),
    ('videoplayerpath', None, 'Path to video analyser (FFMPEG, found automatically if in PATH)')]

trackerdefaults = [
    ('tracker_dfile', None, 'file to store recent downloader info in'),
    ('tracker_dfile_format', 'bencode', 'format of dfile: either "bencode" (default) or pickle (needed when unicode filenames in state)'),
    ('tracker_socket_timeout', 15, 'timeout for closing connections'),
    ('tracker_save_dfile_interval', 5 * 60, 'seconds between saving dfile'),
    ('tracker_timeout_downloaders_interval', 45 * 60, 'seconds between expiring downloaders'),
    ('tracker_reannounce_interval', 30 * 60, 'seconds downloaders should wait between reannouncements'),
    ('tracker_response_size', 50, 'number of peers to send in an info message'),
    ('tracker_timeout_check_interval', 5,
        'time to wait between checking if any connections have timed out'),
    ('tracker_nat_check', 3,
        "how many times to check if a downloader is behind a NAT (0 = don't check)"),
    ('tracker_log_nat_checks', 0,
        "whether to add entries to the log for nat-check results"),
    ('tracker_min_time_between_log_flushes', 3.0,
        'minimum time it must have been since the last flush to do another one'),
    ('tracker_min_time_between_cache_refreshes', 600.0,
        'minimum time in seconds before a cache is considered stale and is flushed'),
    ('tracker_allowed_dir', '', 'only allow downloads for .torrents in this dir'),
    ('tracker_allowed_list', '', 'only allow downloads for hashes in this list (hex format, one per line)'),
    ('tracker_allowed_controls', 0, 'allow special keys in torrents in the allowed_dir to affect tracker access'),
    ('tracker_multitracker_enabled', 0, 'whether to enable multitracker operation'),
    ('tracker_multitracker_allowed', 'autodetect', 'whether to allow incoming tracker announces (can be none, autodetect or all)'),
    ('tracker_multitracker_reannounce_interval', 2 * 60, 'seconds between outgoing tracker announces'),
    ('tracker_multitracker_maxpeers', 20, 'number of peers to get in a tracker announce'),
    ('tracker_aggregate_forward', '', 'format: <url>[,<password>] - if set, forwards all non-multitracker to this url with this optional password'),
    ('tracker_aggregator', '0', 'whether to act as a data aggregator rather than a tracker.  If enabled, may be 1, or <password>; ' +
             'if password is set, then an incoming password is required for access'),
    ('tracker_hupmonitor', 0, 'whether to reopen the log file upon receipt of HUP signal'),
    ('tracker_http_timeout', 60, 
        'number of seconds to wait before assuming that an http connection has timed out'),
    ('tracker_parse_dir_interval', 60, 'seconds between reloading of allowed_dir or allowed_file ' +
             'and allowed_ips and banned_ips lists'),
    ('tracker_show_infopage', 1, "whether to display an info page when the tracker's root dir is loaded"),
    ('tracker_infopage_redirect', '', 'a URL to redirect the info page to'),
    ('tracker_show_names', 1, 'whether to display names from allowed dir'),
    ('tracker_favicon', '', 'file containing x-icon data to return when browser requests favicon.ico'),
    ('tracker_allowed_ips', '', 'only allow connections from IPs specified in the given file; '+
             'file contains subnet data in the format: aa.bb.cc.dd/len'),
    ('tracker_banned_ips', '', "don't allow connections from IPs specified in the given file; "+
             'file contains IP range data in the format: xxx:xxx:ip1-ip2'),
    ('tracker_only_local_override_ip', 2, "ignore the ip GET parameter from machines which aren't on local network IPs " +
             "(0 = never, 1 = always, 2 = ignore if NAT checking is not enabled)"),
    ('tracker_logfile', '', 'file to write the tracker logs, use - for stdout (default)'),
    ('tracker_allow_get', 1, 'use with allowed_dir; adds a /file?hash={hash} url that allows users to download the torrent file'),
    ('tracker_keep_dead', 0, 'keep dead torrents after they expire (so they still show up on your /scrape and web page)'),
    ('tracker_scrape_allowed', 'full', 'scrape access allowed (can be none, specific or full)')
  ]

sessdefaults = sessdefaults + trackerdefaults


# BT per download opts
dldefaults = [
    ('max_uploads', 7,
        "the maximum number of uploads to allow at once."),
    ('keepalive_interval', 120.0,
        'number of seconds to pause between sending keepalives'),
    ('download_slice_size', 2 ** 14,
        "How many bytes to query for per request."),
    ('upload_unit_size', 1460,
        "when limiting upload rate, how many bytes to send at a time"),
    ('request_backlog', 10,
        "maximum number of requests to keep in a single pipe at once."),
    ('max_message_length', 2 ** 23,
        "maximum length prefix encoding you'll accept over the wire - larger values get the connection dropped."),
    ('responsefile', '',
        'file the server response was stored in, alternative to url'),
    ('url', '',
        'url to get file from, alternative to responsefile'),
    ('selector_enabled', 1,
        'whether to enable the file selector and fast resume function'),
    ('expire_cache_data', 10,
        'the number of days after which you wish to expire old cache data ' +
        '(0 = disabled)'),
    ('priority', '',
        'a list of file priorities separated by commas, must be one per file, ' +
        '0 = highest, 1 = normal, 2 = lowest, -1 = download disabled'),
    ('saveas', '',
        'local file name to save the file as, null indicates query user'),
    ('max_slice_length', 2 ** 17,
        "maximum length slice to send to peers, larger requests are ignored"),
    ('max_rate_period', 20.0,
        "maximum amount of time to guess the current rate estimate represents"),
    ('upload_rate_fudge', 5.0, 
        'time equivalent of writing to kernel-level TCP buffer, for rate adjustment'),
    ('tcp_ack_fudge', 0.03,
        'how much TCP ACK download overhead to add to upload rate calculations ' +
        '(0 = disabled)'),
    ('rerequest_interval', 5 * 60,
        'time to wait between requesting more peers'),
    ('min_peers', 20, 
        'minimum number of peers to not do rerequesting'),
    ('http_timeout', 60, 
        'number of seconds to wait before assuming that an http connection has timed out'),
    ('max_initiate', 40,
        'number of peers at which to stop initiating new connections'),
    ('check_hashes', 1,
        'whether to check hashes on disk'),
    ('max_upload_rate', 0,
        'maximum kB/s to upload at (0 = no limit, -1 = automatic)'),
    ('max_download_rate', 0,
        'maximum kB/s to download at (0 = no limit)'),
    ('alloc_type', 'normal',
        'allocation type (may be normal, background, pre-allocate or sparse)'),
    ('alloc_rate', 2.0,
        'rate (in MiB/s) to allocate space at using background allocation'),
    ('buffer_reads', 1,
        'whether to buffer disk reads'),
    ('write_buffer_size', 4,
        'the maximum amount of space to use for buffering disk writes ' +
        '(in megabytes, 0 = disabled)'),
    ('breakup_seed_bitfield', 1,
        'sends an incomplete bitfield and then fills with have messages, '
        'in order to get around stupid ISP manipulation'),
    ('snub_time', 30.0,
        "seconds to wait for data to come in over a connection before assuming it's semi-permanently choked"),
    ('spew', 0,
        "whether to display diagnostic info to stdout"),
    ('rarest_first_cutoff', 2,
        "number of downloads at which to switch from random to rarest first"),
    ('rarest_first_priority_cutoff', 5,
        'the number of peers which need to have a piece before other partials take priority over rarest first'),
    ('min_uploads', 4,
        "the number of uploads to fill out to with extra optimistic unchokes"),
    ('max_files_open', 50,
        'the maximum number of files to keep open at a time, 0 means no limit'),
    ('round_robin_period', 30,
        "the number of seconds between the client's switching upload targets"),
    ('super_seeder', 0,
        "whether to use special upload-efficiency-maximizing routines (only for dedicated seeds)"),
    ('security', 1,
        "whether to enable extra security features intended to prevent abuse"),
    ('max_connections', 0,
        "the absolute maximum number of peers to connect with (0 = no limit)"),
    ('auto_kick', 1,
        "whether to allow the client to automatically kick/ban peers that send bad data"),
    ('double_check', 1,
        "whether to double-check data being written to the disk for errors (may increase CPU load)"),
    ('triple_check', 0,
        "whether to thoroughly check data being written to the disk (may slow disk access)"),
    ('lock_files', 1,
        "whether to lock files the client is working with"),
    ('lock_while_reading', 0,
        "whether to lock access to files being read"),
    ('auto_flush', 0,
        "minutes between automatic flushes to disk (0 = disabled)"),
#
# Tribler per-download opts
#
    ('role', '', # 'helper', 'coordinator' # MARKED FOR DELETION
        "role of the peer in the download"),
    ('helpers_file', '',  # MARKED FOR DELETION
        "file with the list of friends"),
    ('coordinator_permid', '', # MARKED FOR DELETION
        "PermID of the cooperative download coordinator"),
    ('exclude_ips', '', # MARKED FOR DELETION
        "list of IP addresse to be excluded; comma separated"),
    ('mode', DLMODE_NORMAL,
        "0 = normal download, 1 = download in video-on-demand mode"),
    ('vod_usercallback', None, "callback func for video on demand, first arg is a stream object"),
    ('selected_files',[], "files in torrent to download"),
    ('ut_pex_max_addrs_from_peer', 16,
            "maximum number of addresses to accept from peer (0 = disabled PEX)")]


tdefdictdefaults = [ 
    ('comment', '', "comment field"),
    ('created by', '', "created by field"),
    ('announce', '', "default tracker"),
    ('announce-list', '', "default announce list"), 
    ('httpseeds', '',  "default httpseeds") ]

tdefmetadefaults = [
    ('piece_size', 0, "piece size as int (0 = automatic)"), 
    ('makehash_md5', 0, "add end-to-end MD5 checksum"), 
    ('makehash_crc32', 0, "add end-to-end CRC32 checksum"), 
    ('makehash_sha1', 0, "add end-to-end SHA1 checksum"), 
    ('createmerkletorrent', 1, "create a Merkle torrent (.tribe, Tribler only)"),
    ('createtorrentsig', 0, "whether to add a signature to the torrent"),
    ('torrentsigkeypair', None, "keypair for signature"),
    ('thumb', None, "image for video torrents, format: 171x96 JPEG")
    ]

tdefdefaults = tdefdictdefaults + tdefmetadefaults

