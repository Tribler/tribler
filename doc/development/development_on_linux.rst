This section contains information about setting up a Tribler development environment on Linux systems.

Debian/Ubuntu/Mint
------------------

Install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install git libssl-dev libx11-6 libgmp-dev python3 python3-minimal python3-pip python3-libtorrent python3-pyqt5 python3-pyqt5.qtsvg python3-scipy

Clone the Tribler repo:

.. code-block:: bash

    git clone https://github.com/tribler/tribler --recursive


Install python packages:

.. code-block:: bash

    pip3 install --upgrade -r tribler/src/requirements.txt


Install py-ipv8 python dependencies:

.. code-block:: bash

    pip3 install --upgrade -r tribler/src/pyipv8/requirements.txt

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

    git clone https://github.com/tribler/tribler --recursive


Install python packages:

.. code-block:: bash

    pip3 install --upgrade -r tribler/src/requirements.txt


Install py-ipv8 python dependencies

.. code-block:: bash

    pip3 install --upgrade -r tribler/src/pyipv8/requirements.txt

Run Tribler by executing the following commands:

.. code-block:: bash

    tribler/src/tribler.sh  > tribler.log

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
