import json

from twisted.web import resource


class MultichainEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)

        child_handler_dict = {"statistics": MultichainStatsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls())


class MultichainStatsEndpoint(resource.Resource):
    """
    This class handles requests regarding the multichain community information.
    """

    def render_GET(self, request):
        return json.dumps({'statistics': {
            "self_id": "12345667",
            "latest_block_insert_time": "2016-08-04 12:01:53",
            "self_total_blocks": 3243,
            "latest_block_id": "32428fdsjkl3f3",
            "latest_block_requester_id": "fdjklfdhfeek3",
            "latest_block_up_mb": 34,
            "self_total_down_mb": 3859,
            "latest_block_down_mb": 85,
            "self_total_up_mb": 9583,
            "latest_block_responder_id": "f83ldsmhqio"
        }})
