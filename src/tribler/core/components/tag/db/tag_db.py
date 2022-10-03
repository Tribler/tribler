import datetime
import logging
from typing import Callable, Iterable, List, Optional, Set

from pony import orm
from pony.orm import exists, select
from pony.orm.core import Entity
from pony.utils import between

from tribler.core.components.tag.community.tag_payload import TagOperation, TagOperationEnum, TagRelationEnum
from tribler.core.utilities.pony_utils import get_or_create
from tribler.core.utilities.unicode import hexlify

CLOCK_START_VALUE = 0

PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS = b'auto_generated'

SHOW_THRESHOLD = 1
HIDE_THRESHOLD = -2


class TagDatabase:
    def __init__(self, filename: Optional[str] = None, *, create_tables: bool = True, **generate_mapping_kwargs):
        self.instance = orm.Database()
        self.define_binding(self.instance)
        self.instance.bind('sqlite', filename or ':memory:', create_db=True)
        generate_mapping_kwargs['create_tables'] = create_tables
        self.instance.generate_mapping(**generate_mapping_kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

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
            relation = orm.Required(int, default=1, index=True)  # default is the 'HAS_TAG' relation
            tag = orm.Required(lambda: Tag)

            operations = orm.Set(lambda: TorrentTagOp)

            added_count = orm.Required(int, default=0)
            removed_count = orm.Required(int, default=0)

            local_operation = orm.Optional(int)  # in case user don't (or do) want to see it locally

            orm.composite_key(torrent, relation, tag)

            @property
            def score(self):
                return self.added_count - self.removed_count

            def update_counter(self, operation: TagOperationEnum, increment: int = 1, is_local_peer: bool = False):
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
                if operation == TagOperationEnum.ADD:
                    self.added_count += increment
                if operation == TagOperationEnum.REMOVE:
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

    def add_tag_operation(self, operation: TagOperation, signature: bytes, is_local_peer: bool = False,
                          is_auto_generated: bool = False, counter_increment: int = 1) -> bool:
        """ Add the operation that will be applied to the tag.
        Args:
            operation: the class describes the adding operation
            signature: the signature of the operation
            is_local_peer: local operations processes differently than remote operations. They affects
                `TorrentTag.local_operation` field which is used in `self.get_tags()` function.
            is_auto_generated: the indicator of whether this tag was generated automatically or not
            counter_increment: the counter or "numbers" of adding operations

        Returns: True if the operation has been added/updated, False otherwise.
        """
        self.logger.debug(f'Add tag operation. Infohash: {hexlify(operation.infohash)}, tag: {operation.tag}')
        peer = get_or_create(self.instance.Peer, public_key=operation.creator_public_key)
        tag = get_or_create(self.instance.Tag, name=operation.tag)
        torrent = get_or_create(self.instance.Torrent, infohash=operation.infohash)
        torrent_tag = get_or_create(self.instance.TorrentTag, tag=tag, torrent=torrent, relation=operation.relation)
        op = self.instance.TorrentTagOp.get_for_update(torrent_tag=torrent_tag, peer=peer)

        if not op:  # then insert
            self.instance.TorrentTagOp(torrent_tag=torrent_tag, peer=peer, operation=operation.operation,
                                       clock=operation.clock, signature=signature, auto_generated=is_auto_generated)
            torrent_tag.update_counter(operation.operation, increment=counter_increment, is_local_peer=is_local_peer)
            return True

        # if it is a message from the past, then return
        if operation.clock <= op.clock:
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

    def add_auto_generated_tag(self, infohash: bytes, tag: str, relation: TagRelationEnum = TagRelationEnum.HAS_TAG):
        operation = TagOperation(
            infohash=infohash,
            operation=TagOperationEnum.ADD,
            relation=relation,
            clock=CLOCK_START_VALUE,
            creator_public_key=PUBLIC_KEY_FOR_AUTO_GENERATED_TAGS,
            tag=tag
        )

        self.add_tag_operation(operation, signature=b'', is_local_peer=False, is_auto_generated=True,
                               counter_increment=SHOW_THRESHOLD)

    @staticmethod
    def _show_condition(torrent_tag):
        """This function determines show condition for the torrent_tag"""
        return torrent_tag.local_operation == TagOperationEnum.ADD.value or \
               not torrent_tag.local_operation and torrent_tag.score >= SHOW_THRESHOLD

    def _get_tags(self, infohash: bytes, condition: Callable[[], bool],
                  relation: TagRelationEnum = TagRelationEnum.HAS_TAG) -> List[str]:
        """
        Get tags that satisfy a given condition.

        Returns: A list of tags that satisfy the given condition.
        """
        torrent = self.instance.Torrent.get(infohash=infohash)
        if not torrent:
            return []

        query = (
            torrent.tags
            .select(condition)
            .filter(lambda tt: tt.relation == relation.value)
        )
        query = query.order_by(lambda tt: orm.desc(tt.score))
        query = orm.select(tt.tag.name for tt in query)
        return list(query)

    def get_tags(self, infohash: bytes, relation: TagRelationEnum = TagRelationEnum.HAS_TAG) -> List[str]:
        """ Get all tags for this particular torrent.

        Returns: A list of tags
        """
        self.logger.debug(f'Get tags. Infohash: {hexlify(infohash)}, relation: {relation}')

        return self._get_tags(infohash, self._show_condition, relation=relation)

    def get_suggestions(self, infohash: bytes, relation: TagRelationEnum = TagRelationEnum.HAS_TAG) -> List[str]:
        """
        Get all suggestions for a particular torrent.

        Returns: A list of suggestions.
        """
        self.logger.debug(f"Getting tag suggestions for infohash {hexlify(infohash)}")

        def show_suggestions_condition(torrent_tag):
            return not torrent_tag.local_operation and \
                   between(torrent_tag.score, HIDE_THRESHOLD + 1, SHOW_THRESHOLD - 1)

        return self._get_tags(infohash, show_suggestions_condition, relation=relation)

    def get_infohashes(self, tags: Set[str], relation: TagRelationEnum = TagRelationEnum.HAS_TAG) -> List[bytes]:
        """Get list of infohashes that belongs to the tag.
        Only tags with condition `_show_condition` will be returned.
        In the case that the tags set contains more than one tag,
        only torrents that contain all `tags` will be returned.
        """

        query_results = select(
            torrent.infohash for torrent in self.instance.Torrent
            if not exists(
                tag for tag in self.instance.Tag
                if tag.name in tags and not exists(
                    torrent_tag for torrent_tag in self.instance.TorrentTag
                    if torrent_tag.torrent == torrent
                    and torrent_tag.tag == tag
                    and self._show_condition(torrent_tag)
                    and torrent_tag.relation == relation.value
                )
            )
        ).fetch()
        return query_results

    def get_clock(self, operation: TagOperation) -> int:
        """ Get the clock (int) of operation.
        """
        peer = self.instance.Peer.get(public_key=operation.creator_public_key)
        tag = self.instance.Tag.get(name=operation.tag)
        torrent = self.instance.Torrent.get(infohash=operation.infohash)
        if not torrent or not tag or not peer:
            return 0

        torrent_tag = self.instance.TorrentTag.get(tag=tag, torrent=torrent, relation=operation.relation)
        if not torrent_tag:
            return 0

        op = self.instance.TorrentTagOp.get(torrent_tag=torrent_tag, peer=peer)
        return op.clock if op else CLOCK_START_VALUE

    def get_tags_operations_for_gossip(self, time_delta, count: int = 10) -> Iterable[Entity]:
        """ Get random operations from the DB that older than time_delta.

        Args:
            time_delta: a dictionary for `datetime.timedelta`
            count: a limit for a resulting query
        """
        updated_at = datetime.datetime.utcnow() - datetime.timedelta(**time_delta)
        return self._get_random_tag_operations_by_condition(
            condition=lambda tto: tto.updated_at <= updated_at and not tto.auto_generated,
            count=count
        )

    def shutdown(self) -> None:
        self.instance.disconnect()

    def _get_random_tag_operations_by_condition(self, condition: Callable[[Entity], bool], count: int = 5,
                                                attempts: int = 100) -> Set[Entity]:
        operations = set()
        for _ in range(attempts):
            if len(operations) == count:
                return operations

            random_operations_list = self.instance.TorrentTagOp.select_random(1)
            if random_operations_list:
                operation = random_operations_list[0]
                if condition(operation):
                    operations.add(operation)

        return operations
