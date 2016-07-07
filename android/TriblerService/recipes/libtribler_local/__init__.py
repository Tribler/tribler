from pythonforandroid.toolchain import PythonRecipe, shutil, current_directory
from os.path import join
from sh import mkdir, cp

"""
Privacy with BitTorrent and resilient to shut down

http://www.tribler.org
"""
class LocalTriblerRecipe(PythonRecipe):

    version = 'local'

    depends = ['apsw', 'cryptography', 'ffmpeg', 'libsodium', 'libtorrent', 'm2crypto',
               'netifaces', 'openssl', 'pil', 'pycrypto', 'pyleveldb', 'python2',
               'setuptools', 'twisted',
              ]

    python_depends = ['chardet', 'cherrypy', 'configobj', 'decorator', 'feedparser',
                      'libnacl', 'pyasn1', 'six',
                     ]

    site_packages_name = 'Tribler'
    
    call_hostpython_via_targetpython = False


    def should_build(self, arch):
        # Overwrite old build
        return True


    def prebuild_arch(self, arch):
        # Remove from site-packages
        super(LocalTriblerRecipe, self).clean_build(arch.arch)

        # Create empty build dir
        container_dir = self.get_build_container_dir(arch.arch)
        mkdir('-p', container_dir)

        with current_directory(container_dir):
            # Copy source from working copy
            cp('-rf', '/home/paul/repos/tribler-app', self.name)

            # Copy twisted plugin
            shutil.copyfile(join(self.name, 'twisted/plugins/tribler_plugin.py'),
                            '/home/paul/repos/tribler-app/android/TriblerService/service/tribler_plugin.py')

        super(LocalTriblerRecipe, self).prebuild_arch(arch)


    def postbuild_arch(self, arch):
        super(LocalTriblerRecipe, self).postbuild_arch(arch)
        # Install ffmpeg binary
        shutil.copyfile(self.get_recipe('ffmpeg', self.ctx).get_build_bin(arch),
                        '/home/paul/repos/tribler-app/android/TriblerService/service/ffmpeg')


recipe = LocalTriblerRecipe()