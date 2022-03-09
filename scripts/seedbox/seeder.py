"""
This script generates torrents in input folder and seed them.
For available parameters see "parse_args" function below.

Folder structure:

# my channel
# ├ sub_directory
# | ├ file1
# | └ file2
# ├ sub_directory2
# | ├ file3
# | └ file4
# ├ file5
# └ file6

The script generates torrents for each folder contains files.
There are a possibility to add ignored files (see "_ignore_glob" below).
"""
import argparse
import logging
import os
import time
from collections import defaultdict
from pathlib import Path

import libtorrent

import sentry_sdk

# fmt: off
# flake8: noqa

UNLIMITED = -1

_creator = 'TU Delft'

_dht_routers = [
    ('router.utorrent.com', 6881),
    ("router.utorrent.com", 6881),
    ("router.bittorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("dht.aelitis.com", 6881),
    ("router.bitcomet.com", 6881),
]
_port_range = (6881, 7000)
_log_statistics_interval_in_sec = 10
_add_torrent_delay_in_sec = 1
_ignore_glob = [
    '*DS_Store',
    '*.torrent',
    'thumbnail.png',
    'description.md',
]

_logger = logging.getLogger('Seeder')

sentry_sdk.init(
    os.environ.get('SENTRY_URL'),
    traces_sample_rate=1.0
)


def parse_args():
    parser = argparse.ArgumentParser(description='Seed data by using the LibTorrent protocol')

    parser.add_argument('-s', '--source', type=str, help='path to data folder', default='.')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')

    return parser.parse_args()


def setup_logger(verbosity):
    logging_level = logging.DEBUG if verbosity else logging.INFO
    logging.basicConfig(level=logging_level)


def get_folders_with_files(source):
    """ Return all folders that contains files

    Args:
        source: a source folder

    Returns:
        Dictionary where
            * key: is a folder
            * value: is a file list
    """
    result = {}

    for file in Path(source).rglob('*'):
        ignore = any(file.match(a) for a in _ignore_glob)
        if file.is_file() and not ignore:
            result.setdefault(file.parent, set()).add(file)

    return result


def create_torrents(folders, source):
    _logger.info(f'Creating {len(folders)} torrent files...')

    for folder in folders:
        if folder.match(source):
            continue

        torrent_file = folder.parent / f'{folder.name}.torrent'

        if not torrent_file.exists():
            original, encoded = create_torrent_from_folder(folder, folders[folder])
            torrent_file.write_bytes(encoded)
            _logger.info(f'Created: {torrent_file}')

            yield original, folder
        else:
            _logger.info(f'Skipped (file already exists): {torrent_file}')

            encoded = torrent_file.read_bytes()
            decoded = libtorrent.bdecode(encoded)

            yield decoded, folder


def create_torrent_from_folder(folder, files):
    file_storage = libtorrent.file_storage()
    file_storage.set_name(folder.name)

    for file in files:
        relative = file.relative_to(folder.parent)
        size = file.stat().st_size

        file_storage.add_file(str(relative), size)

    flags = libtorrent.create_torrent_flags_t.optimize
    torrent = libtorrent.create_torrent(file_storage, flags=flags)

    torrent.set_creator(_creator)
    libtorrent.set_piece_hashes(torrent, str(folder.parent))

    torrent_data = torrent.generate()
    return torrent_data, libtorrent.bencode(torrent_data)


def log_all_alerts(session):
    for a in session.pop_alerts():
        if a.category() & libtorrent.alert.category_t.error_notification:
            _logger.error(a)
        else:
            _logger.info(a)


def log_statistics(session, handlers, interval):
    while True:
        time.sleep(interval)
        log_all_alerts(session)

        states = defaultdict(int)
        errors = defaultdict(int)

        for h in handlers:
            status = h.status()
            states[status.state] += 1
            if status.errc.value() != 0:
                errors[status.errc.message()] += 1

        _logger.info(f'Torrents states: {states}')
        if errors:
            _logger.info(f'Torrents errors: {errors}')


def seed(torrents):
    _logger.info(f'Create torrent session in port range: {_port_range}')
    session = libtorrent.session()
    session.listen_on(*_port_range)
    for router in _dht_routers:
        session.add_dht_router(*router)

    session.start_dht()

    session.apply_settings({
        'active_seeds': UNLIMITED,
        'active_limit': UNLIMITED
    })

    handlers = []
    for torrent, folder in torrents:
        torrent_info = libtorrent.torrent_info(torrent)
        params = {
            'save_path': str(folder.parent),
            'ti': torrent_info,
            'name': folder.name,
        }

        _logger.info(f'Add torrent: {params}')
        result = session.add_torrent(params)
        handlers.append(result)

        time.sleep(_add_torrent_delay_in_sec)
        log_all_alerts(session)

    log_statistics(session, handlers, _log_statistics_interval_in_sec)


if __name__ == "__main__":
    _arguments = parse_args()
    print(f"Arguments: {_arguments}")

    setup_logger(_arguments.verbosity)
    _folders = get_folders_with_files(_arguments.source)
    _torrents = list(create_torrents(_folders, _arguments.source))
    seed(_torrents)
