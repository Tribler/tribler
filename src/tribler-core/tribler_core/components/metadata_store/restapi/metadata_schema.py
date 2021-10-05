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
    remote_query = Boolean(default=False)
    metadata_type = List(String(description='Limits query to certain metadata types (e.g. "torrent" or "channel")'))


class RemoteQueryParameters(MetadataParameters):
    uuid = String()
    channel_pk = String()


class ChannelSchema(Schema):
    type = Integer()
    id = Integer()
    origin_id = Integer()
    public_key = String()
    name = String()
    category = String()
    status = Integer()
    torrents = Integer()
    state = String()
    dirty = Boolean()
    infohash = String()
    size = Integer()
    num_seeders = Integer()
    num_leechers = Integer()
    last_tracker_check = Integer()
    updated = Integer()
    subscribed = Boolean()
    votes = Float()
    progress = Float()


class TorrentSchema(Schema):
    type = Integer()
    id = Integer()
    origin_id = Integer()
    public_key = String()
    name = String()
    category = String()
    status = Integer()
    torrents = Integer()
    state = String()
    dirty = Boolean()
    infohash = String()
    size = Integer()
    num_seeders = Integer()
    num_leechers = Integer()
    last_tracker_check = Integer()
    updated = Integer()
    subscribed = Boolean()
    votes = Float()
    progress = Float()
