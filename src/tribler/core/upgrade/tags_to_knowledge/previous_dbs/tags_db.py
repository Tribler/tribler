import datetime
from typing import Optional

from pony import orm

from tribler.core.utilities.pony_utils import TrackedDatabase, get_or_create


class TagDatabase:
    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = TrackedDatabase()
        self.define_binding(self.instance)
        self.instance.bind('sqlite', filename or ':memory:', create_db=True)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)

    @staticmethod
    def define_binding(db):
        class Peer(db.Entity):
            id = orm.PrimaryKey(int, auto=True)
            public_key = orm.Required(bytes, unique=True)
            added_at = orm.Optional(datetime.datetime, default=datetime.datetime.utcnow)
            operations = orm.Set(lambda: TorrentTagOp)

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

            @property
            def score(self):
                return self.added_count - self.removed_count

            def update_counter(self, operation: int, increment: int = 1, is_local_peer: bool = False):
                """ Update TorrentTag's counter
                Args:
                    operation: Tag operation
                    increment:
                    is_local_peer: The flag indicates whether do we performs operations from a local user or from
                        a remote user. In case of the local user, his operations will be considered as
                        authoritative for his (only) local Tribler instance.

                Returns:
                """
                if is_local_peer:
                    self.local_operation = operation
                if operation == 1:
                    self.added_count += increment
                if operation == 2:
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
            clock = orm.Required(int)
            signature = orm.Required(bytes)
            updated_at = orm.Required(datetime.datetime, default=datetime.datetime.utcnow)
            auto_generated = orm.Required(bool, default=False)

            orm.composite_key(torrent_tag, peer)

    def add_tag_operation(self, infohash: bytes, tag: str, signature: bytes, operation: int, clock: int,
                          creator_public_key: bytes,
                          is_local_peer: bool = False,
                          is_auto_generated: bool = False, counter_increment: int = 1) -> bool:
        """ Add the operation that will be applied to the tag.
        Args:
            operation: the class describes the adding operation
            signature: the signature of the operation
            is_local_peer: local operations processes differently than remote operations. They affects
                `TorrentTag.local_operation` field which is used in `self.get_tags()` function.

        Returns: True if the operation has been added/updated, False otherwise.
        """
        peer = get_or_create(self.instance.Peer, public_key=creator_public_key)
        tag = get_or_create(self.instance.Tag, name=tag)
        torrent = get_or_create(self.instance.Torrent, infohash=infohash)
        torrent_tag = get_or_create(self.instance.TorrentTag, tag=tag, torrent=torrent)
        op = self.instance.TorrentTagOp.get_for_update(torrent_tag=torrent_tag, peer=peer)

        if not op:  # then insert
            self.instance.TorrentTagOp(torrent_tag=torrent_tag, peer=peer, operation=operation,
                                       clock=clock, signature=signature, auto_generated=is_auto_generated)
            torrent_tag.update_counter(operation, increment=counter_increment, is_local_peer=is_local_peer)
            return True

        # if it is a message from the past, then return
        if clock <= op.clock:
            return False

        # To prevent endless incrementing of the operation, we apply the following logic:

        # 1. Decrement previous operation
        torrent_tag.update_counter(op.operation, increment=-counter_increment, is_local_peer=is_local_peer)
        # 2. Increment new operation
        torrent_tag.update_counter(operation.operation, increment=counter_increment, is_local_peer=is_local_peer)

        # 3. Update the operation entity
        op.set(operation=operation.operation, clock=operation.clock, signature=signature,
               updated_at=datetime.datetime.utcnow(), auto_generated=is_auto_generated)
        return True

    def shutdown(self) -> None:
        self.instance.disconnect()
