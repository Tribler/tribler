Tribler development environment setup on MacOS (10.10 to 10.13).

1. `MacPorts <development_on_osx.rst#macports>`_
2. `HomeBrew <development_on_osx.rst#homebrew>`_
3. `Tribler <development_on_osx.rst#tribler>`_
4. `Notes <development_on_osx.rst#notes>`_

MacPorts
--------

MacPorts Install instructions at `macports.org <https://www.macports.org>`_.
To install the Tribler dependencies using MacPorts, please run the following command in your terminal:

.. code-block:: bash

    sudo port -N install git ffmpeg qt5-qtcreator libtorrent-rasterbar gmp mpfr libmpc libsodium py27-Pillow py27-twisted \
    py27-cherrypy3 py27-cffi py27-chardet py27-configobj py27-gmpy2 py27-pycparser py27-numpy py27-idna py27-cryptography \
    py27-decorator py27-netifaces py27-service_identity py27-asn1-modules py27-pyinstaller py27-pyqt5 py27-sqlite py27-matplotlib py27-libnacl
    
HomeBrew
--------

Note
~~~~

Skip to `Tribler <development_on_osx.rst#tribler>`_ if you are using MacPorts because HomeBrew is a less complete alternative to MacPorts.

HomeBrew installation instructions can be found at `brew.sh <https://brew.sh>`_.

PyQt5
~~~~~

If you wish to run the Tribler Graphical User Interface, PyQt5 should be available on the system. While PyQt5 is available in the pip repository, this is only compatible with Python 3. To install PyQt5, we first need to install Qt5, a C++ library which can be installed with brew:

.. code-block:: bash

    brew install qt5, sip, pyqt5
    brew cask install qt-creator # if you want the visual designer
    qmake --version # test whether qt is installed correctly

Libtorrent
~~~~~~~~~~

An essential dependency of Tribler is libtorrent. libtorrent is dependent on Boost, a set of C++ libraries. Boost can be installed with the following command:

.. code-block:: bash

    brew install boost
    brew install boost-python

By default libtorrent is installed with ``python3``. To install it with ``python2`` you need to do following:

.. code-block:: bash

   brew edit libtorrent-rasterbar


Change the lines of ``args`` from

.. code-block:: bash

    --with-boost-python=boost_python37-mt
    PYTHON=python3

to

.. code-block:: bash

    --with-boost-python=boost_python27-mt
    PYTHON=python2.7


After that you can install it with

.. code-block:: bash

    brew install libtorrent-rasterbar


For the final check you can test whether libtorrent is correctly installed by executing:

.. code-block:: bash

    python
    >>> import libtorrent

Other Packages
~~~~~~~~~~~~~~

There are a bunch of other packages that can easily be installed using pip and brew:

.. code-block:: bash

    brew install homebrew/python/pillow gmp mpfr libmpc libsodium
    sudo easy_install pip
    pip install --user cython  # Needs to be installed first for meliae
    pip install --user bitcoinlib cherrypy cffi chardet configobj cryptography decorator gmpy2 idna libnacl lz4 \
    meliae netifaces numpy pillow psutil pyasn1 pycparser scipy pyopenssl Twisted==16.4.1 networkx service_identity typing

If you encounter any error during the installation of Pillow, make sure that libjpeg and zlib are installed. They can be installed using:

.. code-block:: bash

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
