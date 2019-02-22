from __future__ import absolute_import

from setuptools import find_packages, setup

from Tribler.Core.version import version_id


with open('README.rst', 'r') as f:
    long_description = f.read()

with open('LICENSE', 'r') as f:
    licenses = f.read()

data_dirs = [
    'Tribler.Test.data',
    'Tribler.Test.data.41aea20908363a80d44234e8fef07fab506cd3b4',
    'Tribler.Test.data.contentdir',
    'Tribler.Test.Core.Category.data.Tribler.Core.Category',
    'Tribler.Test.Core.data',
    'Tribler.Test.Core.data.config_files',
    'Tribler.Test.Core.data.libtorrent',
    'Tribler.Test.Core.data.torrent_creation_files',
    'Tribler.Test.Core.data.upgrade_databases',
]

setup(
    name='libtribler',
    description='Tribler core functionality package',
    long_description=long_description,
    license=licenses,
    version=str(version_id),
    url='https://github.com/Tribler/tribler',
    author='Tribler team from Delft University of Technology',
    package_data={'': ['*.*']},
    packages=find_packages() + data_dirs,
)
