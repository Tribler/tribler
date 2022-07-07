import json
import logging
from asyncio import get_event_loop
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import aiohttp
import yaml

from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.restapi.restapi_component import RESTComponent
from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig


async def extract_swagger(destination):
    logging.info(f'Extract swagger for "{destination}"')
    config = TriblerConfig(state_dir=Path('.'))
    config.api.http_enabled = True
    config.api.http_port = 8080

    rest_component = RESTComponent()
    rest_component.swagger_doc_extraction_mode = True

    async with Session(config, [ReporterComponent(), rest_component], failfast=False):
        fp = StringIO()
        proto = aiohttp.web_protocol.RequestHandler(rest_component.rest_manager.runner._server, loop=get_event_loop())
        proto.connection_made(Mock(is_closing=lambda: False, write=lambda b: fp.write(b.decode())))
        proto.data_received(b'GET /docs/swagger.json HTTP/1.1\r\n'
                            b'Connection: close\r\n\r\n')
        await proto.start()
        logging.info('Proto has been started.')

        response = fp.getvalue()
        logging.info(f'Response size: {len(response)}')
        logging.debug(f'Response content: {response}')

    api_spec = json.loads(response.split('\r\n\r\n')[1])
    logging.debug(f'API spec content: {api_spec}')

    # All responses should have a description
    for _, path in api_spec['paths'].items():
        for _, spec in path.items():
            for _, response in spec['responses'].items():
                if 'description' not in response:
                    response['description'] = ''
    # Convert to yaml
    with open(destination, 'w') as f:
        f.write(yaml.dump(api_spec))


if __name__ == '__main__':
    loop = get_event_loop()
    loop.run_until_complete(extract_swagger('restapi/swagger.yaml'))
