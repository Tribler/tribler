from ipv8.REST.schema import schema

from marshmallow import Schema
from marshmallow.fields import Boolean, Integer, String


class HandledErrorSchema(Schema):
    error = String(description='Optional field describing any failures that may have occurred', required=True)
