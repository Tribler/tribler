This section contains information about setting up a Tribler development environment on Linux systems.

Debian/Ubuntu/Mint
------------------

First, install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install ffmpeg libssl-dev libx11-6 vlc libgmp-dev python3 python3-minimal python3-pip python3-libtorrent python3-pyqt5 python3-pyqt5.qtsvg python3-scipy

Secondly, install python packages

.. code-block:: bash

    pip3 install bitcoinlib chardet configobj decorator dnspython ecdsa feedparser jsonrpclib matplotlib netifaces networkx pbkdf2 pony protobuf psutil pyaes pyasn1 pysocks requests lz4 pyqtgraph

Then, install py-ipv8 python dependencies

.. code-block:: bash

    cd src/pyipv8
    pip install --upgrade -r requirements.txt

Finally, download the latest tribler .deb file from `here <https://jenkins-ci.tribler.org/job/Build-Tribler_Ubuntu-64_devel/lastStableBuild/>`__.

Now installing the list of dependencies should no longer throw an error.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.

