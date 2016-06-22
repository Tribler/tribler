import json
from twisted.web import resource


class VariablesEndpoint(resource.Resource):

    isLeaf = True

    # Only contains the most necessary variables needed for the GUI
    def render_GET(self, request):

        variables_dict = {"variables": {
            "ports": {
                "video~port": 1337,
            },
        }}

        return json.dumps(variables_dict)
