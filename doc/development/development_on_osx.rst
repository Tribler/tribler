Tribler development environment setup on MacOS (10.10 to 10.12).

1. `MacPorts <development_on_osx.rst#macports>`_
2. `HomeBrew <development_on_osx.rst#homebrew>`_
3. `Tribler <development_on_osx.rst#tribler>`_
4. `Notes <development_on_osx.rst#notes>`_

MacPorts
--------

MacPorts Install instructions at `macports.org <https://www.macports.org>`_.
To install the Tribler dependencies using MacPorts, please run the following command in your terminal:

.. code-block:: bash

    sudo port -N install git ffmpeg qt5-qtcreator libtorrent-rasterbar gmp mpfr libmpc libsodium py27-m2crypto py27-apsw py27-Pillow py27-twisted py27-cherrypy3 py27-cffi py27-chardet py27-configobj py27-gmpy2 py27-pycparser py27-numpy py27-idna py27-leveldb py27-cryptography py27-decorator py27-feedparser py27-netifaces py27-service_identity py27-asn1-modules py27-pyinstaller py27-pyqt5 py27-sqlite py27-matplotlib
    
HomeBrew
--------

Note
~~~~

Skip to `Tribler <development_on_osx.rst#tribler>`_ if you are using MacPorts because HomeBrew is a less complete alternative to MacPorts.

HomeBrew installation instructions can be found at `brew.sh <https://brew.sh>`_.

PyQt5
~~~~~

If you wish to run the Tribler Graphical User Interface, PyQt5 should be available on the system. While PyQt5 is available in the pip repository, this is only compatible with Python 3. To install PyQt5, we first need to install Qt5, a C++ library which can be installed with brew:

.. code-block:: none

    brew install qt5
    brew cask install qt-creator # if you want the visual designer
    qmake --version # test whether qt is installed correctly

After the installation completed, PyQt5 should be compiled. This library depends on SIP, another library to automatically generate Python bindings from C++ code. Download the latest SIP version `here <https://www.riverbankcomputing.com/software/sip/download>`_, extract it, navigate to the directory where it has been extracted and compile/install it:

.. code-block:: none

    python configure.py
    make
    sudo make install

Next, download PyQt5 from `here <https://sourceforge.net/projects/pyqt/files/PyQt5/>`_ and make sure that you download the version that matches with the version of Qt you installed in the previous steps. Extract the binary and compile it:

.. code-block:: none

    python configure.py
    make
    sudo make install
    python -c "import PyQt5" # this should work without any error

Note that the installation can take a while. After it has finished, the PyQt5 library is installed correctly.

M2Crypto
~~~~~~~~

To install M2Crypto, Openssl has to be installed first. The shipped version of openssl by Apple gives errors when compiling M2Crypto so a self-compiled version should be used. Start by downloading openssl 0.98 from `here <https://www.openssl.org/source/>`_, extract it and install it:

.. code-block:: none

    ./config --prefix=/usr/local
    make && make test
    sudo make install
    openssl version # this should be 0.98

Also Swig 3.0.4 is required for the compilation of the M2Crypto library. The easiest way to install it, it to download Swig 3.0.4 from source `here <http://www.swig.org/download.html>`_ and compile it using:

.. code-block:: none

    ./configure
    make
    sudo make install

Note: if you get an error about a missing PCRE library, install it with brew using ``brew install pcre``.

Now we can install M2Crypto. First download the `source <http://chandlerproject.org/Projects/MeTooCrypto>`_ (version 0.22.3 is confirmed to work on El Capitan and Yosemite) and install it:

.. code-block:: none

    python setup.py build build_ext --openssl=/usr/local
    sudo python setup.py install build_ext --openssl=/usr/local

Reopen your terminal window and test it out by executing:

.. code-block:: none

    python -c "import M2Crypto"

Apsw
~~~~

Apsw can be installed by brew but this does not seem to work to compile the last version (the Clang compiler uses the ``sqlite.h`` include shipped with Xcode which is outdated). Instead, the source should be downloaded from their `Github repository <https://github.com/rogerbinns/apsw>`_ (make sure to download a release version) and compiled using:

.. code-block:: none

    sudo python setup.py fetch --all build --enable-all-extensions install test
    python -c "import apsw" # verify whether apsw is successfully installed

Libtorrent
~~~~~~~~~~

An essential dependency of Tribler is libtorrent. libtorrent is dependent on Boost, a set of C++ libraries. Boost can be installed with the following command:

.. code-block:: none

    brew install boost
    brew install boost-python

Now we can install libtorrent:

.. code-block:: none

    brew install libtorrent-rasterbar --with-python

After the installation, we should add a pointer to the ``site-packages`` of Python so it can find the new libtorrent library using the following command:

.. code-block:: none

    sudo echo 'import site; site.addsitedir("/usr/local/lib/python2.7/site-packages")' >> /Library/Python/2.7/site-packages/homebrew.pth

This command basically adds another location for the Python site-packages (the location where libtorrent-rasterbar is installed). This command should be executed since the location where brew installs the Python packages is not in sys.path. You can test whether libtorrent is correctly installed by executing:

.. code-block:: none

    python
    >>> import libtorrent

Other Packages
~~~~~~~~~~~~~~

There are a bunch of other packages that can easily be installed using pip and brew:

.. code-block:: none

    brew install homebrew/python/pillow gmp mpfr libmpc libsodium
    sudo easy_install pip
    pip install --user cherrypy cffi chardet configobj cryptography decorator dnspython ecdsa feedparser gmpy2 jsonrpclib idna keyring leveldb netifaces numpy pbkdf2 pillow protobuf pyasn1 pysocks pycparser requests twisted service_identity

If you encounter any error during the installation of Pillow, make sure that libjpeg and zlib are installed. They can be installed using:

.. code-block:: none

    brew tap homebrew/dupes
    brew install libjpeg zlib
    brew link --force zlib

Tribler
-------

.. code-block:: bash

    git clone --recursive  https://github.com/Tribler/tribler.git
    cd tribler
    cp /usr/local/lib/libsodium.dylib ./ || cp /opt/local/lib/libsodium.dylib ./
    mkdir vlc
    which ffmpeg | xargs -I {} cp "{}" vlc/
    
Proceed proceed to `Build instructions <../building/building_on_osx.rst>`_

Notes
-----

System Integrity Protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The security system on MacOS can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python. If this library cannot be loaded, it gives an error that libsodium could not be found. This is because the ``DYLD_LIBRARY_PATH`` cannot be set when Python starts. More information about this can be read `here <https://forums.developer.apple.com/thread/13161>`_.

The best solution to this problem is to link or copy ``libsodium.dylib`` into the Tribler root directory.

Help
~~~~

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
