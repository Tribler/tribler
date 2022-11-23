"""
This script scans the input directory and create a Tribler channel based on
torrents found.

For available parameters see "parse_args" function below.

Folder structure:

my channel
├ sub_directory
| ├ file1.torrent
| └ file2.torrent
├ file3.torrent
├ thumbnail.png
└ description.md
"""

import argparse
import logging
import os
from json import dumps
from pathlib import Path
from types import SimpleNamespace

import libtorrent
import sentry_sdk
from pony.orm import db_session

from tribler.core.components import libtorrent
from tribler.core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler.core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.utilities.tiny_tribler_service import TinyTriblerService

_description_file_name = 'description.md'
_thumbnail_file_name = 'thumbnail.png'

_logger = logging.getLogger('Disseminator')

sentry_sdk.init(
    os.environ.get('SENTRY_URL'),
    traces_sample_rate=1.0
)


def parse_args():
    parser = argparse.ArgumentParser(description='Disseminate data by using the Tribler network')

    parser.add_argument('-s', '--source', type=str, help='path to data folder', default='.')
    parser.add_argument('-d', '--tribler_dir', type=str, help='path to data folder', default='./.Tribler')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')
    parser.add_argument('-f', '--fragile', help='Fail at the first error', action='store_true')
    parser.add_argument('-t', '--testnet', help='Testnet run', action='store_true')

    return parser.parse_args()


def setup_logger(verbosity):
    logging_level = logging.DEBUG if verbosity else logging.INFO
    logging.basicConfig(level=logging_level)


class ChannelHelper:
    def __init__(self, community, manager):
        self.community = community
        self.manager = manager
        self.directories = SimpleNamespace(tree={}, directory=None)

    @db_session
    def create_root_channel(self, name, description=''):
        _logger.info(f'Creating channel: {name}')
        channels = self.community.mds.ChannelMetadata

        if len(channels.get_channels_by_title(name)) >= 1:
            _logger.warning(f'Channel with name {name} already exists')
            return False

        self.directories.directory = channels.create_channel(name, description)
        self.flush()

        return True

    @db_session
    def add_torrent(self, file, relative_path):
        _logger.info(f'Add torrent: {file}')

        directory = self.get_directory(relative_path)
        decoded_torrent = libtorrent.bdecode(file.read_bytes())
        directory.add_torrent_to_channel(TorrentDef(metainfo=decoded_torrent), None)

    @db_session
    def add_thumbnail(self, thumbnail):
        if not thumbnail:
            return

        _logger.info(f'Add thumbnail: {thumbnail}')

        root_channel = self.directories.directory
        self.community.mds.ChannelThumbnail(public_key=root_channel.public_key,
                                            origin_id=root_channel.id_,
                                            status=NEW,
                                            binary_data=thumbnail,
                                            data_type='image/png')

    @db_session
    def add_description(self, description):
        if not description:
            return

        _logger.info(f'Add description: {description}')

        root_channel = self.directories.directory
        self.community.mds.ChannelDescription(public_key=root_channel.public_key,
                                              origin_id=root_channel.id_,
                                              json_text=dumps({"description_text": description}),
                                              status=NEW)

    @db_session
    def get_directory(self, path):
        current = self.directories

        for part in path.parts[:-1]:
            next_directory = current.tree.get(part, None)
            if next_directory is not None:
                current = next_directory
                continue

            next_directory = SimpleNamespace(
                tree={},
                directory=self.community.mds.CollectionNode(title=part, origin_id=current.directory.id_, status=NEW)
            )

            current.tree[part] = next_directory
            current = next_directory
            self.flush()

            _logger.info(f'Directory created: {part}')

        return current.directory

    @db_session
    def commit(self):
        _logger.info('Commit changes')

        for t in self.community.mds.CollectionNode.commit_all_channels():
            self.manager.updated_my_channel(TorrentDef.load_from_dict(t))

    @db_session
    def flush(self):
        _logger.debug('Flush')

        self.community.mds.db.flush()


class Service(TinyTriblerService):
    def __init__(self, source_dir, testnet: bool, *args, **kwargs):
        super().__init__(*args, **kwargs,
                         components=[
                             KnowledgeComponent(), MetadataStoreComponent(), KeyComponent(), Ipv8Component(),
                             SocksServersComponent(), LibtorrentComponent(), GigachannelManagerComponent(),
                             GigaChannelComponent()
                         ])
        self.config.general.testnet = testnet
        self.source_dir = Path(source_dir)

    def get_torrents_from_source(self):
        return [(file, file.relative_to(self.source_dir)) for file in self.source_dir.rglob('*.torrent')]

    def get_thumbnail(self):
        f = self.source_dir / _thumbnail_file_name
        return f.read_bytes() if f.exists() else None

    def get_description(self):
        f = self.source_dir / _description_file_name
        return f.read_text() if f.exists() else None

    async def create_channel(self, community, manager):
        channel_helper = ChannelHelper(community, manager)
        channel_name = self.source_dir.name

        if not channel_helper.create_root_channel(channel_name):
            return

        torrents = self.get_torrents_from_source()

        for file, relative_path in torrents:
            channel_helper.add_torrent(file, relative_path)

        channel_helper.add_thumbnail(self.get_thumbnail())
        channel_helper.add_description(self.get_description())

        channel_helper.commit()

        _logger.info(f'{len(torrents)} torrents where added')

    async def on_tribler_started(self):
        await super().on_tribler_started()
        gigachannel_component = self.session.get_instance(GigaChannelComponent)
        gigachannel_manager_component = self.session.get_instance(GigachannelManagerComponent)
        await self.create_channel(gigachannel_component.community,
                                  gigachannel_manager_component.gigachannel_manager)


if __name__ == "__main__":
    _arguments = parse_args()
    print(f"Arguments: {_arguments}")

    setup_logger(_arguments.verbosity)

    service = Service(
        source_dir=Path(_arguments.source),
        state_dir=Path(_arguments.tribler_dir),
        testnet=_arguments.testnet
    )

    service.run(fragile=_arguments.fragile)
