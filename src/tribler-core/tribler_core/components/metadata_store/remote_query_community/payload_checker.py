import enum
from dataclasses import dataclass, field

from pony.orm import db_session

from tribler_core.components.metadata_store.category_filter.l2_filter import is_forbidden
from tribler_core.components.metadata_store.db.serialization import (
    CHANNEL_DESCRIPTION,
    CHANNEL_THUMBNAIL,
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    DELETED,
    NULL_KEY,
    REGULAR_TORRENT,
)
from tribler_core.utilities.sentinels import sentinel
from tribler_core.utilities.unicode import hexlify


class ObjState(enum.Enum):
    UPDATED_LOCAL_VERSION = enum.auto()  # We updated the local version of the ORM object with the received one
    LOCAL_VERSION_NEWER = enum.auto()  # The local version of the ORM object is newer than the received one
    LOCAL_VERSION_SAME = enum.auto()  # The local version of the ORM object is the same as the received one
    NEW_OBJECT = enum.auto()  # The received object is unknown to us and thus added to ORM


CONTINUE = sentinel('CONTINUE')  # Sentinel object indicating that the check yielded no result


@dataclass
class ProcessingResult:
    # This class is used to return results of processing of a payload by process_payload.
    # It includes the ORM object created as a result of processing, the state of the object
    # as indicated by ObjState enum, and missing dependencies list that includes a list of query
    # arguments for get_entries to query the sender back through Remote Query Community
    md_obj: object = None
    obj_state: object = None
    missing_deps: list = field(default_factory=list)


