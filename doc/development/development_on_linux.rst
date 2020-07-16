This section contains information about setting up a Tribler development environment on Linux systems.

Debian/Ubuntu/Mint
------------------

First, install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install git libssl-dev libx11-6 vlc libgmp-dev python3 python3-minimal python3-pip python3-libtorrent python3-pyqt5 python3-pyqt5.qtsvg python3-scipy

Secondly, install python packages

.. code-block:: bash

    pip3 install aiohttp aiohttp_apispec chardet configobj decorator libnacl matplotlib netifaces networkx pony psutil pyasn1 requests lz4 pyqtgraph

Then, install py-ipv8 python dependencies

.. code-block:: bash

    cd src/pyipv8
    pip install --upgrade -r requirements.txt

You can now clone the Tribler source code, and run Tribler by executing the following commands:

.. code-block:: bash

    git clone https://github.com/tribler/tribler --recursive
    cd tribler/src
    ./tribler.sh

Alternatively, you can run the latest stable version of Tribler by downloading and installing the .deb file from `here <https://github.com/tribler/tribler/releases/>`__. This option is only recommended for running Tribler and is not suitable for development.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
