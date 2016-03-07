import os
import libtorrent


def create_torrent_file(file_path_list, params, callback=None):
    base_dir = None

    num_files = len([file for file in file_path_list if os.path.isfile(file)])
    if num_files > 1:
        # outpaths should start with a common prefix, this prefix is the swarmname of the torrent
        # if srcpaths contain c:\a\1, c:\a\2 -> basepath should be c:\ and basedir a and outpaths should be a\1 and a\2
        # if srcpaths contain c:\a\1, c:\a\2, c:\a\b\1, c:\a\b\2 -> basepath
        # should be c:\ and outpaths should be a\1, a\2, a\b\1 and a\b\2
        base_path = os.path.abspath(os.path.commonprefix(file_path_list))
        base_path, base_dir = os.path.split(base_path)

    else:
        file_path_list = [file for file in file_path_list if os.path.isfile(file)]

        src_path = file_path_list[0]
        base_path, _ = os.path.split(src_path)

    fs = libtorrent.file_storage()
    for f in file_path_list:
        libtorrent.add_files(fs, f)

    if params.get('piece length'):
        piece_size = params['piece length']
    else:
        piece_size = 0

    flags = libtorrent.create_torrent_flags_t.optimize | libtorrent.create_torrent_flags_t.calculate_file_hashes
    torrent = libtorrent.create_torrent(fs, piece_size=piece_size, flags=flags)
    if params.get('comment'):
        torrent.set_comment(params['comment'])
    if params.get('created by'):
        torrent.set_creator(params['created by'])
    # main tracker
    if params.get('announce'):
        torrent.add_tracker(params['announce'])
    # tracker list
    if params.get('announce-list'):
        tier = 1
        for tracker in params['announce-list']:
            torrent.add_tracker(params['announce'], tier=tier)
            tier += 1
    # DHT nodes
    if params.get('nodes'):
        for node in params['nodes']:
            torrent.add_node(*node)
    # HTTP seeding
    if params.get('httpseeds'):
        torrent.add_http_seed(params['httpseeds'])

    if num_files == 1:
        if params.get('urllist', False):
            torrent.add_url_seed(params['urllist'])

    # read the files and calculate the hashes
    libtorrent.set_piece_hashes(torrent, base_path)

    t1 = torrent.generate()
    torrent = libtorrent.bencode(t1)

    postfix = '.torrent'

    torrent_file_name = os.path.join(base_path, t1['info']['name'] + postfix)
    with open(torrent_file_name, 'wb') as f:
        f.write(torrent)

    if callback is not None:
        result = {'success': True,
                  'base_path': base_path,
                  'base_dir': base_dir,
                  'torrent_file_path': torrent_file_name}
        callback(result)


def get_info_from_handle(handle):
    # In libtorrent 0.16.18, the torrent_handle.torrent_file method is not available.
    # this method checks whether the torrent_file method is available on a given handle.
    # If not, fall back on the deprecated get_torrent_info
    if hasattr(handle, 'torrent_file'):
        return handle.torrent_file()
    return handle.get_torrent_info()
