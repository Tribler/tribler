"""
This file lists the python dependencies for Tribler.

Note that this file should not depend on any external modules itself other than builtin ones.
"""
import importlib
import logging
import re
import sys
from enum import Enum
from typing import Iterator

import pkg_resources

from tribler_common.utilities import show_system_popup

from tribler_core.utilities.path_util import Path

logger = logging.getLogger(__name__)

Scope = Enum('Scope', 'core gui common')


# pylint: disable=import-outside-toplevel
def check_for_missing_dependencies(scope: Scope):
    """
    Checks modules installed with pip, especially via linux post installation script.
    Program exits with a dialog if there are any missing dependencies.

    :param scope: Defines the scope of the dependencies. Can have two values: Scope.core and Scope.gui.
    """
    logger.info(f'Check for missing dependencies. Scope: {scope}')
    if scope == Scope.core:
        check_for_libtorrent()

    check_for_pip_dependencies(scope)


def check_for_pip_dependencies(scope: Scope):
    missed_pip_dependencies = ", ".join(get_missed(scope))
    text = f'These libraries require installation via pip: [{missed_pip_dependencies}]'

    if missed_pip_dependencies:
        show_system_popup("Dependencies missing!", f"Found missing dependencies in {scope}!\n" + text)
        return

    logger.info('Requirements are satisfied.')


def check_for_libtorrent():
    try:
        importlib.import_module('libtorrent')
        return
    except ImportError:
        pass

    error_text = 'libtorrent for python should be installed.'
    logger.error(error_text)
    show_system_popup("Dependencies missing!", error_text)
    sys.exit(1)


def get_dependencies(scope: Scope) -> Iterator[str]:
    requirements = 'requirements.txt'
    if scope == Scope.core:
        import tribler_core

        return _get_pip_dependencies(Path(tribler_core.__file__).parent / requirements)
    if scope == Scope.gui:
        import tribler_gui

        return _get_pip_dependencies(Path(tribler_gui.__file__).parent / requirements)
    if scope == Scope.common:
        import tribler_common

        return _get_pip_dependencies(Path(tribler_common.__file__).parent / requirements)
    raise ValueError(f'Scope should be one of {list(Scope)}')


def get_missed(scope: Scope) -> Iterator[str]:
    installed_dependencies = {
        package.key.lower() for package in pkg_resources.working_set  # pylint: disable=not-an-iterable
    }
    logger.debug(f'Installed dependencies: {installed_dependencies}')

    for dependency in get_dependencies(scope):
        if dependency.lower() not in installed_dependencies:
            logger.error(f'Missed dependency: {dependency}')
            yield dependency


def _extract_libraries_from_requirements(text: str) -> Iterator[str]:
    logger.debug(f'requirements.txt content: {text}')
    for library in filter(None, text.split('\n')):
        yield re.split(r'[><=~]', library, maxsplit=1)[0]


def _get_pip_dependencies(path_to_requirements: Path) -> Iterator[str]:
    logger.info(f'Getting dependencies from: {path_to_requirements}')
    return _extract_libraries_from_requirements(path_to_requirements.read_text())
