from distutils.core import setup
from Tribler.Core.version import version_id

setup(
    name='libtribler',
    version=str(version_id),
    author='Tribler',
    packages=['Tribler', 'Tribler.Category', 'Tribler.community', 'Tribler.community.allchannel', 'Tribler.community.bartercast4', 'Tribler.community.tunnel', 'Tribler.community.tunnel.Socks5', 'Tribler.community.tunnel.crypto', 'Tribler.community.channel', 'Tribler.community.demers', 'Tribler.community.metadata', 'Tribler.community.search', 'Tribler.community.template', 'Tribler.Core', 'Tribler.Core.APIImplementation', 'Tribler.Core.CacheDB', 'Tribler.Core.DecentralizedTracking', 'Tribler.Core.DecentralizedTracking.pymdht', 'Tribler.Core.DecentralizedTracking.pymdht.core', 'Tribler.Core.DecentralizedTracking.pymdht.plugins', 'Tribler.Core.DecentralizedTracking.pymdht.profiler', 'Tribler.Core.DecentralizedTracking.pymdht.profiler.parsers', 'Tribler.Core.DecentralizedTracking.pymdht.ui', 'Tribler.Core.Libtorrent', 'Tribler.Core.TorrentChecker', 'Tribler.Core.Utilities', 'Tribler.Core.Video', 'Tribler.Core.TFTP', 'Tribler.dispersy', 'Tribler.dispersy.discovery', 'Tribler.dispersy.tests', 'Tribler.dispersy.tests.debugcommunity', 'Tribler.dispersy.libnacl', 'Tribler.Test', 'Tribler.Test.API', 'Tribler.Utilities', 'Tribler.Core.Upgrade', 'Tribler.Core.Modules', 'Tribler.Main', 'Tribler.Main.Utility'],
    url='https://github.com/Tribler/tribler',
    license='LICENSE.txt',
    description='AT3 package for Python for Android',
    package_data={'Tribler': ['schema_sdb_v27.sql', 'anon_test.torrent'],
                  'Tribler.Category' : ['filter_terms.filter', 'filter_terms.filter'],
                  'Tribler.Category' : ['category.conf', 'category.conf']},
    include_package_data=True,
    long_description='This is the core tribler functionality package which is used for the android app.',
)
