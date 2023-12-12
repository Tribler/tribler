from marshmallow.fields import Integer, String

from tribler.core.components.database.restapi.schema import MetadataParameters


class RemoteQueryParameters(MetadataParameters):
    uuid = String()
    channel_pk = String(description='Channel to query, must also define origin_id')
    origin_id = Integer(default=None, description='Peer id to query, must also define channel_pk')
