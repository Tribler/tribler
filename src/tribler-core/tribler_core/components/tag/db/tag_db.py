import datetime
import logging
from enum import IntEnum
from typing import List, Optional

from pony import orm


class Operation(IntEnum):
    ADD = 1
    REMOVE = 2


class TagDatabase:
    def __init__(self, filename: Optional[str] = None):
        self.instance = orm.Database()
        self.define_binding(self.instance)
        self.instance.bind('sqlite', filename or ':memory:', create_db=True)
        self.instance.generate_mapping(create_tables=True)
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def define_binding(db):
        class Peer(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            public_key = orm.Required(bytes, unique=True)
            added_at = orm.Optional(datetime.datetime, default=datetime.datetime.utcnow)
            operations = orm.Set(lambda: TorrentTagOp)
            last_time = orm.Required(int, default=0)

        class Torrent(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            infohash = orm.Required(bytes, unique=True)
            tags = orm.Set(lambda: TorrentTag)

        class TorrentTag(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            torrent = orm.Required(lambda: Torrent)
            tag = orm.Required(lambda: Tag)
            operations = orm.Set(lambda: TorrentTagOp)

            added_count = orm.Required(int, default=0)
            removed_count = orm.Required(int, default=0)

            local_operation = orm.Optional(int)  # in case user don't (or do) want to see it locally

            orm.composite_key(torrent, tag)

            def update_counter(self, operation: Operation, increment: int = 1, is_local_peer: bool = False):
                """ Update TorrentTag's counter
                Args:
                    operation: Tag operation
                    increment:
                    is_local_peer: The flag indicates whether do we performs operations from a local user or from
                        a remote user. In case of the local user, his operations will be considered as
                        most valuable for his (only) local Tribler instance.

                Returns:
                """
                if is_local_peer:
                    self.local_operation = operation
                if operation == Operation.ADD:
                    self.added_count += increment
                if operation == Operation.REMOVE:
                    self.removed_count += increment

        class Tag(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            name = orm.Required(str, unique=True)
            torrents = orm.Set(lambda: TorrentTag)

        class TorrentTagOp(db.Entity):
            id = orm.PrimaryKey(int, auto=True)

            torrent_tag = orm.Required(lambda: TorrentTag)
            peer = orm.Required(lambda: Peer)

            operation = orm.Required(int)
            time = orm.Required(int)
            signature = orm.Required(bytes)
            updated_at = orm.Required(datetime.datetime, default=datetime.datetime.utcnow)

            orm.composite_key(torrent_tag, peer)

    @staticmethod
    def _get_or_create(cls, create_kwargs=None, **kwargs):  # pylint: disable=bad-staticmethod-argument
        """Get or create db entity.
        Args:
            cls: Entity's class, eg: `self.instance.Peer`
            create_kwargs: Additional arguments for creating new entity
            **kwargs: Arguments for selecting or for creating in case of missing entity

        Returns: Entity's instance
        """
        obj = cls.get_for_update(**kwargs)
        if not obj:
            if create_kwargs:
                kwargs.update(create_kwargs)
            obj = cls(**kwargs)
        return obj

    def add_tag_operation(self, infohash: bytes, tag: str, operation: Operation, time_of_operation: int,
                          creator_public_key: bytes, signature: bytes, is_local_peer: bool = False):
        """ Add the operation that will be applied to the tag
        Args:
            infohash: the infohash of a torrent to which tag will be added
            tag: the string representation of a tag
            operation: the operation (add, remove) on a tag
            time_of_operation: an integer that represents time. If the adding operation has time less or equal to the
                particular operation in the database, then it not be added.
            creator_public_key: a public key of the operation's creator
            signature: the signature of the operation
            is_local_peer: local operations processes differently than remote operations. They affects
                `TorrentTag.local_operation` field which is used in `self.get_tags()` function.

        Returns:
        """
        self.logger.debug(f'Add tag operation. Infohash: {infohash}, tag: {tag}')
        peer = self._get_or_create(self.instance.Peer, public_key=creator_public_key,
                                   create_kwargs={'last_time': time_of_operation})
        tag = self._get_or_create(self.instance.Tag, name=tag)
        torrent = self._get_or_create(self.instance.Torrent, infohash=infohash)
        torrent_tag = self._get_or_create(self.instance.TorrentTag, tag=tag, torrent=torrent)
        op = self.instance.TorrentTagOp.get_for_update(torrent_tag=torrent_tag, peer=peer)

        if not op:  # then insert
            self.instance.TorrentTagOp(torrent_tag=torrent_tag, peer=peer, operation=operation, time=time_of_operation,
                                       signature=signature)
            torrent_tag.update_counter(operation, is_local_peer=is_local_peer)
            return

        # if it is a message from the past, then return
        if time_of_operation <= op.time:
            return

        # To prevent endless incrementing of the operation, we apply the following logic:

        # 1. Decrement previous operation
        torrent_tag.update_counter(op.operation, increment=-1, is_local_peer=is_local_peer)
        # 2. Increment new operation
        torrent_tag.update_counter(operation, is_local_peer=is_local_peer)
        # 3. Update the operation entity
        op.set(operation=operation, time=time_of_operation, signature=signature)

    def get_tags(self, infohash: bytes) -> List[str]:
        """ Get all tags for this particular torrent

        Returns: A list of tags
        """
        self.logger.debug(f'Get tags. Infohash: {infohash}')

        torrent = self.instance.Torrent.get(infohash=infohash)
        if not torrent:
            return []

        def show_condition(torrent_tag):
            return torrent_tag.local_operation == Operation.ADD.value or \
                   not torrent_tag.local_operation and torrent_tag.added_count >= 2

        query = torrent.tags.select(show_condition)
        query = orm.select(tt.tag.name for tt in query)
        return list(query)

    def get_last_time_of_operation(self, infohash: bytes, tag: str, peer_public_key: bytes) -> int:
        """ Get time of operation
        Args:
            infohash: the infohash of a torrent to which tag will be added
            tag: the string representation of a tag
            peer_public_key: a public key of the operation's creator

        Returns: Time that represented by integer. If there is no operation for this infohash,
            tag and peer_public_key, then 0 will be return
        """
        peer = self.instance.Peer.get(public_key=peer_public_key)
        tag = self.instance.Tag.get(name=tag)
        torrent = self.instance.Torrent.get(infohash=infohash)
        if not torrent or not tag:
            return 0

        torrent_tag = self.instance.TorrentTag.get(tag=tag, torrent=torrent)
        if not torrent_tag or not peer:
            return 0

        op = self.instance.TorrentTagOp.get(torrent_tag=torrent_tag, peer=peer)
        return op.time if op else 0

    def shutdown(self) -> None:
        self.instance.disconnect()
