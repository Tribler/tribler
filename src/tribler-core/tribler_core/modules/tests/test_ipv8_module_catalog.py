from tribler_core.modules.ipv8_module_catalog import get_hiddenimports


def test_hiddenimports():
    """
    Check if all hidden imports are detected
    """
    assert not get_hiddenimports()
