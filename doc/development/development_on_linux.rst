This section contains information about setting up a Tribler development environment on Linux systems.

Debian 12
------------------

Install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install git libssl-dev libx11-6 libgmp-dev python3 python3-minimal python3-pip python3-libtorrent python3-pyqt5 python3-pyqt5.qtsvg python3-scipy python3-full libboost-tools-dev libboost-dev libboost-system-dev

Clone the Tribler repo:

.. code-block:: bash

    git clone https://github.com/tribler/tribler

Install python packages:

.. code-block:: bash

    mkdir tribler_env
    python3 -m venv tribler_env
    perl -pi -e 's/libtorrent==.*/async_timeout==4.0.3/g' tribler/requirements-core.txt
    ./tribler_env/bin/pip3 install --upgrade -r tribler/requirements.txt

Install libtorrent (it's missing from pip) (requiers ~2GB RAM per CPU):

.. code-block:: bash

    wget "https://github.com/arvidn/libtorrent/releases/download/v1.2.19/libtorrent-rasterbar-1.2.19.tar.gz"
    tar -xf libtorrent-rasterbar-1.2.19.tar.gz
    cd libtorrent-rasterbar-1.2.19
    echo "using gcc ;" >>~/user-config.jam
    ln -s /usr/lib/x86_64-linux-gnu/libboost_python311.so.1.74.0 /usr/lib/x86_64-linux-gnu/libboost_python311.so
    ../tribler_env/bin/python3 setup.py build


Run Tribler by executing the following commands:

.. code-block:: bash

    tribler/src/tribler.sh  > tribler.log

Alternatively, you can run the latest stable version of Tribler by downloading and installing the .deb file from `here <https://github.com/tribler/tribler/releases/>`__. This option is only recommended for running Tribler and is not suitable for development.


Ubuntu/Mint
------------------

Install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install git libssl-dev libx11-6 libgmp-dev python3 python3-minimal python3-pip python3-libtorrent python3-pyqt5 python3-pyqt5.qtsvg python3-scipy

Clone the Tribler repo:

.. code-block:: bash

    git clone https://github.com/tribler/tribler


Install python packages:

.. code-block:: bash

    pip3 install --upgrade -r tribler/requirements.txt


Run Tribler by executing the following commands:

.. code-block:: bash

    tribler/src/tribler.sh  > tribler.log

Alternatively, you can run the latest stable version of Tribler by downloading and installing the .deb file from `here <https://github.com/tribler/tribler/releases/>`__. This option is only recommended for running Tribler and is not suitable for development.


Fedora/CentOS/RedHat
------------------

Install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo dnf install python3-devel python3-pip git

Clone the Tribler repo:

.. code-block:: bash

    git clone https://github.com/tribler/tribler


Install python packages:

.. code-block:: bash

    pip3 install --upgrade -r tribler/requirements.txt

Run Tribler by executing the following commands:

.. code-block:: bash

    tribler/src/tribler.sh  > tribler.log

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
