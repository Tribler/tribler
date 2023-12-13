from marshmallow import Schema
from marshmallow.fields import Boolean, Float, Integer, List, String


class MetadataParameters(Schema):
    first = Integer(default=1, description='Limit the range of the query')
    last = Integer(default=50, description='Limit the range of the query')
    sort_by = String(description='Sorts results in forward or backward, based on column name (e.g. "id" vs "-id")')
    sort_desc = Boolean(default=True)
    txt_filter = String(description='FTS search on the chosen word* terms')
    hide_xxx = Boolean(default=False, description='Toggles xxx filter')
    category = String()
    exclude_deleted = Boolean(default=False)
    metadata_type = List(String(description='Limits query to certain metadata types (e.g. "torrent" or "channel")'))


class SearchMetadataParameters(MetadataParameters):
    include_total = Boolean(default=False, description='Include total rows found in query response, expensive if '
                                                       'there is many rows')
    max_rowid = Integer(default=None, description='Only return results with rowid lesser than max_rowid')


class MetadataSchema(Schema):
    type = Integer()
    id = Integer()
    origin_id = Integer()
    public_key = String()
    name = String()
    category = String()
    progress = Float(required=False)


class CollectionSchema(MetadataSchema):
    torrents = Integer()
    state = String()
    description_flag = Boolean()
    thumbnail_flag = Boolean()


class TorrentSchema(MetadataSchema):
    status = Integer()
    infohash = String()
    size = Integer()
    num_seeders = Integer()
    num_leechers = Integer()
    last_tracker_check = Integer()
    updated = Integer()


class ChannelSchema(TorrentSchema, CollectionSchema):
    dirty = Boolean()
    subscribed = Boolean()
    votes = Float()
