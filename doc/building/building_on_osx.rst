This section contains information about building Tribler on macOS. The final result you should have is a ``.dmg`` file which, when opened, allows ``Tribler.app`` to be copied to the Applications directory. This guide has been tested on macOS 10.11 (El Capitan). It is recommended to run this builder on a system that is already able to run Tribler without problems (it means that all the required packages required by Tribler are installed already). Information about setting up a developer environment on macOS can be found `here <(https://github.com/Tribler/tribler/blob/devel/doc/development/development_on_osx.rst>`_.

Required packages
-----------------

To build and distribute Tribler, there are some required scripts and packages:
* The git command tools are required to fetch the latest release information. They are installed when you start Xcode for the first time but you can also install it using ``brew`` or another package library.
* PyInstaller: this library creates an executable binary and can be installed using pip (``pip install pyinstaller``).
* vlc: PyInstaller automatically searches for the vlc library in the system and bundles it.
* The builder needs to find all packages that are required by Tribler so make sure you can run Tribler on your machine and that there are no missing dependencies.
* In order to attach the EULA to the ``.dmg`` file, we make use of the ``eulagise`` script. This script is written in PERL and is based on a more fully-featured script. The script can be dowloaded from `GitHub <https://github.com/CompoFX/compo/blob/master/tool/eulagise.pl>`_. The builder expects the script to be executable and added to the ``PATH`` environment variable. This can be done with the following commands:

.. code-block:: none

    cp eulagise.pl /usr/local/bin/eulagise
    chmod +x /usr/local/bin/eulagise
    eulagise # to test it - it should show that you should add some flags

Building Tribler on macOS
-------------------------
Start by checking out the directory you want to clone (using ``git clone --recursive``). Open a terminal and ``cd`` to this new cloned directory (referenced to as ``tribler_source`` in this guide).

Next, we should inject version information into the files about the latest release. This is done by the ``update_version_from_git.py`` script found in ``Tribler/Main/Build``. Invoke it from the ``tribler_source`` directory by executing:

.. code-block:: none

    Tribler/Main/Build/update_version_from_git.py

Now execute the builder with the following command:

.. code-block:: none

    ./mac/makedistmac_64bit.sh

This will create the ``.dmg`` file in the ``tribler_source/dist`` directory.
