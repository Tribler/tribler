import os

import libtorrent


DANGEROUS_ALERT_CATEGORIES = {libtorrent.alert.category_t.error_notification,
                              libtorrent.alert.category_t.performance_warning}


def bdecode(data):
    return libtorrent.bdecode(data)


def bencode(data):
    libtorrent.bencode(data)


def create_torrent_file(file_path_list, params):
    fs = libtorrent.file_storage()

    # filter all non-files
    file_path_list_filtered = []
    for path in file_path_list:
        if not os.path.exists(path):
            raise IOError('Path does not exist: %s' % path)
        elif os.path.isfile(path):
            file_path_list_filtered.append(path)

    # get the directory where these files are in. If there are multiple files, take the common directory they are in
    if len(file_path_list_filtered) == 1:
        base_path = os.path.split(file_path_list_filtered[0])[0]
    else:
        base_path = os.path.dirname(os.path.commonprefix(file_path_list_filtered))

    # the base_dir directory is the parent directory of the base_path and is passed to the set_piece_hash method
    base_dir = os.path.split(base_path)[0]

    if len(file_path_list_filtered) == 1:
        filename = os.path.basename(file_path_list_filtered[0])
        fs.add_file(filename, os.path.getsize(file_path_list_filtered[0]))
    else:
        for full_file_path in file_path_list_filtered:
            filename = os.path.join(base_path[len(base_dir) + 1:], full_file_path[len(base_dir):])[1:]
            fs.add_file(filename, os.path.getsize(full_file_path))

    if params.get('piece length'):
        piece_size = params['piece length']
    else:
        piece_size = 0

    flags = libtorrent.create_torrent_flags_t.optimize

    # This flag doesn't exist anymore in libtorrent V1.1.0
    if hasattr(libtorrent.create_torrent_flags_t, 'calculate_file_hashes'):
        flags |= libtorrent.create_torrent_flags_t.calculate_file_hashes

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
            torrent.add_tracker(tracker, tier=tier)
            tier += 1
    # DHT nodes
    # http://www.bittorrent.org/beps/bep_0005.html
    if params.get('nodes'):
        for node in params['nodes']:
            torrent.add_node(*node)
    # HTTP seeding
    # http://www.bittorrent.org/beps/bep_0017.html
    if params.get('httpseeds'):
        torrent.add_http_seed(params['httpseeds'])

    # Web seeding
    # http://www.bittorrent.org/beps/bep_0019.html
    if len(file_path_list) == 1:
        if params.get('urllist', False):
            torrent.add_url_seed(params['urllist'])

    # read the files and calculate the hashes
    if len(file_path_list) == 1:
        libtorrent.set_piece_hashes(torrent, base_path)
    else:
        libtorrent.set_piece_hashes(torrent, base_dir)

    t1 = torrent.generate()
    torrent = libtorrent.bencode(t1)

    postfix = u'.torrent'

    if params.get('name'):
        if not isinstance(params['name'], unicode):
            params['name'] = unicode(params['name'], 'utf-8')
        torrent_file_name = os.path.join(base_path, params['name'] + postfix)
    else:
        torrent_file_name = os.path.join(base_path, unicode(t1['info']['name'], 'utf-8') + postfix)
    with open(torrent_file_name, 'wb') as f:
        f.write(torrent)

    return {'success': True,
            'base_path': base_path,
            'base_dir': base_dir,
            'torrent_file_path': torrent_file_name}


def torrent_info(meta_info):
    libtorrent.torrent_info(meta_info)


def default_atp(share_mode):
    atp = {'storage_mode': libtorrent.storage_mode_t.storage_mode_sparse,
           'paused': True,
           'auto_managed': False,
           'duplicate_is_error': True}
    if share_mode:
        atp["flags"] = libtorrent.add_torrent_params_flags_t.flag_share_mode

    return atp
