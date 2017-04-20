[general]
family_filter = boolean(default=True)
state_dir = string(default='')
ec_keypair_filename = string(default='')
megacache = boolean(default=True)
videoanalyserpath = string(default='')

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

[trustchain]
enabled = boolean(default=True)
ec_keypair_filename = string(default='')
live_edges_enabled = boolean(default=True)

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

[video_server]
enabled = boolean(default=True)
port = integer(min=-1, max=65536, default=-1)

[upgrader]
enabled = boolean(default=True)

[watch_folder]
enabled = boolean(default=False)
directory = string(default='')

[http_api]
enabled = boolean(default=False)
port = integer(min=-1, max=65536, default=-1)

[credit_mining]
enabled = boolean(default=False)
max_torrents_per_source = integer(default=20)
max_torrents_active = integer(default=50)
source_interval = integer(default=100)
swarm_interval = integer(default=100)
share_mode_target = integer(default=3)
tracker_interval = integer(default=200)
logging_interval = integer(default=60)
# By default we want to automatically boost legal-predetermined channels
boosting_sources = string_list(default=list('http://bt.etree.org/rss/bt_etree_org.rdf'))
boosting_enabled = string_list(default=list('http://bt.etree.org/rss/bt_etree_org.rdf'))
boosting_disabled = string_list(default=list())
archive_sources = string_list(default=list())
policy = string(default=seederratio)
