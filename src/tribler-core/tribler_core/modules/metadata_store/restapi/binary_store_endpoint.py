from binascii import unhexlify

from aiohttp import web
from aiohttp.web_request import Request

from pony.orm import db_session

from tribler_core.restapi.rest_endpoint import RESTEndpoint
from tribler_core.utilities.path_util import Path


class BinaryDataEndpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/{filename}', self.get_binary_data),
                web.post('', self.post_binary_data),
            ]
        )

    async def get_binary_data(self, request):
        filename = Path(request.match_info['filename'])
        data_hash = unhexlify(filename.stem)
        with db_session:
            obj = self.session.mds.BinaryData.get(hash=data_hash)

        return web.Response(body=obj.data, content_type=obj.content_type) if obj else web.Response(status=400)

    async def post_binary_data(self, request: Request):
        post_body = await request.read()
        with db_session:
            obj = self.session.mds.BinaryData(data=post_body)

        return web.Response(status=201)
