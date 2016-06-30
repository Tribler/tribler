from distutils.core import setup
from Tribler.Core.version import version_id


with open('README.rst', 'r') as f:
    long_description = f.read()

with open('Tribler/LICENSE.txt', 'r') as f:
    licenses = f.read()

packages = [
    'Tribler',
    'Tribler.Category',
    'Tribler.Core',
    'Tribler.Core.APIImplementation',
    'Tribler.Core.CacheDB',
    'Tribler.Core.Config',
    'Tribler.Core.DecentralizedTracking',
    'Tribler.Core.DecentralizedTracking.pymdht',
    'Tribler.Core.DecentralizedTracking.pymdht.core',
    'Tribler.Core.DecentralizedTracking.pymdht.plugins',
    'Tribler.Core.DecentralizedTracking.pymdht.profiler',
    'Tribler.Core.DecentralizedTracking.pymdht.profiler.parsers',
    'Tribler.Core.DecentralizedTracking.pymdht.ui',
    'Tribler.Core.DecentralizedTracking.pymdht.ut2mdht',
    'Tribler.Core.Libtorrent',
    'Tribler.Core.Modules',
    'Tribler.Core.Modules.channel',
    'Tribler.Core.Modules.restapi',
    'Tribler.Core.Modules.restapi.channels',
    'Tribler.Core.TFTP',
    'Tribler.Core.TorrentChecker',
    'Tribler.Core.Upgrade',
    'Tribler.Core.Utilities',
    'Tribler.Core.Video',
    'Tribler.Main',
    'Tribler.Main.Dialogs',
    'Tribler.Main.Emercoin',
    'Tribler.Main.Utility',
    'Tribler.Main.vwxGUI',
    'Tribler.Main.webUI',
    'Tribler.Policies',
    'Tribler.Utilities',
    'Tribler.community',
    'Tribler.community.allchannel',
    'Tribler.community.bartercast4',
    'Tribler.community.channel',
    'Tribler.community.demers',
    'Tribler.community.multichain',
    'Tribler.community.search',
    'Tribler.community.template',
    'Tribler.community.tunnel',
    'Tribler.community.tunnel.Socks5',
    'Tribler.community.tunnel.crypto',
    'Tribler.dispersy',
    'Tribler.dispersy.discovery',
    'Tribler.dispersy.libnacl.libnacl',
    'Tribler.dispersy.tool',
    'Tribler.dispersy.tracker',
]

test_suite = [
    'Tribler.dispersy.tests',
    'Tribler.dispersy.tests.debugcommunity',
    'Tribler.Test',
    'Tribler.Test.API',
    'Tribler.Test.Category',
    'Tribler.Test.Category.data.Tribler.Category',
    'Tribler.Test.Community',
    'Tribler.Test.Community.Bartercast',
    'Tribler.Test.Community.Multichain',
    'Tribler.Test.Community.Tunnel',
    'Tribler.Test.Core',
    'Tribler.Test.Core.data.config_files',
    'Tribler.Test.Core.data.libtorrent',
    'Tribler.Test.Core.data.sqlite_scripts',
    'Tribler.Test.Core.data.torrent_creation_files',
    'Tribler.Test.Core.data.upgrade_databases',
    'Tribler.Test.Core.Libtorrent',
    'Tribler.Test.Core.Modules',
    'Tribler.Test.Core.Modules.channel',
    'Tribler.Test.Core.Modules.Channel',
    'Tribler.Test.Core.Modules.RestApi',
    'Tribler.Test.Core.Modules.RestApi.Channels',
    'Tribler.Test.Core.Upgrade',
    'Tribler.Test.data',
    'Tribler.Test.data.41aea20908363a80d44234e8fef07fab506cd3b4',
    'Tribler.Test.data.contentdir',
]

setup(
    name='libtribler',
    description='Tribler core functionality package',
    long_description=long_description,
    license=licenses,
    version=str(version_id),
    url='https://github.com/Tribler/tribler',
    author='Tribler team from Delft University of Technology',
    package_data={
        'Tribler': [
            'schema_sdb_v28.sql',
            'anon_test.torrent'],
        'Tribler.Category': [
            'filter_terms.filter',
            'category.conf'],
        'Tribler.Core.DecentralizedTracking.pymdht.core': [
            'bootstrap_stable',
            'bootstrap_unstable'],
    },
    packages=packages,
)
