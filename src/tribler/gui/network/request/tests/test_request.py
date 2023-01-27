from tribler.gui.network.request.request import Request


def test_default_constructor():
    request = Request(
        endpoint='endpoint'
    )
    assert request


def test_dict_data_constructor():
    """ Test that data becomes raw_data as an encoded json
    """
    request = Request(
        endpoint='endpoint',
        data={
            'key': 'value'
        }
    )
    assert request.raw_data == b'{"key": "value"}'


def test_bytes_data_constructor():
    request = Request(
        endpoint='endpoint',
        data=b'bytes'
    )
    assert request.raw_data == b'bytes'


def test_str_data_constructor():
    request = Request(
        endpoint='endpoint',
        data='str'
    )
    assert request.raw_data == b'str'
