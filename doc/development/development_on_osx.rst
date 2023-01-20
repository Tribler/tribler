Tribler development environment setup on MacOS (10.10 to latest).
    
HomeBrew
--------

This guide will outline how to setup a Tribler development environment on Mac.

PyQt5
~~~~~

If you wish to run the Tribler Graphical User Interface, PyQt5 should be available on the system. To install PyQt5, we first need to install Qt5, a C++ library which can be installed with Brew:

.. code-block:: bash

    brew install python3 qt5 sip pyqt5
    brew cask install qt-creator # if you want the visual designer
    brew link qt5 --force # to allow access qmake from the terminal

    qmake --version # test whether qt is installed correctly


Other Packages
~~~~~~~~~~~~~~

There are a bunch of other packages that can easily be installed using pip and brew:

.. code-block:: bash

    brew install gmp mpfr libmpc libsodium
    python3 -m pip install -r requirements.txt

Tribler
-------

The security system on MacOS can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python. If this library cannot be loaded, it gives an error that libsodium could not be found. This is because the ``DYLD_LIBRARY_PATH`` cannot be set when Python starts. More information about this can be read `here <https://forums.developer.apple.com/thread/13161>`__.

The best solution to this problem is to link or copy ``libsodium.dylib`` into the Tribler root directory.

.. code-block:: bash

    git clone  https://github.com/Tribler/tribler.git
    cd tribler
    cp /usr/local/lib/libsodium.dylib ./ || cp /opt/local/lib/libsodium.dylib ./

You can now run Tribler by executing the following bash script in the ``src`` directory:

.. code-block:: bash

    ./tribler.sh

Proceed proceed to `Build instructions <../building/building_on_osx.rst>`_

Help
~~~~

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.

Apple Silicon
-------
There are currently no python bindings available to install from pip.
Therefore you need to build them from source.

To do this, please install openssl and boost first:

.. code-block:: bash
    brew install openssl boost boost-build boost-python3

And then follow the `instruction <https://github.com/arvidn/libtorrent/blob/v1.2.18/docs/python_binding.rst>`_.

This instruction was checked for the following versions:

* python 3.11
* libtorrent 1.2.18