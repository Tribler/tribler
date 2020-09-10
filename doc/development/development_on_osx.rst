Tribler development environment setup on MacOS (10.10 to latest).
    
HomeBrew
--------

This guide will outline how to setup a Tribler development environment on Mac.

PyQt5
~~~~~

If you wish to run the Tribler Graphical User Interface, PyQt5 should be available on the system. To install PyQt5, we first need to install Qt5, a C++ library which can be installed with Brew:

.. code-block:: bash

    brew install python3, qt5, sip, pyqt5
    brew cask install qt-creator # if you want the visual designer
    brew link qt5 --force # to allow access qmake from the terminal

    qmake --version # test whether qt is installed correctly

Libtorrent
~~~~~~~~~~

You can install libtorrent with Brew using the following command:

.. code-block:: bash

    brew install libtorrent-rasterbar


To verify a correct installation, you can execute:

.. code-block:: bash

    python3
    >>> import libtorrent


**Symbol not found: _kSCCompAnyRegex** error

If you see `Symbol not found: _kSCCompAnyRegex` error, then follow
https://github.com/Homebrew/homebrew-core/pull/43858 for the explanation.

You can build libtorrent by yourself: http://libtorrent.org/python_binding.html
or by using this workaround from PR:

1. Edit brew formula:

.. code-block:: bash

    brew edit libtorrent-rasterbar

2. Add on the top of the `install` function `ENV.append` string as described below:

.. code-block:: bash

    def install
        ENV.append "LDFLAGS", "-framework SystemConfiguration -framework CoreFoundation"

3. Build `libtorrent-rasterbar` from source:

.. code-block:: bash

    brew install libtorrent-rasterbar --build-from-source


Other Packages
~~~~~~~~~~~~~~

There are a bunch of other packages that can easily be installed using pip3 and brew:

.. code-block:: bash

    brew install homebrew/python/pillow gmp mpfr libmpc libsodium
    pip3 install --user aiohttp aiohttp_apispec cffi chardet configobj cryptography decorator gmpy2 idna libnacl lz4 \
    netifaces networkx numpy pathlib pillow psutil pyasn1 pyopenssl pyqtgraph pyyaml

If you encounter any error during the installation of Pillow, make sure that libjpeg and zlib are installed. They can be installed using:

.. code-block:: bash

    brew tap homebrew/dupes
    brew install libjpeg zlib
    brew link --force zlib

To enable Bitcoin wallet management (optional), you should install the bitcoinlib library (support for this wallet is experimental):

.. code-block:: bash

    pip3 install bitcoinlib==0.4.10

Tribler
-------

The security system on MacOS can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python. If this library cannot be loaded, it gives an error that libsodium could not be found. This is because the ``DYLD_LIBRARY_PATH`` cannot be set when Python starts. More information about this can be read `here <https://forums.developer.apple.com/thread/13161>`__.

The best solution to this problem is to link or copy ``libsodium.dylib`` into the Tribler root directory.

.. code-block:: bash

    git clone --recursive  https://github.com/Tribler/tribler.git
    cd tribler
    cp /usr/local/lib/libsodium.dylib ./ || cp /opt/local/lib/libsodium.dylib ./

You can now run Tribler by executing the following bash script in the ``src`` directory:

.. code-block:: bash

    ./tribler.sh

Proceed proceed to `Build instructions <../building/building_on_osx.rst>`_

Help
~~~~

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
