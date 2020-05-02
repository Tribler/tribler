from asyncio import get_event_loop
from unittest.mock import Mock

import aiohttp

import yaml

from tribler_core.restapi.rest_manager import RESTManager


async def start_api():
    session = Mock()
    session.config.get_http_api_key = lambda: 'apikey'
    session.config.get_http_api_port = lambda: 8085
    api_manager = RESTManager(session)
    await api_manager.start()


async def download_api_spec(destination_fn):
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        response = await session.get('http://127.0.0.1:8085/docs/swagger.json')
        api_spec = await response.json()

    # Fix circular definition (as sphinxcontrib-openapi can't handle it)
    api_spec['definitions']['Block']['properties']['linked'] = {'description': 'Nested Block'}
    # All responses should have a description
    for _, path in api_spec['paths'].items():
        for _, spec in path.items():
            for _, response in spec['responses'].items():
                if 'description' not in response:
                    response['description'] = ''
    # Convert to yaml
    with open(destination_fn, 'w') as destination_fp:
        destination_fp.write(yaml.dump(api_spec))


async def extract_swagger(destination_fn):
    await start_api()
    await download_api_spec(destination_fn)


if __name__ == '__main__':
    loop = get_event_loop()
    loop.run_until_complete(extract_swagger('restapi/swagger.yaml'))
