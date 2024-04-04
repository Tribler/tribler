Running Tribler from Source
===========================

In order to run Tribler from its source you will need to perform some setup.
We assume you have ``git`` and ``python`` installed.


Steps
-----

1. Clone the Tribler repo:

.. code-block:: bash

    git clone https://github.com/tribler/tribler
    
    
2. Install python packages:

.. code-block:: bash

    python -m pip install --upgrade -r tribler/requirements.txt

3. Run Tribler:

.. code-block:: bash

    cd src
    python run_tribler.py

Sometimes, you may run into platform-specific issues.
If this is your case, continue reading for your appropriate platform.


MacOS
-----

You may need to install QT5 and other packages separately:

.. code-block:: bash

    # QT5
    brew install python3 qt5 sip pyqt5
    brew cask install qt-creator  # if you want the visual designer
    brew link qt5 --force  # to allow access qmake from the terminal
    qmake --version  # test whether qt is installed correctly
    export PATH="/usr/local/opt/qt@5/bin:$PATH"
    
    # Other packages
    brew install gmp mpfr libmpc libsodium

The security system on MacOS can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python.
If this library cannot be loaded, it gives an error that libsodium could not be found.
You can link or copy ``libsodium.dylib`` into the Tribler root directory:

.. code-block:: bash

    cd tribler  # Wherever you have Tribler installed
    cp /usr/local/lib/libsodium.dylib ./ || cp /opt/local/lib/libsodium.dylib ./


Apple Silicon
-------
There are currently no python bindings available to install from pip.
Therefore you need to build them from source.

To do this, please install openssl and boost first:

.. code-block:: bash
    brew install openssl boost boost-build boost-python3

And then follow the `instruction <https://github.com/arvidn/libtorrent/blob/v1.2.18/docs/python_binding.rst>`_.


Windows
-------

You may need to install the following packages separately:

* `OpenSSL <https://community.chocolatey.org/packages?q=openssl>`_
* `Libsodium <https://github.com/Tribler/py-ipv8/blob/master/doc/preliminaries/install_libsodium.rst>`_
