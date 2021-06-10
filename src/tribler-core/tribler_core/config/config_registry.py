from tribler_core.utilities.install_dir import get_lib_path

_tribler_core = get_lib_path()

SPECIFICATION_REGISTRY = [
    _tribler_core / 'general.ini',
    _tribler_core / 'modules/tunnel/community/tunnel_community.ini',
    _tribler_core / 'modules/bandwidth_accounting/bandwidth_accounting.ini',
    _tribler_core / 'modules/bootstrap.ini',
    _tribler_core / 'modules/metadata_store/chant.ini',
    _tribler_core / 'modules/torrent_checker/torrent_checking.ini',
    _tribler_core / 'modules/libtorrent/libtorrent.ini',
    _tribler_core / 'modules/ipv8.ini',
    _tribler_core / 'modules/watch_folder.ini',
    _tribler_core / 'restapi/api.ini',
    _tribler_core / 'modules/resource_monitor/resource_monitor.ini',
    _tribler_core / 'modules/popularity/popularity_community.ini',
]

