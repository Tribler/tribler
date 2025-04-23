from marshmallow import Schema
from marshmallow.fields import Boolean, Float, Integer, List, String


class MetadataParameters(Schema):
    """
    The REST API schema for metadata parameters.
    """

    first = Integer(load_default=1, metadata={"description": "Limit the range of the query"})
    last = Integer(load_default=50, metadata={"description": "Limit the range of the query"})
    sort_by = String(metadata={
        "description": 'Sorts results in forward or backward, based on column name (e.g. "id" vs "-id")'
    })
    sort_desc = Boolean(load_default=True)
    txt_filter = String(metadata={"description": "FTS search on the chosen word* terms"})
    hide_xxx = Boolean(load_default=False, metadata={"description": "Toggles xxx filter"})
    category = String()
    exclude_deleted = Boolean(load_default=False)
    metadata_type = List(String(metadata={
        "description": 'Limits query to certain metadata types (e.g. "torrent" or "channel")'
    }))


class SearchMetadataParameters(MetadataParameters):
    """
    The REST API schema for search parameters.
    """

    include_total = Boolean(load_default=False, metadata={
        "description": "Include total rows found in query response, expensive if there are many rows"
    })
    max_rowid = Integer(load_default=None, metadata={
        "description": "Only return results with rowid lesser than max_rowid"
    })


class MetadataSchema(Schema):
    """
    The REST API schema for metadata itself.
    """

    type = Integer()
    id = Integer()
    origin_id = Integer()
    public_key = String()
    name = String()
    category = String()
    progress = Float(required=False)


class CollectionSchema(MetadataSchema):
    """
    The REST API schema for collected torrents.
    """

    torrents = Integer()
    state = String()
    description_flag = Boolean()
    thumbnail_flag = Boolean()


class TorrentSchema(MetadataSchema):
    """
    The REST API schema for a torrent.
    """

    status = Integer()
    infohash = String()
    size = Integer()
    num_seeders = Integer()
    num_leechers = Integer()
    last_tracker_check = Integer()
    updated = Integer()


class ChannelSchema(TorrentSchema, CollectionSchema):
    """
    The REST API schema for a channel.
    """

    dirty = Boolean()
    subscribed = Boolean()
    votes = Float()
