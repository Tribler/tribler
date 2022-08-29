from marshmallow import Schema
from marshmallow.fields import Dict, String


class HandledErrorSchema(Schema):
    error = String(description='Optional field describing any failures that may have occurred', required=True)
    context = Dict(description='Arbitrary dict of additional data useful to understanding the error',
                   keys=String(), required=False)
