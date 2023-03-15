""" A helper mocking function to mask ImportError on a scoped code.
Failed imports will be ignored.

This module has been copied from https://github.com/posener/mock-import and modified by @drew2a
to allow `mock_import` ignore only packages included to the `packages` list.

Original module distributes under Apache License 2.0.
"""
import builtins
from typing import List, Union
from unittest.mock import MagicMock, patch

__all__ = ['patch_import']

_builtins_import = builtins.__import__


def patch_import(modules=Union[List[str], str], strict: bool = False, always_raise_exception_on_import=False,
                 **mock_kwargs):
    """
    Mocks import statement, and disable ImportError if a module
    could not be imported.
    :param modules: a list of prefixes of modules that should
        be mocked, and an ImportError could not be raised for.
    :param strict: If `strict` is equal to True, then whenever importing module exists or not, it will be replaced
        by MagicMock. If `strict` is equal to False, then the real module will be return in case it is exist, and
        MagicMock in case the module doesn't exist.
    :param always_raise_exception_on_import: if set to True, then the import of the particular module always will raise
        the ImportError
    :param mock_kwargs: kwargs for MagicMock object.
    :return: patch object
    """
    if isinstance(modules, str):
        modules = [modules]

    def try_import(module_name, *args, **kwargs):
        is_the_target_module = any((module_name == m or module_name.startswith(m + '.') for m in modules))

        if not is_the_target_module:
            return _builtins_import(module_name, *args, **kwargs)

        if always_raise_exception_on_import:
            raise ImportError

        if strict:
            return MagicMock(**mock_kwargs)

        try:
            return _builtins_import(module_name, *args, **kwargs)
        except ImportError:
            return MagicMock(**mock_kwargs)

    return patch('builtins.__import__', try_import)
