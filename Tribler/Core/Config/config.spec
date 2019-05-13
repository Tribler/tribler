[general]
log_dir = string(default='logs')
testnet = boolean(default=False)
version_checker_enabled = boolean(default=True)

[tunnel_community]
enabled = boolean(default=True)
socks5_listen_ports = string_list(default=list('-1', '-1', '-1', '-1', '-1'))
exitnode_enabled = boolean(default=False)
random_slots = integer(default=5)
competing_slots = integer(default=15)

[market_community]
enabled = boolean(default=True)
matchmaker = boolean(default=True)
record_transactions = boolean(default=False)

[dht]
enabled = boolean(default=True)

[trustchain]
enabled = boolean(default=True)
ec_keypair_filename = string(default='ec_multichain.pem')
testnet_keypair_filename = string(default='ec_trustchain_testnet.pem')
live_edges_enabled = boolean(default=True)

[bootstrap]
enabled = boolean(default=True)
max_download_rate = integer(min=1, default=1000000)
infohash = string(default='13a25451c761b1482d3e85432f07c4be05ca8a56')

[wallets]
bitcoinlib_enabled = boolean(default=True)
dummy_wallets_enabled = boolean(default=False)

[chant]
enabled = boolean(default=True)
channel_edit = boolean(default=False)
channels_dir = string(default='channels')

[torrent_checking]
enabled = boolean(default=True)

[libtorrent]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)
proxy_type = integer(min=0, max=5, default=0)
proxy_server = string(default=':')
proxy_auth = string(default=':')
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
channel_download = boolean(default=False)

[ipv8]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=7759)
address = string(default='0.0.0.0')
bootstrap_override = string(default='')
statistics = boolean(default=False)

[video_server]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[watch_folder]
enabled = boolean(default=False)
directory = string(default='')

[http_api]
enabled = boolean(default=False)
port = integer(min=-1, max=65536, default=-1)
retry_port = boolean(default=False)

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
