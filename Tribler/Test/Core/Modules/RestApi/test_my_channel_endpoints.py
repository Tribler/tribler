from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestMyChannelEndpoints(AbstractApiTest):

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created
        """
        return self.do_request('mychannel/overview', expected_code=404)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

        channel_json = {u'overview': {u'name': u'testname', u'description': u'testdescription',
                                      u'identifier': 'fakedispersyid'.encode('hex')}}
        channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        channel_db_handler.on_channel_from_dispersy('fakedispersyid', None,
                                                         channel_json['overview']['name'],
                                                         channel_json['overview']['description'])

        return self.do_request('mychannel/overview', expected_code=200, expected_json=channel_json)
