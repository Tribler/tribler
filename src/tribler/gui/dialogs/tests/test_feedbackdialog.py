from unittest.mock import Mock, patch

from tribler.gui.dialogs.feedbackdialog import dump, dump_with_name


def test_dump_with_name_start():
    """ Test dump_with_name with a start value"""
    actual = dump_with_name('name', 'value', 'start')
    expected = ('start========================================\n'
                'name:\n'
                '========================================\n'
                "'value'")

    assert actual == expected


@patch('tribler.gui.dialogs.feedbackdialog.dump')
def test_dump_with_name_str(mock_dump: Mock):
    """ Test that dump_with_name calls the `dump` function"""
    dump_with_name('name', 'value')
    assert mock_dump.called


def test_dump_none():
    """ Test dump with a None value"""
    assert dump(None) == 'None'


def test_dump_dict():
    """ Test dump with a complex dict value"""
    actual = dump(
        {

            'key': {
                'key1': 'value1'
            },
            'key2': 'value2',
            'key3': ['value3', 'value4']
        }
    )

    expected = ('{\n'
                "  'key': {\n"
                "    'key1': 'value1'\n"
                '  },\n'
                "  'key2': 'value2',\n"
                "  'key3': [\n"
                "    'value3',\n"
                "    'value4'\n"
                '  ]\n'
                '}')

    assert actual == expected
