This section contains information about setting up a Tribler development environment on Linux systems.

Debian/Ubuntu/Mint
------------------

First, install the required dependencies by executing the following command in your terminal:

.. code-block:: bash

    sudo apt install ffmpeg libssl-dev libx11-6 vlc libgmp-dev python2.7 python-minimal python-pip python-cherrypy3 python-libtorrent python-meliae python-pyqt5 python-pyqt5.qtsvg python-scipy python-typing

Secondly, install python packages

.. code-block:: bash

 pip install bitcoinlib chardet configobj decorator dnspython ecdsa feedparser jsonrpclib leveldb matplotlib netifaces networkx pbkdf2 pony protobuf psutil pyaes pyasn1 pysocks requests lz4

Then, install py-ipv8 python dependencies

.. code-block:: bash

    cd Tribler/pyipv8
    pip install --upgrade -r requirements.txt

Finally, download the latest tribler .deb file from `here <https://jenkins-ci.tribler.org/job/Build-Tribler_Ubuntu-64_devel/lastStableBuild/>`__.

Now installing the list of dependencies should no longer throw an error.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.

Arch Linux
----------

Execute the following command in your terminal:

.. code-block:: bash

    pacman -S libsodium libtorrent-rasterbar python2-pyqt5 qt5-svg phonon-qt5-vlc python2-cherrypy python2-cryptography python2-decorator python2-chardet python2-netifaces python2-twisted python2-configobj python2-matplotlib python2-networkx python2-psutil python2-scipy python2-libnacl python2-lz4 python2-pony python2-pyopenssl python2-typing
