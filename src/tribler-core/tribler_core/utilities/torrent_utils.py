import logging
from hashlib import sha1

import libtorrent
from libtorrent import bencode

from tribler_core.utilities import path_util

logger = logging.getLogger(__name__)


def commonprefix(paths_list):
    # this unlike the os path .commonprefix version always returns path prefixes as it compares
    # path component wise.
    base_set = set(paths_list[0].parents)
    for p in paths_list[1:]:
        base_set.intersection_update(set(p.parents))

    return sorted(base_set, reverse=True)[0]


def create_torrent_file(file_path_list, params, torrent_filepath=None):
    fs = libtorrent.file_storage()

    # filter all non-files
    file_path_list_filtered = []
    for path in file_path_list:
        path = path_util.Path(path)
        if not path.exists():
            raise IOError('Path does not exist: %s' % path)
        elif path.is_file():
            file_path_list_filtered.append(path)

    # get the directory where these files are in. If there are multiple files, take the common directory they are in
    if len(file_path_list_filtered) == 1:
        base_path = path_util.split(file_path_list_filtered[0])[0]
    else:
        base_path = path_util.abspath(commonprefix(file_path_list_filtered))

    # the base_dir directory is the parent directory of the base_path and is passed to the set_piece_hash method

    if len(file_path_list_filtered) == 1:
        filename = path_util.basename(file_path_list_filtered[0])
        fs.add_file(filename, path_util.getsize(file_path_list_filtered[0]))
    else:
        for full_file_path in file_path_list_filtered:
            #FIXME: there should be a better, cleaner way to define this
            filename = path_util.join(*full_file_path.parts[len(base_path.parent.parts):])
            fs.add_file(str(filename), path_util.getsize(full_file_path))

    if params.get(b'piece length'):
        piece_size = params[b'piece length']
    else:
        piece_size = 0

    flags = libtorrent.create_torrent_flags_t.optimize

    # This flag doesn't exist anymore in libtorrent V1.1.0
    if hasattr(libtorrent.create_torrent_flags_t, 'calculate_file_hashes'):
        flags |= libtorrent.create_torrent_flags_t.calculate_file_hashes

    params = {k: (v.decode('utf-8') if isinstance(v, bytes) else v) for k, v in params.items()}

    torrent = libtorrent.create_torrent(fs, piece_size=piece_size, flags=flags)
    # Python2 wants binary, python3 want unicode
    if params.get(b'comment'):
        torrent.set_comment(params[b'comment'])
    if params.get(b'created by'):
        torrent.set_creator(params[b'created by'])
    # main tracker
    if params.get(b'announce'):
        torrent.add_tracker(params[b'announce'])
    # tracker list
    if params.get(b'announce-list'):
        tier = 1
        for tracker in params[b'announce-list']:
            torrent.add_tracker(tracker, tier=tier)
            tier += 1
    # DHT nodes
    # http://www.bittorrent.org/beps/bep_0005.html
    if params.get(b'nodes'):
        for node in params[b'nodes']:
            torrent.add_node(*node)
    # HTTP seeding
    # http://www.bittorrent.org/beps/bep_0017.html
    if params.get(b'httpseeds'):
        torrent.add_http_seed(params[b'httpseeds'])

    # Web seeding
    # http://www.bittorrent.org/beps/bep_0019.html
    if len(file_path_list) == 1:
        if params.get(b'urllist', False):
            torrent.add_url_seed(params[b'urllist'])

    # read the files and calculate the hashes
    if len(file_path_list) == 1:
        libtorrent.set_piece_hashes(torrent, str(base_path))
    else:
        libtorrent.set_piece_hashes(torrent, str(base_path.parent))

    t1 = torrent.generate()
    torrent = libtorrent.bencode(t1)

    if torrent_filepath:
        with open(torrent_filepath, 'wb') as f:
            f.write(torrent)

    return {
        'success': True,
        'base_path': base_path,
        'base_dir': base_path.parent,
        'torrent_file_path': torrent_filepath,
        'metainfo': torrent,
        'infohash': sha1(bencode(t1[b'info'])).digest()
    }


def get_info_from_handle(handle):
    # In libtorrent 0.16.18, the torrent_handle.torrent_file method is not available.
    # this method checks whether the torrent_file method is available on a given handle.
    # If not, fall back on the deprecated get_torrent_info
    try:
        if hasattr(handle, 'torrent_file'):
            return handle.torrent_file()
        return handle.get_torrent_info()
    except AttributeError as ae:
        logger.warning("No torrent info found from handle: %s", str(ae))
        return None
    except RuntimeError as e:  # This can happen when the torrent handle is invalid.
        logger.warning("Got exception when fetching info from handle: %s", str(e))
        return None
