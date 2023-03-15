"""
This file lists the python dependencies for Tribler.

Note that this file should not depend on any external modules itself other than builtin ones.
"""
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional

import tribler

# fmt: off

logger = logging.getLogger(__name__)


class Scope(Enum):
    core = 'core'
    gui = 'gui'


# Exceptional pip packages where the name does not match with actual import.
package_to_import_mapping = {
    'Faker': 'faker',
}


def get_dependencies(scope: Scope) -> Iterator[str]:
    requirements_path = _get_path_to_requirements_txt(scope)
    return _get_pip_dependencies(requirements_path)


def _get_path_to_requirements_txt(scope: Scope) -> Path:
    root_path = Path(tribler.__file__).parent.parent.parent
    if scope == Scope.core:
        return root_path / 'requirements-core.txt'
    if scope == Scope.gui:
        return root_path / 'requirements.txt'
    raise AttributeError(f'Scope is {scope} but should be in {list(Scope)}')


def _get_pip_dependencies(path_to_requirements: Path) -> Iterator[str]:
    logger.info(f'Getting dependencies from: {path_to_requirements}')
    requirements_text = path_to_requirements.read_text()
    return _extract_libraries_from_requirements(requirements_text)


def _extract_libraries_from_requirements(text: str) -> Iterator[str]:
    logger.debug(f'requirements.txt content: {text}')
    for line in text.split('\n'):
        package = _extract_package_from_line(line)
        if package:
            yield package


def _extract_package_from_line(line) -> Optional[str]:
    without_comment = line.partition('#')[0].strip()
    without_version = re.split(r'[><=~]', without_comment, maxsplit=1)[0]
    with_underscores = without_version.replace('-', '_')
    package = package_to_import_mapping.get(with_underscores, with_underscores)
    return package or None
