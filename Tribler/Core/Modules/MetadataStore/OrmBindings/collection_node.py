from __future__ import absolute_import, print_function

import os

from ipv8.database import database_blob

from pony import orm
from pony.orm import db_session, select

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import chunks
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import (
    COMMITTED,
    DIRTY_STATUSES,
    NEW,
    TODELETE,
    UPDATED,
)
from Tribler.Core.Modules.MetadataStore.OrmBindings.torrent_metadata import tdef_to_metadata_dict
from Tribler.Core.Modules.MetadataStore.serialization import COLLECTION_NODE, CollectionNodePayload
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Core.Utilities.unicode import ensure_unicode
from Tribler.Core.exceptions import DuplicateTorrentFileError


def define_binding(db):
    class CollectionNode(db.MetadataNode):
        """
        This ORM class represents a generic named container, i.e. a folder. It is used as an intermediary node
        in building the nested channels tree.
        Methods for copying stuff recursively are bound to it.
        """

        _discriminator_ = COLLECTION_NODE

        # FIXME: ACHTUNG! PONY BUG! attributes inherited from multiple inheritance are not cached!
        # Therefore, we are forced to move the attributes to common ancestor class of CollectionNode and ChannelTorrent,
        # that is MetadataNode. When Pony fixes it, we must move it here for clarity.
        # num_entries = orm.Optional(int, size=64, default=0)

        # Special class-level properties
        _payload_class = CollectionNodePayload
        payload_arguments = _payload_class.__init__.__code__.co_varnames[
            : _payload_class.__init__.__code__.co_argcount
        ][1:]
        nonpersonal_attributes = db.MetadataNode.nonpersonal_attributes + ('num_entries',)

        @property
        @db_session
        def state(self):
            if self.is_personal:
                return "Personal"
            return "Preview"

        @db_session
        def to_simple_dict(self):
            result = super(CollectionNode, self).to_simple_dict()
            result.update(
                {
                    "torrents": self.num_entries,
                    "state": self.state,
                    "total": self.contents_len,
                    "dirty": self.dirty if self.is_personal else False,
                }
            )
            return result

        def make_copy(self, tgt_parent_id, recursion_depth=15, **kwargs):
            new_node = db.MetadataNode.make_copy(self, tgt_parent_id, **kwargs)
            # Recursive copying
            if recursion_depth:
                for node in self.actual_contents:
                    if issubclass(type(node), CollectionNode):
                        node.make_copy(new_node.id_, recursion_depth=recursion_depth - 1)
                    else:
                        node.make_copy(new_node.id_)
            return new_node

        @db_session
        def copy_torrent_from_infohash(self, infohash):
            """
            Search the database for a given infohash and create a copy of the matching entry in the current channel
            :param infohash:
            :return: New TorrentMetadata signed with your key.
            """

            existing = db.TorrentMetadata.select(lambda g: g.infohash == database_blob(infohash)).first()

            if not existing:
                return None

            new_entry_dict = {
                "origin_id": self.id_,
                "infohash": existing.infohash,
                "title": existing.title,
                "tags": existing.tags,
                "size": existing.size,
                "torrent_date": existing.torrent_date,
                "tracker_info": existing.tracker_info,
                "status": NEW,
            }
            return db.TorrentMetadata.from_dict(new_entry_dict)

        @property
        def dirty(self):
            return self.contents.where(lambda g: g.status in DIRTY_STATUSES).exists()

        @property
        def contents(self):
            return db.ChannelNode.select(
                lambda g: g.public_key == self.public_key and g.origin_id == self.id_ and g != self
            )

        @property
        def actual_contents(self):
            return self.contents.where(lambda g: g.status != TODELETE)

        @db_session
        def get_random_torrents(self, limit):
            return self.contents.where(lambda g: g.status not in [NEW, TODELETE]).random(limit)

        @property
        @db_session
        def contents_list(self):
            return list(self.contents)

        @property
        def contents_len(self):
            return orm.count(self.contents)

        @db_session
        def add_torrent_to_channel(self, tdef, extra_info=None):
            """
            Add a torrent to your channel.
            :param tdef: The torrent definition file of the torrent to add
            :param extra_info: Optional extra info to add to the torrent
            """
            new_entry_dict = dict(tdef_to_metadata_dict(tdef), status=NEW)
            if extra_info:
                new_entry_dict['tags'] = extra_info.get('description', '')

            # See if the torrent is already in the channel
            old_torrent = db.TorrentMetadata.get(public_key=self.public_key, infohash=tdef.get_infohash())
            if old_torrent:
                # If it is there, check if we were going to delete it
                if old_torrent.status == TODELETE:
                    new_timestamp = self._clock.tick()
                    old_torrent.set(timestamp=new_timestamp, origin_id=self.id_, **new_entry_dict)
                    old_torrent.sign()
                    # As we really don't know what status this torrent had _before_ it got its TODELETE status,
                    # we _must_ set its status to UPDATED, for safety
                    old_torrent.status = UPDATED
                    torrent_metadata = old_torrent
                else:
                    raise DuplicateTorrentFileError()
            else:
                torrent_metadata = db.TorrentMetadata.from_dict(dict(origin_id=self.id_, **new_entry_dict))
            return torrent_metadata

        @db_session
        def pprint_tree(self, file=None, _prefix="", _last=True):
            print(_prefix, "`- " if _last else "|- ", (self.num_entries, self.metadata_type), sep="", file=file)
            _prefix += "   " if _last else "|  "
            child_count = self.actual_contents.count()
            for i, child in enumerate(list(self.actual_contents)):
                if issubclass(type(child), CollectionNode):
                    _last = i == (child_count - 1)
                    child.pprint_tree(file, _prefix, _last)
                else:
                    print(_prefix, "`- " if _last else "|- ", child.metadata_type, sep="", file=file)

        @db_session
        def get_contents_recursive(self):
            results_stack = []
            for subnode in self.contents:
                if issubclass(type(subnode), CollectionNode):
                    results_stack.extend(subnode.get_contents_recursive())
                results_stack.append(subnode)
            return results_stack

        @db_session
        def add_torrents_from_dir(self, torrents_dir, recursive=False):
            torrents_list = []
            errors_list = []

            def rec_gen(dir_):
                for root, _, filenames in os.walk(dir_):
                    for fn in filenames:
                        yield os.path.join(root, fn)

            filename_generator = rec_gen(torrents_dir) if recursive else os.listdir(torrents_dir)

            # Build list of .torrents to process
            for f in filename_generator:
                filepath = ensure_unicode(
                    os.path.join(ensure_unicode(torrents_dir, 'utf-8'), ensure_unicode(f, 'utf-8')), 'utf-8'
                )
                if os.path.isfile(filepath) and ensure_unicode(f, 'utf-8').endswith(u'.torrent'):
                    torrents_list.append(filepath)

            for chunk in chunks(torrents_list, 100):  # 100 is a reasonable chunk size for commits
                for f in chunk:
                    try:
                        self.add_torrent_to_channel(TorrentDef.load(f))
                    except DuplicateTorrentFileError:
                        pass
                    except Exception:
                        # Have to use the broad exception clause because Py3 versions of libtorrent
                        # generate generic Exceptions
                        errors_list.append(f)
                orm.commit()  # Optimization to drop excess cache

            return torrents_list, errors_list

        @staticmethod
        @db_session
        def commit_all_channels():
            committed_channels = []
            commit_queues_list = db.ChannelMetadata.get_commit_forest()
            for _, queue in commit_queues_list.items():
                channel = queue[-1]
                # Committing empty channels
                if len(queue) == 1:
                    # Empty top-level channels are deleted on-sight
                    if channel.status == TODELETE:
                        channel.delete()
                    else:
                        # Only the top-level channel entry was changed. Just mark it committed and do nothing.
                        channel.status = COMMITTED
                    continue

                # Committing non-empty channels
                queue_prepared = db.ChannelMetadata.prepare_commit_queue_for_channel(queue)
                if isinstance(channel, db.ChannelMetadata):
                    committed_channels.append(channel.commit_channel_torrent(commit_list=queue_prepared))
                # Top-level collections get special treatment.
                # These can be used for e.g. non-published personal favourites collections.
                elif isinstance(channel, db.CollectionNode):
                    for g in queue:
                        if g.status in [NEW, UPDATED]:
                            g.status = COMMITTED
                        elif g.status == TODELETE:
                            g.delete()

            return committed_channels

        @staticmethod
        @db_session
        def get_children_dict_to_commit():
            db.CollectionNode.collapse_deleted_subtrees()
            upd_dict = {}
            children = {}
            # TODO: optimize me by rewriting in pure SQL with recursive CTEs

            def update_node_info(n):
                # Add the node to its parent's set of children
                if n.origin_id not in children:
                    children[n.origin_id] = {n}
                else:
                    children[n.origin_id].add(n)
                upd_dict[n.id_] = n

            dead_parents = set()
            # First we traverse the tree upwards from changed leaves to find all nodes affected by changes
            for node in db.ChannelNode.select(lambda g: g.status in DIRTY_STATUSES):
                update_node_info(node)
                # This process resolves the parents completely.
                # Therefore, if a parent is already in the dict, its path has already been resolved.
                while node and (node.origin_id not in upd_dict):
                    # Add the node to its parent's set of children
                    update_node_info(node)
                    # Get parent node
                    parent = db.CollectionNode.get(public_key=node.public_key, id_=node.origin_id)
                    if not parent:
                        dead_parents.add(node.origin_id)
                    node = parent

            # Normally, dead_parents should consist only of 0 node, which is root. Otherwise, we got some orphans.
            if 0 in dead_parents:
                dead_parents.remove(0)
            # Delete orphans
            db.ChannelNode.select(
                lambda g: database_blob(db.ChannelNode._my_key.pub().key_to_bin()[10:]) == g.public_key
                and g.origin_id in dead_parents
            ).delete()
            orm.flush()  # Just in case...
            if not children or 0 not in children:
                return {}
            return children

        @staticmethod
        @db_session
        def get_commit_forest():
            children = db.CollectionNode.get_children_dict_to_commit()
            if not children:
                return {}
            # We want a separate commit tree/queue for each toplevel channel
            forest = {}
            toplevel_nodes = [node for node in children.pop(0)]
            for root_node in toplevel_nodes:
                # Tree -> stack -> queue
                commit_queue = []
                tree_stack = [root_node]
                while tree_stack and children.get(tree_stack[-1].id_, None):
                    # Traverse the tree from top to bottom converting it to a stack
                    while children.get(tree_stack[-1].id_, None):
                        node = children[tree_stack[-1].id_].pop()
                        tree_stack.append(node)

                    while not issubclass(type(tree_stack[-1]), db.CollectionNode):
                        commit_queue.append(tree_stack.pop())
                    # Unwind the tree stack until either the stack is empty or we meet a non-empty node
                    while tree_stack and not children.get(tree_stack[-1].id_, None):
                        while not issubclass(type(tree_stack[-1]), db.CollectionNode):
                            commit_queue.append(tree_stack.pop())

                        # It was a terminal collection
                        collection = tree_stack.pop()
                        commit_queue.append(collection)

                if not commit_queue or commit_queue[-1] != root_node:
                    commit_queue.append(root_node)
                forest[root_node.id_] = tuple(commit_queue)

            return forest

        @staticmethod
        def prepare_commit_queue_for_channel(commit_queue):
            """
            This routine prepares the raw commit queue for commit by updating the elements' properties and
            re-signing them. Also, it removes the channel entry itself from the queue [:-1], because its
            meaningless to put it in the blobs, as it must be updated with the new infohash after commit.

            :param commit_queue:
            :return:
            """
            for node in commit_queue:
                # Avoid updating entries that must be deleted:
                # soft delete payloads require signatures of unmodified entries
                if issubclass(type(node), db.CollectionNode) and node.status != TODELETE:
                    # Update recursive count of actual non-collection contents
                    node.num_entries = select(
                        # For each subnode, if it is a collection, add the count of its contents to the recursive sum.
                        # Otherwise, add just 1 to the sum (to count the subnode itself).
                        (g.num_entries if g.metadata_type == COLLECTION_NODE else 1)
                        for g in node.actual_contents
                    ).sum()
                    node.timestamp = db.ChannelNode._clock.tick()
                    node.sign()
            return sorted(commit_queue, key=lambda x: x.timestamp)[:-1]

        def delete(self, *args, **kwargs):
            # Recursively delete contents
            if kwargs.pop('recursive', True):
                for node in self.contents:
                    node.delete(*args, **kwargs)
            super(CollectionNode, self).delete(*args, **kwargs)

        @staticmethod
        @db_session
        def collapse_deleted_subtrees():
            """
            This procedure scans personal channels for collection nodes marked TODELETE and recursively removes
            their contents. The nodes themselves are left intact so soft delete entries can be generated from them
            in the future.
            The procedure should be always run _before_ committing personal channels.
            """
            # TODO: optimize with SQL recursive CTEs

            def get_highest_deleted_parent(node, highest_deleted_parent=None):
                if node.origin_id == 0:
                    return highest_deleted_parent
                parent = db.CollectionNode.get(public_key=node.public_key, id_=node.origin_id)
                if not parent:
                    return highest_deleted_parent
                if parent.status == TODELETE:
                    highest_deleted_parent = parent
                return get_highest_deleted_parent(parent, highest_deleted_parent)

            deletion_set = {
                get_highest_deleted_parent(node, highest_deleted_parent=node).rowid
                for node in db.CollectionNode.select(lambda g: g.status == TODELETE)
                if node
            }

            for node in [db.CollectionNode[rowid] for rowid in deletion_set]:
                for subnode in node.contents:
                    subnode.delete()

        @db_session
        def get_contents_to_commit(self):
            return db.ChannelMetadata.prepare_commit_queue_for_channel(self.get_commit_forest().get(self.id_, []))

        def update_properties(self, update_dict):
            # Sanity checks: check that we don't create a recursive dependency or an orphaned channel
            new_origin_id = update_dict.get('origin_id', self.origin_id)
            if new_origin_id not in (0, self.origin_id):
                new_parent = CollectionNode.get(public_key=self.public_key, id_=new_origin_id)
                if not new_parent:
                    raise ValueError("Target collection does not exists")
                root_path = new_parent.get_parents_ids()
                if new_origin_id == self.id_ or self.id_ in root_path:
                    raise ValueError("Can't move collection into itself or its descendants!")
                if 0 not in root_path:
                    # TODO: add orphan-cleaning hook here
                    raise ValueError("Tried to move collection into an orphaned hierarchy!")
            updated_self = super(CollectionNode, self).update_properties(update_dict)
            if updated_self.origin_id == 0 and self.metadata_type == COLLECTION_NODE:
                # Coerce to ChannelMetadata
                # ACHTUNG! This is a somewhat awkward way to re-create the entry as an instance of
                # another class. Be very careful with it!
                self_dict = updated_self.to_dict()
                updated_self.delete(recursive=False)
                self_dict.pop("rowid")
                self_dict.pop("metadata_type")
                self_dict['infohash'] = random_infohash()
                self_dict["sign_with"] = self._my_key
                updated_self = db.ChannelMetadata.from_dict(self_dict)
            return updated_self

    return CollectionNode
