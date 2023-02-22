from unittest.mock import MagicMock

from tribler.gui.network.request import Request


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


def test_on_finished():
    # Test that if 'request.reply' is empty, the `on_finish` method is called with an empty dict.
    # see: https://github.com/Tribler/tribler/issues/7297
    on_finish = MagicMock()
    request = Request(endpoint='endpoint', on_finish=on_finish)
    request.manager = MagicMock()
    request.reply = MagicMock(readAll=MagicMock(return_value=b''))

    request.on_finished()

    on_finish.assert_called_once_with({})
