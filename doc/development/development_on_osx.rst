This section contains information about setting up a Tribler development environment on macOS. Unlike Linux based systems where installing third-party libraries is often a single ``apt-get`` command, installing and configuring the necessary libraries requires more attention on macOS. This guide has been tested with macOS 10.10.5 (Yosemite) but should also work for macOS 10.11 (El Capitan).

Note that the guide below assumes that Python is installed in the default location of Python (shipped with macOS). This location is normally in ``/Library/Python/2.7``. Writing to this location requires root access when using easy_install or pip. To avoid root commands, you can install Python in a virtualenv. More information about setting up Python in a virtualenv can be found `here <http://www.marinamele.com/2014/05/install-python-virtualenv-virtualenvwrapper-mavericks.html>`_.

Introduction
------------

Compilation of C/C++ libraries should be performed using Clang which is part of the Xcode Command Line Tools. The Python version shipped with macOS can be used and this guide has been tested using Python 2.7. The current installed version and binary of Python can be found by executing:

.. code-block:: none

    python --version # gets the python version
    which python # prints the path of the Python executable

Note that the default location of third-party Python libraries (for example, installed with ``pip``) can be found in ``/Library/Python/2.7/site-packages``.

Many packages can be installed by using the popular brew and pip executables. Brew and pip can be installed by using:

.. code-block:: none

    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    sudo easy_install pip

This should be done after accepting the Xcode license so open Xcode at least once before installing Brew.

Xcode Tools
-----------

The installation of Xcode is required in order to compile some C/C++ libraries. Xcode is an IDE developed by Apple and can be downloaded for free from the Mac App Store. After installation, the Command Line Tools should be installed by executing:

.. code-block:: none

    xcode-select --install

PyQt5
-----

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
--------

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
----

Apsw can be installed by brew but this does not seem to work to compile the last version (the Clang compiler uses the ``sqlite.h`` include shipped with Xcode which is outdated). Instead, the source should be downloaded from their `Github repository <https://github.com/rogerbinns/apsw>`_ (make sure to download a release version) and compiled using:

.. code-block:: none

    sudo python setup.py fetch --all build --enable-all-extensions install test
    python -c "import apsw" # verify whether apsw is successfully installed

Libtorrent
----------

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
--------------

There are a bunch of other packages that can easily be installed using pip and brew:

.. code-block:: none

    brew install homebrew/python/pillow gmp mpfr libmpc libsodium
    pip install --user cherrypy cffi chardet configobj cryptography decorator feedparser gmpy2 idna leveldb netifaces numpy pillow pyasn1 pycparser twisted service_identity

If you encounter any error during the installation of Pillow, make sure that libjpeg and zlib are installed. They can be installed using:

.. code-block:: none

    brew tap homebrew/dupes
    brew install libjpeg zlib
    brew link --force zlib

Tribler should now be able to startup without warnings by executing this command in the Tribler root directory:

.. code-block:: none

    ./tribler.sh

If there are any missing packages, they can often be installed by one pip or brew command. If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.

System Integrity Protection on El Capitan
-----------------------------------------

The new security system in place in El Capitan can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python. If this library cannot be loaded, it gives an error that libsodium could not be found. This is because the ``DYLD_LIBRARY_PATH`` cannot be set when Python starts. More information about this can be read `here <https://forums.developer.apple.com/thread/13161>`_.

There are two solutions for this problem. First, ``libsodium.dylib`` can symlinked into the Tribler root directory. This can be done by executing the following command **in the Tribler root directory**:

.. code-block:: none

    ln -s /usr/local/lib/libsodium.dylib

Now the ``ctypes`` Python library will be able to find the ``libsodium.dylib`` file.

The second solution is to disable SIP. This is not recommended since it makes the system more vulnerable for attacks. Information about disabling SIP can be found `here <http://www.imore.com/el-capitan-system-integrity-protection-helps-keep-malware-away>`_.
