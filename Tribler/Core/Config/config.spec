[general]
family_filter = boolean(default=True)
state_dir = string(default='')
ec_keypair_filename = string(default='')
megacache = boolean(default=True)
videoanalyserpath = string(default='')
log_dir = string(default=None)
testnet = boolean(default=False)

[allchannel_community]
enabled = boolean(default=True)

[channel_community]
enabled = boolean(default=True)

[preview_channel_community]
enabled = boolean(default=True)

[search_community]
enabled = boolean(default=True)

[tunnel_community]
enabled = boolean(default=True)
socks5_listen_ports = string_list(default=list('-1', '-1', '-1', '-1', '-1'))
exitnode_enabled = boolean(default=False)

[market_community]
enabled = boolean(default=True)
matchmaker = boolean(default=True)
ec_keypair_filename = string(default='')

[dht]
enabled = boolean(default=True)

[trustchain]
enabled = boolean(default=True)
ec_keypair_filename = string(default='')
testnet_keypair_filename = string(default='')
live_edges_enabled = boolean(default=True)

[wallets]
btc_testnet = boolean(default=False)
dummy_wallets_enabled = boolean(default=False)

[metadata]
enabled = boolean(default=True)
store_dir = string(default=collected_metadata)

[mainline_dht]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[torrent_checking]
enabled = boolean(default=True)

[torrent_store]
enabled = boolean(default=True)
store_dir = string(default=collected_torrents)

[torrent_collecting]
enabled = boolean(default=True)
max_torrents = integer(default=50000)
directory = string(default='')

[libtorrent]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)
proxy_type = integer(min=0, max=5, default=0)
proxy_server = string(default='')
proxy_auth = string(default='')
max_connections_download = integer(default=-1)
max_download_rate = integer(default=0)
max_upload_rate = integer(default=0)
utp = boolean(default=True)
dht = boolean(default=True)

anon_listen_port = integer(min=-1, max=65536, default=-1)
anon_proxy_type = integer(min=0, max=5, default=0)
anon_proxy_server_ip = ip_addr(default=127.0.0.1)
anon_proxy_server_ports = string_list(default=list('-1', '-1', '-1', '-1', '-1'))
anon_proxy_auth = string(default='')

[download_defaults]
anonymity_enabled = boolean(default=True)
number_hops = integer(min=0, max=3, default=1)
safeseeding_enabled = boolean(default=True)
saveas = string(default=None)
seeding_mode = string(default='ratio')
seeding_ratio = float(default=2.0)
seeding_time = float(default=60)

[dispersy]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[ipv8]
enabled = boolean(default=True)
address = string(default='0.0.0.0')
bootstrap_override = string(default='')

[video_server]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[watch_folder]
enabled = boolean(default=False)
directory = string(default='')

[http_api]
enabled = boolean(default=False)
port = integer(min=-1, max=65536, default=-1)

[resource_monitor]
enabled = boolean(default=True)
cpu_priority = integer(min=0, max=5, default=1)
poll_interval = integer(min=1, default=5)
history_size = integer(min=1, default=20)

[credit_mining]
enabled = boolean(default=True)
sources = string_list(default=list())
max_disk_space = integer(min=0, default=53687091200)

[popularity_community]
enabled = boolean(default=True)
cache_dir = string(default=health_cache)
