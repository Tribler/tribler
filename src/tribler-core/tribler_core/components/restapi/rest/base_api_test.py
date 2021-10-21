import json
from json import JSONDecodeError

from aiohttp import ClientSession

from tribler_core.components.restapi.rest import get_param
from tribler_core.utilities.path_util import Path
from tribler_core.version import version_id


def path_to_str(obj):
    if isinstance(obj, dict):
        return {path_to_str(k): path_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [path_to_str(i) for i in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


async def do_real_request(port, endpoint, expected_code=200, expected_json=None,
                          request_type='GET', post_data=None, headers=None, json_response=True):
    post_data = post_data or {}
    data = json.dumps(path_to_str(post_data)) if isinstance(post_data, (dict, list)) else post_data
    is_url = endpoint.startswith('http://') or endpoint.startswith('https://')
    url = endpoint if is_url else f'http://localhost:{port}/{endpoint}'
    headers = headers or {'User-Agent': 'Tribler ' + version_id}

    async with ClientSession() as session:
        async with session.request(request_type, url, data=data, headers=headers, ssl=False) as response:
            status, response = response.status, (await response.json(content_type=None)
                                                 if json_response else await response.read())
            assert status == expected_code, response
            if response is not None and expected_json is not None:
                assert expected_json == response
            return response


async def do_request(test_client, url, expected_code=200, expected_json=None,
                     request_type='GET', post_data=None, headers=None, json_response=True):
    post_data = post_data or {}
    data = json.dumps(path_to_str(post_data)) if isinstance(post_data, (dict, list)) else post_data
    headers = headers or {'User-Agent': 'Tribler ' + version_id}

    async with test_client.request(request_type, url, data=data, headers=headers, ssl=False) as response:
        status = response.status
        try:
            response = (await response.json(content_type=None)
                        if json_response else await response.read())
        except JSONDecodeError:
            response = None

        if status == 500 and expected_code != 500:
            if 'message' in response['error']:
                print(response['error']['message'])
            else:
                print(response['error'])
        assert status == expected_code, response
        if response is not None and expected_json is not None:
            assert response == expected_json
        return response


def test_get_parameters():
    """
    Test the get_parameters method
    """
    parameters = {'abc': [3]}
    assert get_param(parameters, 'abcd') is None
    assert get_param(parameters, 'abc') is not None
