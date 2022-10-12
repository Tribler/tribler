from marshmallow import Schema
from marshmallow.fields import String


class HandledErrorSchema(Schema):
    error = String(description='Optional field describing any failures that may have occurred', required=True)