class PayloadChecker:
    def __init__(self, mds, payload, skip_personal_metadata_payload=True, channel_public_key=None):
        self.mds = mds
        self.payload = payload
        self.skip_personal_metadata_payload = skip_personal_metadata_payload
        self.channel_public_key = channel_public_key
        self._logger = self.mds._logger  # pylint: disable=W0212

    def reject_payload_with_nonmatching_public_key(self, channel_public_key):
        """
        This check rejects payloads that do not match the given public key. It is used during authoritative
        updates of channels from disk (serialized and downloaded in the torrent form) to prevent
        channel creators from injecting random garbage into local database.
        """
        if self.payload.public_key != channel_public_key:
            self._logger.warning(
                "Tried to push metadata entry with foreign public key.\
             Expected public key: %s, entry public key / id: %s / %i",
                hexlify(channel_public_key),
                self.payload.public_key,
                self.payload.id_,
            )
            return []
        return CONTINUE

    def process_delete_node_command(self):
        """
        Check if the payload is a command to delete an existing node. If it is, delete the node
        and return empty list. Otherwise, CONTINUE control to further checks.
        """
        if self.payload.metadata_type == DELETED:
            # We only allow people to delete their own entries, thus PKs must match
            node = self.mds.ChannelNode.get_for_update(
                signature=self.payload.delete_signature, public_key=self.payload.public_key
            )
            if node:
                node.delete()
                return []
        return CONTINUE

    def reject_unknown_payload_type(self):
        """
        Check if the payload contains metadata of a known type.
        If it does not, stop processing and return empty list.
        Otherwise, CONTINUE control to further checks.
        """
        if self.payload.metadata_type not in [
            CHANNEL_TORRENT,
            REGULAR_TORRENT,
            COLLECTION_NODE,
            CHANNEL_DESCRIPTION,
            CHANNEL_THUMBNAIL,
        ]:
            return []
        return CONTINUE

    def reject_payload_with_offending_words(self):
        """
        Check if the payload contains strong offending words.
        If it does, stop processing and return empty list.
        Otherwise, CONTINUE control to further checks.
        """
        if is_forbidden(
            " ".join([getattr(self.payload, attr) for attr in ("title", "tags", "text") if hasattr(self.payload, attr)])
        ):
            return []
        return CONTINUE

    def add_ffa_node(self):
        """
        Check if the payload contains metadata of Free-For-All (FFA) type, which is just a REGULAR_TORRENT payload
        without signature. If it does, create a corresponding node in the local database.
        Otherwise, CONTINUE control to further checks.
        """
        if self.payload.public_key == NULL_KEY:
            if self.payload.metadata_type == REGULAR_TORRENT:
                node = self.mds.TorrentMetadata.add_ffa_from_dict(self.payload.to_dict())
                if node:
                    return [ProcessingResult(md_obj=node, obj_state=ObjState.NEW_OBJECT)]
            return []
        return CONTINUE

    def add_node(self):
        """
        Try to create a local node from the payload.
        If it is impossible, CONTINUE control to further checks (there should not be any more, really).
        """
        for orm_class in (
            self.mds.TorrentMetadata,
            self.mds.ChannelMetadata,
            self.mds.CollectionNode,
            self.mds.ChannelThumbnail,
            self.mds.ChannelDescription,
        ):
            if orm_class._discriminator_ == self.payload.metadata_type:  # pylint: disable=W0212
                obj = orm_class.from_payload(self.payload)
                return [ProcessingResult(md_obj=obj, obj_state=ObjState.NEW_OBJECT)]
        return CONTINUE

    def reject_personal_metadata(self):
        """
        Check if the payload contains metadata signed by our private key. This could happen in a situation where
        someone else tries to push us our old channel data, for example.
        Since we are the only authoritative source of information about our own channel, we reject
        such payloads and thus return empty list.
        Otherwise, CONTINUE control to further checks.
        """
        if self.payload.public_key == self.mds.my_public_key_bin:
            return []
        return CONTINUE

    def reject_obsolete_metadata(self):
        """
        Check if the received payload contains older deleted metadata for a channel we are subscribed to.
        In that case, we reject the metadata and return an empty list.
        Otherwise, CONTINUE control to further checks.
        """

        # ACHTUNG! Due to deficiencies in the current Channels design, it is impossible to
        # reliably tell if the received entry belongs to a channel we already subscribed,
        # if some of the intermediate folders were deleted earlier.
        # Also, this means we must return empty list for the case when the local subscribed channel
        # version is higher than the receive payload. This behavior does not conform to the
        # "local results == remote results" contract, but that is not a problem in most important cases
        # (e.g. browsing a non-subscribed channel). One situation where it can still matter is when
        # a remote search returns deleted results for a channel that we subscribe locally.
        parent = self.mds.CollectionNode.get(public_key=self.payload.public_key, id_=self.payload.origin_id)
        if parent is None:
            # Probably, this is a payload for an unknown object, so nothing to do here
            return CONTINUE
        # If the immediate parent is not a real channel, look for its toplevel parent in turn
        parent = parent.get_parent_nodes()[0] if parent.metadata_type != CHANNEL_TORRENT else parent

        if parent.metadata_type == CHANNEL_TORRENT and self.payload.timestamp <= parent.local_version:
            # The received metadata is an older entry from a channel we are subscribed to. Reject it.
            return []
        return CONTINUE

    def update_local_node(self):
        """
        Check if the received payload contains an updated version of metadata node we already have
        in the local database (e.g. a newer version of channel entry gossiped to us).
        We try to update the local metadata node in that case, returning UPDATED_LOCAL_VERSION status.
        Conversely, if we got a newer version of the metadata node, we return it to higher level
        with a LOCAL_VERSION_NEWER mark, so the higher level can possibly push an update back to the sender.
        If we don't have some version of the node locally, CONTINUE control to further checks.
        """
        # Check for the older version of the added node
        node = self.mds.ChannelNode.get_for_update(public_key=self.payload.public_key, id_=self.payload.id_)
        if not node:
            return CONTINUE

        node.to_simple_dict()  # Force loading of related objects (like TorrentMetadata.health) in db_session

        if node.timestamp == self.payload.timestamp:
            # We got the same version locally and do nothing.
            # Nevertheless, it is important to indicate to upper levels that we recognised
            # the entry, for e.g. channel votes bumping
            return [ProcessingResult(md_obj=node, obj_state=ObjState.LOCAL_VERSION_SAME)]
        if node.timestamp > self.payload.timestamp:
            # We got the newer version, return it to upper level (for e.g. a pushback update)
            return [ProcessingResult(md_obj=node, obj_state=ObjState.LOCAL_VERSION_NEWER)]
        if node.timestamp < self.payload.timestamp:
            # The received metadata has newer version than the stuff we got, so we have to update the local version.
            return self.update_channel_node(node)

        # This should never happen, really. But nonetheless, to appease the linter...
        return CONTINUE

    def update_channel_node(self, node):
        # Update the local metadata entry
        if node.metadata_type == self.payload.metadata_type:
            node.set(**self.payload.to_dict())
            return [ProcessingResult(md_obj=node, obj_state=ObjState.UPDATED_LOCAL_VERSION)]

        # Remote change of md type.
        # We delete the original node and replace it with the updated one.
        for orm_class in (self.mds.ChannelMetadata, self.mds.CollectionNode):
            if orm_class._discriminator_ == self.payload.metadata_type:  # pylint: disable=W0212
                node.delete()
                obj = orm_class.from_payload(self.payload)
                return [ProcessingResult(md_obj=obj, obj_state=ObjState.UPDATED_LOCAL_VERSION)]

        # Something went wrong, log it
        self._logger.warning(
            f"Tried to update channel node to illegal type: "
            f" original type: {node.metadata_type}"
            f" updated type: {self.payload.metadata_type}"
            f" {hexlify(self.payload.public_key)}, {self.payload.id_} "
        )
        return []

    def request_missing_dependencies(self, node_list):
        """
        Scan the results for entries with locally missing dependencies, such as thumbnail and description nodes,
        and modify the results by adding a dict with request for missing nodes in the get_entries format.
        """
        for r in node_list:
            updated_local_channel_node = (
                r.obj_state == ObjState.UPDATED_LOCAL_VERSION and r.md_obj.metadata_type == CHANNEL_TORRENT
            )
            r.missing_deps.extend(
                self.requests_for_child_dependencies(r.md_obj, include_newer=updated_local_channel_node)
            )

        return node_list

    def perform_checks(self):
        """
        This method runs checks on the received payload. Essentially, it acts like a firewall, rejecting
        incorrect or conflicting entries. Individual checks can return either CONTINUE, an empty list or a list
        of ProcessingResult objects. If CONTINUE sentinel object is returned, checks will proceed further.
        If non-CONTINUE result is returned by a check, the checking process stops.
        """
        if self.channel_public_key:
            yield self.reject_payload_with_nonmatching_public_key(self.channel_public_key)
        if self.skip_personal_metadata_payload:
            yield self.reject_personal_metadata()
        # We only allow deleting entries during authoritative updates
        if self.channel_public_key:
            yield self.process_delete_node_command()
        yield self.reject_unknown_payload_type()
        yield self.reject_payload_with_offending_words()
        yield self.reject_obsolete_metadata()
        yield self.add_ffa_node()
        yield self.update_local_node()
        yield self.add_node()

        # Something went wrong, log it
        self._logger.warning(
            f"Payload processing ended without actions, this should not happen normally."
            f" Payload type: {self.payload.metadata_type}"
            f" {hexlify(self.payload.public_key)}, {self.payload.id_} "
            f" {self.payload.timestamp}"
        )

        yield []

    def requests_for_child_dependencies(self, node, include_newer=False):
        """
        This method checks the given ORM node (object) for missing dependencies, such as thumbnails and/or
        descriptions. To do so, it checks for existence of special dependency flags in the object's
        "reserved_flags" field and checks for existence of the corresponding dependencies in the local database.
        """
        if node.metadata_type not in (CHANNEL_TORRENT, COLLECTION_NODE):
            return []

        result = []
        if node.description_flag:
            result.extend(self.check_and_request_child_dependency(node, CHANNEL_DESCRIPTION, include_newer))
        if node.thumbnail_flag:
            result.extend(self.check_and_request_child_dependency(node, CHANNEL_THUMBNAIL, include_newer))

        return result

    def check_and_request_child_dependency(self, node, dep_type, include_newer=False):
        """
        For each missing dependency it will generate a query in the "get_entry" format that should be addressed to the
        peer that sent the original payload/node/object.
        If include_newer argument is true, it will generate a query even if the dependencies exist in the local
        database. However, this query will limit the selection to dependencies with a higher timestamp than that
        of the local versions. Effectively, this query asks the remote peer for updates on dependencies. Thus,
        it should only be issued when it is known that the parent object was updated.
        """
        dep_node = self.mds.ChannelNode.select(
            lambda g: g.origin_id == node.id_ and g.public_key == node.public_key and g.metadata_type == dep_type
        ).first()
        request_dict = {
            "metadata_type": [dep_type],
            "channel_pk": node.public_key,
            "origin_id": node.id_,
            "first": 0,
            "last": 1,
        }
        if not dep_node:
            return [request_dict]
        if include_newer:
            request_dict["attribute_ranges"] = (("timestamp", dep_node.timestamp + 1, None),)
            return [request_dict]
        return []

    @db_session
    def process_payload(self):
        result = []
        for result in self.perform_checks():
            if result is not CONTINUE:
                break

        if self.channel_public_key is None:
            # The request came from the network, so check for missing dependencies
            result = self.request_missing_dependencies(result)
        return result


def process_payload(metadata_store, payload, skip_personal_metadata_payload=True, channel_public_key=None):
    """
    This routine decides what to do with a given payload and executes the necessary actions.
    To do so, it looks into the database, compares version numbers, etc.
    It returns a list of tuples each of which contain the corresponding new/old object and the actions
    that were performed on that object.
    :param metadata_store: Metadata Store object serving the database
    :param payload: payload to work on
    :param skip_personal_metadata_payload: if this is set to True, personal torrent metadata payload received
            through gossip will be ignored. The default value is True.
    :param channel_public_key: rejects payloads that do not belong to this key.
           Enabling this allows to skip some costly checks during e.g. channel processing.

    :return: a list of ProcessingResult objects
    """

    return PayloadChecker(
        metadata_store,
        payload,
        skip_personal_metadata_payload=skip_personal_metadata_payload,
        channel_public_key=channel_public_key,
    ).process_payload()
