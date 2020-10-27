[general]
version = string(default='')
log_dir = string(default='logs')
version_checker_enabled = boolean(default=True)

[tunnel_community]
enabled = boolean(default=True)
socks5_listen_ports = string_list(default=list('-1', '-1', '-1', '-1', '-1'))
exitnode_enabled = boolean(default=False)
random_slots = integer(default=5)
competing_slots = integer(default=15)
testnet = boolean(default=False)

[discovery_community]
enabled = boolean(default=True)

[dht]
enabled = boolean(default=True)

[trustchain]
ec_keypair_filename = string(default='ec_multichain.pem')
testnet_keypair_filename = string(default='ec_trustchain_testnet.pem')
testnet = boolean(default=False)

[bandwidth_accounting]
testnet = boolean(default=False)

[bootstrap]
enabled = boolean(default=True)
max_download_rate = integer(min=1, default=1000000)
infohash = string(default='b496932f32daad964e1b63188faabf74d22b45ea')

[chant]
enabled = boolean(default=True)
manager_enabled = boolean(default=True)
channel_edit = boolean(default=False)
channels_dir = string(default='channels')
testnet = boolean(default=False)

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
dht_readiness_timeout = integer(default=30)

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
seeding_mode = option('forever', 'never', 'ratio', 'time', default='forever')
seeding_ratio = float(default=2.0)
seeding_time = float(default=60)
channel_download = boolean(default=False)
add_download_to_channel = boolean(default=False)

[ipv8]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=7759)
address = string(default='0.0.0.0')
bootstrap_override = string(default='')
statistics = boolean(default=False)
walk_interval = float(default=0.5)
walk_scaling_enabled = boolean(default=True)
walk_scaling_upper_limit = float(default=3.0)

[video_server]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[watch_folder]
enabled = boolean(default=False)
directory = string(default='')

[api]
http_enabled = boolean(default=False)
http_port = integer(min=-1, max=65536, default=-1)
https_enabled = boolean(default=False)
https_port = integer(min=-1, max=65536, default=-1)
https_certfile = string(default='')
key = string(default=None)
retry_port = boolean(default=False)

[resource_monitor]
enabled = boolean(default=True)
cpu_priority = integer(min=0, max=5, default=1)
poll_interval = integer(min=1, default=5)
history_size = integer(min=1, default=20)

[popularity_community]
enabled = boolean(default=True)
cache_dir = string(default=health_cache)
