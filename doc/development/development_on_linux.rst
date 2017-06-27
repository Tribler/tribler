This section contains information about setting up a Tribler development environment on Linux systems.

Debian/Ubuntu/Mint
------------------

First, install the required dependencies by executing the following command in your terminal:

.. code-block:: none

    sudo apt-get install libav-tools libsodium18 libx11-6 python-apsw python-cherrypy3 python-cryptography python-decorator python-dnspython python-ecdsa python-feedparser python-jsonrpclib python-leveldb python-libtorrent python-matplotlib python-m2crypto python-netifaces python-pbkdf2 python-pil python-protobuf python-pyasn1 python-pysocks python-requests python-twisted python2.7 vlc python-chardet python-configobj python-pyqt5 python-pyqt5.qtsvg

Next, download the latest .deb file from `here <https://jenkins.tribler.org/job/Build-Tribler_Ubuntu-64_devel/lastStableBuild/>`_.

Installing libsodium13 and python-cryptography on Ubuntu 14.04
--------------------------------------------------------------

While installing libsodium13 and python-cryptography on a clean Ubuntu 14.04 install (possibly other versions as well), the situation can occur where the Ubuntu terminal throws the following error when trying to install the dependencies mentioned earlier in the README.rst:

    E: Unable to locate package libsodium13
    E: Unable to locate package python-cryptography

This means that the required packages are not directly in the available package list of Ubuntu 14.04.

To install the packages, the required files have to be downloaded from their respective websites.

For libsodium13, download ``libsodium13\_1.0.1-1\_<ProcessorType\>.deb`` from `<http://packages.ubuntu.com/vivid/libsodium13](http://packages.ubuntu.com/vivid/libsodium13>`_

For python-cryptography, download ``python-cryptography\_0.8-1ubuntu2\_<ProcessorType\>.deb`` from `<http://packages.ubuntu.com/vivid/python-cryptography>`_.

**Installing the files**
**Through terminal**

After downloading files go to the download folder and install the files through terminal:

**For amd64:**

.. code-block:: none

    cd ./Downloads
    dpkg -i libsodium13_1.0.1-1_amd64.deb
    dpkg -i python-cryptography_0.8-1ubuntu2_amd64.deb

**For i386:**

.. code-block:: none

    cd ./Downloads
    dpkg -i libsodium13_1.0.1-1_i386.deb
    dpkg -i python-cryptography_0.8-1ubuntu2_i386.deb

**Through file navigator:**

Using the file navigator to go to the download folder and by clicking on the .deb files to have the software installer install the packages.

Now installing the list of dependencies should no longer throw an error.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.

Arch Linux
----------

Execute the following command in your terminal:

.. code-block:: none

    pacman -S libsodium libtorrent-rasterbar python2-pyqt5 qt5-svg phonon-qt5-vlc python2-apsw python2-cherrypy python2-cryptography python2-decorator python2-feedparser python2-chardet python2-m2crypto python2-netifaces python2-plyvel python2-requests python2-twisted python2-configobj python2-matplotlib
