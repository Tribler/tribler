from os import getenv
from os.path import join, exists
from sh import mkdir, cp
from pythonforandroid.toolchain import PythonRecipe, current_directory


class LocalTriblerRecipe(PythonRecipe):
    """
    Privacy with BitTorrent and resilient to shut down

    http://www.tribler.org
    """

    src_root = getenv('WORKSPACE', '/home/paul/repos/tribler-app')

    version = 'local'

    depends = ['apsw', 'cryptography', 'libsodium', 'libtorrent', 'm2crypto',
               'netifaces', 'openssl', 'pil', 'pycrypto', 'pyleveldb', 'python2',
               'setuptools', 'twisted', 'coverage', #'vlc',  #'ffmpeg',
              ]

    python_depends = ['chardet', 'cherrypy', 'configobj', 'decorator', 'feedparser',
                      'libnacl', 'pyasn1', 'six', 'nose', 'nosexcover',
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
            cp('-rf', self.src_root, self.name)

        super(LocalTriblerRecipe, self).prebuild_arch(arch)


    def postbuild_arch(self, arch):
        super(LocalTriblerRecipe, self).postbuild_arch(arch)

        # Install twistd plugins
        cp('-rf', join(self.get_build_dir(arch.arch), 'twisted'),
           join(self.ctx.get_python_install_dir(), 'lib/python2.7/site-packages'))

        # Install ffmpeg binary
        source = self.get_recipe('ffmpeg', self.ctx).get_build_bin(arch)
        target = join(self.src_root, 'android/TriblerService/service/ffmpeg')
        if not exists(target):
            cp('-f', source, target)


recipe = LocalTriblerRecipe()
